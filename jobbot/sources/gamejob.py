"""게임잡 (gamejob.co.kr) 수집기 — 이 봇의 메인 소스.

게임잡은 게임 업계 전용이라 직군 분류가 정확하다. 직무 코드는 검색 페이지의
필터 트리(data-value-json)에서 가져온 값이며, /recruit/_GI_Job_List 가
필터 + 페이지네이션을 그대로 받는 부분 렌더링 엔드포인트다.
"""

from __future__ import annotations

import html as H
import logging
import re

import httpx

from ..models import Posting
from .base import UA, Source

log = logging.getLogger(__name__)

LIST_URL = "https://www.gamejob.co.kr/recruit/_GI_Job_List"
VIEW_URL = "https://www.gamejob.co.kr/Recruit/GI_Read/View?GI_No={}"
PAGE_SIZE = 40

# 카테고리 -> 게임잡 직무 코드
#   1 게임개발(클라이언트) / 2 게임개발(모바일) / 6 모델링 / 9 게임기획 / 16 서버
DUTY_CODES = {
    "기획": ["9"],
    "모델링": ["6"],
    "서버": ["16"],
    "클라이언트": ["1", "2"],
}

_ROW = re.compile(r"<tr>\s*<td>.*?</tr>", re.S)
_GI = re.compile(r"GI_No=(\d+)")
_CO = re.compile(r'class="company[^"]*">\s*<a[^>]*>\s*<strong>(.*?)</strong>', re.S)
_TI = re.compile(r'class="tit">\s*<a[^>]*>\s*<strong>(.*?)</strong>', re.S)
_INFO = re.compile(r'<p class="info">(.*?)</p>', re.S)
_SPAN = re.compile(r"<span>(.*?)</span>", re.S)
_DATE = re.compile(r'<span class="date">(.*?)</span>', re.S)
_TOTAL = re.compile(r'totalJobcnt">\((\d+)\)')


def _clean(s: str) -> str:
    return H.unescape(re.sub(r"<[^>]+>", "", s)).strip()


class GameJob(Source):
    name = "gamejob"

    def __init__(self, delay: float = 0.7, max_pages: int = 30, only_entry: bool = False):
        super().__init__(delay)
        self.max_pages = max_pages
        self.only_entry = only_entry

    async def fetch(self, client: httpx.AsyncClient) -> list[Posting]:
        out: list[Posting] = []
        for category, codes in DUTY_CODES.items():
            out += await self._fetch_category(client, category, ",".join(codes))
        log.info("[gamejob] %d건 수집", len(out))
        return out

    def _career_params(self) -> dict[str, str]:
        """경력 공고를 서버에서 미리 걸러 받아올 파라미터.

        career_stat 0=신입, 2=경력무관 / career=1_3 은 1~3년.
        두 조건은 OR 로 합쳐진다 (신입 17 + 무관 127 + 1~3년 151 = 295 로 확인).
        """
        if not self.only_entry:
            return {}
        return {"career_stat": "0,2", "career": "1_3"}

    async def _fetch_category(self, client, category: str, duty: str) -> list[Posting]:
        headers = {
            "User-Agent": UA,
            "X-Requested-With": "XMLHttpRequest",
            "Referer": "https://www.gamejob.co.kr/Recruit/joblist?menucode=duty",
        }
        found: dict[str, Posting] = {}
        total = None
        for page in range(1, self.max_pages + 1):
            r = await self._get(
                client,
                LIST_URL,
                params={"Page": page, "duty": duty, **self._career_params()},
                headers=headers,
            )
            if r is None:
                break
            doc = r.text
            if total is None:
                m = _TOTAL.search(doc)
                total = int(m.group(1)) if m else None

            rows = self._parse(doc, category)
            if not rows:
                break
            before = len(found)
            for p in rows:
                found.setdefault(p.external_id, p)
            # 같은 페이지가 반복되거나 마지막 페이지면 중단
            if len(found) == before or len(rows) < PAGE_SIZE:
                break
            if total is not None and len(found) >= total:
                break

        log.info("[gamejob] %s: %d건 (사이트 표기 %s)", category, len(found), total)
        return list(found.values())

    def _parse(self, doc: str, category: str) -> list[Posting]:
        out = []
        for m in _ROW.finditer(doc):
            row = m.group(0)
            gi = _GI.search(row)
            ti = _TI.search(row)
            if not (gi and ti):
                continue
            co = _CO.search(row)
            info = _INFO.search(row)
            spans = [_clean(s) for s in _SPAN.findall(info.group(1))] if info else []
            date = _DATE.search(row)

            # info 스팬 순서: 경력 / 학력 / 지역 / 게임장르 / 고용형태
            career = spans[0] if len(spans) > 0 else ""
            location = spans[2] if len(spans) > 2 else ""
            employment = spans[4] if len(spans) > 4 else ""

            out.append(
                Posting(
                    source=self.name,
                    external_id=gi.group(1),
                    category=category,
                    title=_clean(ti.group(1)),
                    company=_clean(co.group(1)) if co else "",
                    url=VIEW_URL.format(gi.group(1)),
                    career_raw=career,
                    location=location,
                    employment=employment,
                    deadline=_clean(date.group(1)) if date else "",
                    tags=spans[3].split(", ") if len(spans) > 3 and spans[3] else [],
                )
            )
        return out

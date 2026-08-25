"""사람인 (saramin.co.kr) 수집기.

사람인에는 게임 전용 직무 트리가 없어서 키워드 검색을 쓴다. 검색이 헐거워
"게임 기획"으로 검색해도 경영기획·UI디자이너 같은 공고가 딸려 오므로,
relevance.is_relevant() 로 두 단계를 거른다.
  1) 제목·회사·직무태그에 게임 업계 신호가 있어야 하고
  2) 제목에 해당 직군 용어가 있어야 하며 제외어에 걸리면 버린다.
"""

from __future__ import annotations

import html as H
import logging
import re

import httpx

from ..models import Posting
from ..relevance import is_relevant
from .base import UA, Source

log = logging.getLogger(__name__)

SEARCH = "https://www.saramin.co.kr/zf_user/search/recruit"
VIEW_URL = "https://www.saramin.co.kr/zf_user/jobs/relay/view?rec_idx={}"
PAGE_SIZE = 40

KEYWORDS = {
    "기획": ["게임 기획", "레벨 디자이너", "게임 시스템 기획"],
    "아트": ["게임 3D 모델러", "게임 애니메이터", "게임 그래픽 디자이너"],
    "서버": ["게임 서버 개발", "게임 백엔드"],
    "클라이언트": ["게임 클라이언트", "유니티 개발", "언리얼 개발"],
}

_ITEM = re.compile(
    r'<div class="item_recruit"[^>]*value="(\d+)".*?'
    r'(?=<div class="item_recruit"|<div class="pagination)',
    re.S,
)
_TITLE = re.compile(r'<h2 class="job_tit">\s*<a[^>]*title="([^"]*)"', re.S)
_CORP = re.compile(r'<strong class="corp_name">\s*<a[^>]*>(.*?)</a>', re.S)
_COND = re.compile(r'<div class="job_condition">(.*?)</div>', re.S)
_SPAN = re.compile(r"<span>(.*?)</span>", re.S)
_DATE = re.compile(r'<span class="date">(.*?)</span>', re.S)
_SECTOR = re.compile(r'<div class="job_sector">(.*?)</div>', re.S)


def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", H.unescape(re.sub(r"<[^>]+>", " ", s))).strip()


class Saramin(Source):
    name = "saramin"

    def __init__(self, delay: float = 0.7, max_pages: int = 5):
        super().__init__(delay)
        self.max_pages = max_pages

    async def fetch(self, client: httpx.AsyncClient) -> list[Posting]:
        out: list[Posting] = []
        for category, words in KEYWORDS.items():
            seen: dict[str, Posting] = {}
            for word in words:
                for p in await self._search(client, category, word):
                    seen.setdefault(p.external_id, p)
            log.info("[saramin] %s: %d건", category, len(seen))
            out += seen.values()
        log.info("[saramin] %d건 수집", len(out))
        return out

    async def _search(self, client, category: str, word: str) -> list[Posting]:
        headers = {"User-Agent": UA, "Referer": "https://www.saramin.co.kr/"}
        out: list[Posting] = []
        for page in range(1, self.max_pages + 1):
            params = {
                "searchword": word,
                "recruitPage": page,
                "recruitSort": "reg_dt",
                "recruitPageCount": PAGE_SIZE,
            }
            r = await self._get(client, SEARCH, params=params, headers=headers)
            if r is None:
                break
            rows, raw_count = self._parse(r.text, category)
            out += rows
            if raw_count < PAGE_SIZE:
                break
        return out

    def _parse(self, doc: str, category: str) -> tuple[list[Posting], int]:
        out: list[Posting] = []
        raw = 0
        for m in _ITEM.finditer(doc):
            raw += 1
            block, rec = m.group(0), m.group(1)
            t = _TITLE.search(block)
            if not t:
                continue
            title = H.unescape(t.group(1)).strip()
            corp = _CORP.search(block)
            company = _clean(corp.group(1)) if corp else ""
            sector = _SECTOR.search(block)
            sector_txt = _clean(sector.group(1)) if sector else ""

            if not is_relevant(category, title, f"{company} {sector_txt}"):
                continue

            cond = _COND.search(block)
            spans = [_clean(s) for s in _SPAN.findall(cond.group(1))] if cond else []
            # 스팬 순서: 지역 / 경력 / 학력 / 고용형태
            location = spans[0] if len(spans) > 0 else ""
            career = spans[1] if len(spans) > 1 else ""
            employment = spans[3] if len(spans) > 3 else ""
            date = _DATE.search(block)

            out.append(
                Posting(
                    source=self.name,
                    external_id=rec,
                    category=category,
                    title=title,
                    company=company,
                    url=VIEW_URL.format(rec),
                    career_raw=career,
                    location=location,
                    employment=employment,
                    deadline=_clean(date.group(1)) if date else "",
                )
            )
        return out, raw

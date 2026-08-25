"""잡코리아 (jobkorea.co.kr) 수집기.

검색 결과가 React로 렌더링되고 클래스명이 Tailwind 유틸리티라 안정적인
선택자가 거의 없다. 카드 경계는 data-sentry-component="CardJob" 로 잡고,
카드 안에서 GI_Read 로 가는 앵커 두 개(첫째=공고명, 둘째=회사명)를 쓴다.
카드 안 텍스트를 순서대로 읽는 방식은 배지("즉시 지원" 등) 때문에 밀리므로
쓰지 않는다.

검색 상단에는 게임과 무관한 광고 공고가 섞이므로 relevance.is_relevant() 로 걸러낸다.
그래도 네 소스 중 가장 깨지기 쉬워서 config.yaml 기본값은 off.
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

SEARCH = "https://www.jobkorea.co.kr/Search/"
VIEW_URL = "https://www.jobkorea.co.kr/Recruit/GI_Read/{}"

KEYWORDS = {
    "기획": ["게임기획", "레벨디자이너"],
    "아트": ["게임 3D모델러", "게임 애니메이터", "게임 그래픽"],
    "서버": ["게임서버", "게임 백엔드"],
    "클라이언트": ["게임클라이언트", "유니티", "언리얼"],
}

NOISE = {"스크랩", "즉시 지원", "AD", "지금 주목할 만한 공고"}

_CARD = re.compile(r'data-sentry-component="CardJob"')
_ANCHOR = re.compile(r'<a\b[^>]*href="([^"]*)"[^>]*>(.*?)</a>', re.S)
_GID = re.compile(r"/Recruit/GI_Read/(\d+)")
_CAREER = re.compile(r"(신입\s*·?\s*경력|신입|경력무관|경력\s*\d+년\s*[↑~])")
_REGION = re.compile(
    r"^(서울|경기|인천|부산|대구|대전|광주|울산|세종|강원|충북|충남|"
    r"전북|전남|경북|경남|제주|전국|해외)"
)


def _text(fragment: str) -> str:
    return H.unescape(re.sub(r"<[^>]+>", " ", fragment)).strip()


def _parts(seg: str) -> list[str]:
    raw = re.sub(r"<[^>]+>", "\x01", seg)
    out = []
    for p in raw.split("\x01"):
        p = H.unescape(p).strip()
        if p and p not in NOISE and not p.startswith("data-sentry"):
            out.append(p)
    return out


class JobKorea(Source):
    name = "jobkorea"

    def __init__(self, delay: float = 0.7, max_pages: int = 3):
        super().__init__(delay)
        self.max_pages = max_pages

    async def fetch(self, client: httpx.AsyncClient) -> list[Posting]:
        out: list[Posting] = []
        for category, words in KEYWORDS.items():
            seen: dict[str, Posting] = {}
            for word in words:
                for p in await self._search(client, category, word):
                    seen.setdefault(p.external_id, p)
            log.info("[jobkorea] %s: %d건", category, len(seen))
            out += seen.values()
        log.info("[jobkorea] %d건 수집", len(out))
        return out

    async def _search(self, client, category: str, word: str) -> list[Posting]:
        headers = {"User-Agent": UA, "Referer": "https://www.jobkorea.co.kr/"}
        out: list[Posting] = []
        for page in range(1, self.max_pages + 1):
            r = await self._get(
                client, SEARCH, params={"stext": word, "Page_No": page}, headers=headers
            )
            if r is None:
                break
            rows = self._parse(r.text, category)
            if not rows:
                break
            out += rows
        return out

    def _parse(self, doc: str, category: str) -> list[Posting]:
        marks = [m.start() for m in _CARD.finditer(doc)]
        out: list[Posting] = []
        for i, start in enumerate(marks):
            end = marks[i + 1] if i + 1 < len(marks) else min(start + 8000, len(doc))
            seg = doc[start:end]

            gid = _GID.search(seg)
            if not gid:
                continue
            anchors = [t for _, t in ((u, _text(v)) for u, v in _ANCHOR.findall(seg)) if t]
            if len(anchors) < 2:
                continue
            title, company = anchors[0], anchors[1]

            rest = [p for p in _parts(seg) if p not in (title, company)]
            body = " ".join(rest)
            if not is_relevant(category, title, f"{company} {body}"):
                continue

            cm = _CAREER.search(body)
            # 카드에는 지역 말고 "탄탄한 중견기업" 같은 홍보 배지도 섞여 있다.
            location = next((p for p in rest if _REGION.match(p)), "")

            out.append(
                Posting(
                    source=self.name,
                    external_id=gid.group(1),
                    category=category,
                    title=title,
                    company=company,
                    url=VIEW_URL.format(gid.group(1)),
                    career_raw=cm.group(1) if cm else "",
                    location=location,
                )
            )
        return out

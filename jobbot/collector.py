"""활성화된 소스를 모두 돌려 공고를 모으고, 경력 구분을 매긴다."""

from __future__ import annotations

import asyncio
import logging

import httpx

from .classify import apply_levels
from .models import SENIOR, Posting
from .sources import REGISTRY

log = logging.getLogger(__name__)


def _build(name: str, delay: float, only_entry: bool):
    cls = REGISTRY[name]
    # 게임잡만 서버쪽 경력 필터를 지원한다. 나머지는 아래에서 로컬로 거른다.
    if name == "gamejob":
        return cls(delay=delay, only_entry=only_entry)
    return cls(delay=delay)


async def collect(cfg: dict) -> list[Posting]:
    enabled = [n for n, on in (cfg.get("sources") or {}).items() if on]
    delay = float(cfg.get("request_delay", 0.7))
    only_entry = bool(cfg.get("only_entry", False))
    sources = [_build(n, delay, only_entry) for n in enabled if n in REGISTRY]
    log.info("수집 시작: %s", ", ".join(s.name for s in sources) or "(없음)")

    limits = httpx.Limits(max_connections=8)
    async with httpx.AsyncClient(
        timeout=30.0, follow_redirects=True, limits=limits
    ) as client:
        results = await asyncio.gather(
            *(s.fetch(client) for s in sources), return_exceptions=True
        )

    postings: list[Posting] = []
    for src, res in zip(sources, results):
        if isinstance(res, Exception):
            log.error("[%s] 수집 실패: %s", src.name, res)
            continue
        postings += res

    apply_levels(postings, int(cfg.get("entry_max_years", 3)))

    if only_entry:
        # 게임잡은 서버에서 이미 걸렀지만, 나머지 세 소스와 게임잡이 흘린 것까지
        # 여기서 한 번 더 막는다. 판정 기준을 한 곳에 두는 게 안전하다.
        before = len(postings)
        postings = [p for p in postings if p.level != SENIOR]
        dropped = before - len(postings)
        if dropped:
            log.info("경력 공고 %d건 제외", dropped)

    log.info("총 %d건 수집 완료", len(postings))
    return postings

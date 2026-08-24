"""활성화된 소스를 모두 돌려 공고를 모으고, 경력 구분을 매긴다."""

from __future__ import annotations

import asyncio
import logging

import httpx

from .classify import apply_levels
from .models import Posting
from .sources import REGISTRY

log = logging.getLogger(__name__)


async def collect(cfg: dict) -> list[Posting]:
    enabled = [n for n, on in (cfg.get("sources") or {}).items() if on]
    delay = float(cfg.get("request_delay", 0.7))
    sources = [REGISTRY[n](delay=delay) for n in enabled if n in REGISTRY]
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
    log.info("총 %d건 수집 완료", len(postings))
    return postings

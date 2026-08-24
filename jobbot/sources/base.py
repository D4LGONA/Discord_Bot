"""수집 소스 공통 뼈대."""

from __future__ import annotations

import asyncio
import logging

import httpx

from ..models import Posting

log = logging.getLogger(__name__)

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)


class Source:
    name = "base"

    def __init__(self, delay: float = 0.7):
        self.delay = delay

    async def fetch(self, client: httpx.AsyncClient) -> list[Posting]:
        raise NotImplementedError

    async def _get(self, client: httpx.AsyncClient, url: str, **kw) -> httpx.Response | None:
        """실패해도 예외를 밖으로 던지지 않는다. 한 소스가 죽어도 나머지는 살아야 한다."""
        try:
            r = await client.get(url, **kw)
            r.raise_for_status()
            return r
        except Exception as exc:  # noqa: BLE001
            log.warning("[%s] 요청 실패 %s: %s", self.name, url, exc)
            return None
        finally:
            await asyncio.sleep(self.delay)

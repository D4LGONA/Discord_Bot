"""원티드 (wanted.co.kr) 수집기.

원티드는 "게임" 직군 그룹(959) 하나로 요청하면 게임 공고만 정확히 내려주고,
공고마다 category_tag.id 가 붙어 있어 직군 분류를 로컬에서 정확히 할 수 있다.
annual_from/annual_to 로 요구 연차가 숫자로 오는 것도 장점.

한계: 이 엔드포인트는 최신 50건에서 잘린다. offset·sort·job_category_id 를
넘겨도 서버가 무시한다(직접 확인함). 매일 신규분만 뽑는 용도라 실사용에는
문제가 없지만, 원티드 게임 공고 전체(200여 건)를 한 번에 받지는 못한다.
"""

from __future__ import annotations

import logging

import httpx

from ..models import Posting
from .base import UA, Source

log = logging.getLogger(__name__)

API = "https://www.wanted.co.kr/api/chaos/navigation/v1/results"
VIEW_URL = "https://www.wanted.co.kr/wd/{}"
GAME_GROUP = 959     # 직군 그룹 "게임"
HARD_LIMIT = 50      # 서버가 강제하는 상한

# 원티드 직무 태그 id -> 우리 카테고리
#   958 게임운영자(GM) 는 4개 직군에 해당하지 않아 제외
TAG_TO_CATEGORY = {
    892: "기획",        # 게임 기획자
    880: "아트",        # 게임 그래픽 디자이너
    881: "아트",        # 게임 아티스트
    960: "서버",        # 게임 서버 개발자
    961: "클라이언트",  # 게임 클라이언트 개발자
    878: "클라이언트",  # 유니티 개발자
    897: "클라이언트",  # 언리얼 개발자
    962: "클라이언트",  # 모바일 게임 개발자
}


class Wanted(Source):
    name = "wanted"

    async def fetch(self, client: httpx.AsyncClient) -> list[Posting]:
        params = {
            "country": "kr",
            "job_group_id": GAME_GROUP,
            "sort": "job.latest_order",
            "limit": HARD_LIMIT,
            "offset": 0,
        }
        r = await self._get(
            client, API, params=params, headers={"User-Agent": UA, "Accept": "application/json"}
        )
        if r is None:
            return []
        try:
            data = r.json().get("data") or []
        except Exception as exc:  # noqa: BLE001
            log.warning("[wanted] JSON 파싱 실패: %s", exc)
            return []

        out = []
        for j in data:
            tag = (j.get("category_tag") or {}).get("id")
            category = TAG_TO_CATEGORY.get(tag)
            if category is None:
                continue
            out.append(self._to_posting(j, category))

        by_cat: dict[str, int] = {}
        for p in out:
            by_cat[p.category] = by_cat.get(p.category, 0) + 1
        log.info("[wanted] %d건 수집 %s", len(out), by_cat)
        return out

    def _to_posting(self, j: dict, category: str) -> Posting:
        addr = j.get("address") or {}
        loc = " ".join(x for x in (addr.get("location"), addr.get("district")) if x)
        a_from, a_to = j.get("annual_from"), j.get("annual_to")

        if a_from is None:
            career_raw, career_min = "", None
        elif a_from == 0:
            career_raw, career_min = "신입 · 경력무관", 0
        elif a_to and a_to < 100:
            career_raw, career_min = f"경력 {a_from}~{a_to}년", a_from
        else:
            career_raw, career_min = f"경력 {a_from}년↑", a_from

        return Posting(
            source=self.name,
            external_id=str(j.get("id")),
            category=category,
            title=(j.get("position") or "").strip(),
            company=((j.get("company") or {}).get("name") or "").strip(),
            url=VIEW_URL.format(j.get("id")),
            career_raw=career_raw,
            career_min=career_min,
            location=loc,
            deadline=(j.get("due_time") or "상시")[:10],
        )

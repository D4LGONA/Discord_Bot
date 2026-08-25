"""공고 하나를 표현하는 공통 자료구조."""

from __future__ import annotations

from dataclasses import dataclass, field

# 사용자가 요청한 4개 직군. 표시 순서도 이 순서를 따른다.
CATEGORIES = ("기획", "클라이언트", "서버", "아트")

# 경력 구분
ENTRY = "entry"    # 인턴/신입 지원가능 (요구경력 N년 이하)
SENIOR = "senior"  # 경력 공고

LEVEL_LABEL = {
    ENTRY: "인턴 · 신입 지원가능",
    SENIOR: "경력",
}


@dataclass(slots=True)
class Posting:
    source: str            # gamejob / wanted / saramin / jobkorea
    external_id: str       # 사이트 내부 공고 ID
    category: str          # CATEGORIES 중 하나
    title: str
    company: str
    url: str
    career_raw: str = ""        # 사이트에 표기된 원문 (예: "경력3년↑")
    career_min: int | None = None   # 최소 요구경력. 신입/무관이면 0, 파악 실패 시 None
    location: str = ""
    employment: str = ""        # 정규직 / 계약직 / 인턴직 ...
    deadline: str = ""
    level: str = SENIOR         # ENTRY or SENIOR, classify.py가 채움
    tags: list[str] = field(default_factory=list)

    @property
    def key(self) -> tuple[str, str, str]:
        """중복 판정 키. 같은 공고가 여러 직군에 걸릴 수 있어 카테고리를 포함한다."""
        return (self.source, self.external_id, self.category)

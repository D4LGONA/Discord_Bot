"""사이트마다 제각각인 경력 표기를 하나의 기준으로 정규화한다."""

from __future__ import annotations

import re

from .models import ENTRY, SENIOR, Posting

# "경력3년↑", "경력 3년 이상", "3~5년", "경력 3-5년" 등에서 첫 숫자를 뽑는다.
_YEARS = re.compile(r"(\d+)\s*년")
_RANGE = re.compile(r"(\d+)\s*[~\-–]\s*(\d+)")

# 요구경력이 사실상 0인 표기들.
# "무관" 만 단독으로 넣으면 "학력무관"·"나이무관"까지 신입으로 빨려 들어간다.
_ZERO_TOKENS = ("신입", "경력무관", "경력 무관", "인턴", "신입/경력", "신입·경력")


def parse_career_years(raw: str) -> int | None:
    """표기 문자열에서 '최소 요구경력(년)'을 추출. 알 수 없으면 None."""
    if not raw:
        return None
    text = raw.strip()

    # 신입·경력무관·인턴은 경력 0년으로 본다.
    if any(tok in text for tok in _ZERO_TOKENS) and not _YEARS.search(text):
        return 0

    # "3~5년" 형태면 하한을 취한다.
    m = _RANGE.search(text)
    if m:
        return int(m.group(1))

    m = _YEARS.search(text)
    if m:
        return int(m.group(1))

    # 숫자는 없는데 신입 계열 단어가 섞인 경우 (예: "신입 경력")
    if any(tok in text for tok in _ZERO_TOKENS):
        return 0
    return None


def classify_level(posting: Posting, entry_max_years: int = 3) -> str:
    """인턴/신입 지원가능(ENTRY)인지 경력(SENIOR)인지 판정."""
    # 고용형태가 인턴이면 요구경력과 무관하게 신입 트랙으로 본다.
    if "인턴" in (posting.employment or ""):
        return ENTRY

    years = posting.career_min
    if years is None:
        years = parse_career_years(posting.career_raw)

    if years is None:
        # 경력 정보를 못 읽은 공고를 신입 목록에 섞으면 노이즈가 커진다.
        # 제목에 신입/주니어 신호가 있을 때만 신입으로 올린다.
        title = posting.title
        if any(tok in title for tok in ("신입", "주니어", "junior", "Junior", "인턴", "Intern")):
            return ENTRY
        return SENIOR

    return ENTRY if years <= entry_max_years else SENIOR


def apply_levels(postings: list[Posting], entry_max_years: int = 3) -> list[Posting]:
    for p in postings:
        if p.career_min is None:
            p.career_min = parse_career_years(p.career_raw)
        p.level = classify_level(p, entry_max_years)
    return postings

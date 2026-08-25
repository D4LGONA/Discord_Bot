"""수집한 공고를 디스코드 임베드로 조립한다."""

from __future__ import annotations

import re
from datetime import datetime

import discord

from .models import CATEGORIES, ENTRY, LEVEL_LABEL, SENIOR, Posting

# 디스코드 하드 리밋
DESC_LIMIT = 4000      # 실제 4096. 여유를 둔다
EMBED_TITLE_LIMIT = 250

CATEGORY_STYLE = {
    "기획": ("📝", 0x5865F2),
    "모델링": ("🎨", 0xEB459E),
    "서버": ("🗄️", 0x57F287),
    "클라이언트": ("🖥️", 0xFEE75C),
}

LEVEL_STYLE = {
    ENTRY: "🌱",
    SENIOR: "💼",
}

SOURCE_LABEL = {
    "gamejob": "게임잡",
    "wanted": "원티드",
    "saramin": "사람인",
    "jobkorea": "잡코리아",
}

# 임베드 설명은 마크다운으로 렌더링되므로 제목에 섞인 서식 문자를 죽인다.
_MD_CHARS = "*_~`|"


def _safe(text: str, limit: int = 78) -> str:
    """임베드 링크 텍스트로 안전하게. 대괄호는 링크 문법을 깨뜨린다."""
    t = text.replace("[", "(").replace("]", ")")
    for ch in _MD_CHARS:
        t = t.replace(ch, "\\" + ch)
    t = re.sub(r"\s+", " ", t).strip()
    return t if len(t) <= limit else t[: limit - 1] + "…"


def _line(p: Posting) -> str:
    meta = [p.company or "회사 미상"]
    if p.career_raw:
        meta.append(p.career_raw)
    if p.location:
        meta.append(p.location)
    meta.append(SOURCE_LABEL.get(p.source, p.source))
    return f"• [{_safe(p.title)}]({p.url})\n　{_safe(' · '.join(meta), 96)}"


def _sort_key(p: Posting):
    """신입 목록은 '신입 > 경력무관 > 경력N년' 순으로 보이게."""
    years = p.career_min if p.career_min is not None else 99
    agnostic = 1 if "무관" in p.career_raw else 0
    return (years, agnostic, p.company, p.title)


def build_embeds(
    postings: list[Posting],
    *,
    max_per_section: int = 25,
) -> list[discord.Embed]:
    """카테고리별로 임베드를 만든다. 길면 같은 카테고리를 여러 장으로 쪼갠다."""
    embeds: list[discord.Embed] = []
    today = datetime.now().strftime("%Y-%m-%d")

    for category in CATEGORIES:
        items = [p for p in postings if p.category == category]
        if not items:
            continue
        emoji, color = CATEGORY_STYLE[category]

        levels = [lv for lv in (ENTRY, SENIOR) if any(p.level == lv for p in items)]
        # 경력 공고를 안 받는 설정이면 구분이 하나뿐이라 섹션 제목이 군더더기가 된다.
        show_level_header = len(levels) > 1

        blocks: list[str] = []
        for level in levels:
            group = sorted((p for p in items if p.level == level), key=_sort_key)
            shown = group[:max_per_section]
            lines = [_line(p) for p in shown]
            if show_level_header:
                head = f"**{LEVEL_STYLE[level]} {LEVEL_LABEL[level]} — {len(group)}건**"
                if len(group) > len(shown):
                    head += f"  _(상위 {len(shown)}건만 표시)_"
                blocks.append(head + "\n" + "\n".join(lines))
            else:
                if len(group) > len(shown):
                    lines.append(f"_… 외 {len(group) - len(shown)}건_")
                blocks.append("\n".join(lines))

        if not blocks:
            continue

        # 4000자 제한에 맞춰 페이지로 분할
        pages: list[str] = []
        buf = ""
        for block in blocks:
            for chunk in _split_block(block, DESC_LIMIT):
                if len(buf) + len(chunk) + 2 > DESC_LIMIT:
                    if buf:
                        pages.append(buf)
                    buf = chunk
                else:
                    buf = f"{buf}\n\n{chunk}" if buf else chunk
        if buf:
            pages.append(buf)

        for i, page in enumerate(pages, 1):
            suffix = f" ({i}/{len(pages)})" if len(pages) > 1 else ""
            e = discord.Embed(
                title=f"{emoji} {category} — {len(items)}건{suffix}"[:EMBED_TITLE_LIMIT],
                description=page,
                color=color,
            )
            if i == len(pages):
                e.set_footer(text=f"{today} · 게임 개발자 채용공고")
            embeds.append(e)

    return embeds


def _split_block(block: str, limit: int) -> list[str]:
    """한 섹션이 통째로 제한을 넘으면 줄 단위로 쪼갠다."""
    if len(block) <= limit:
        return [block]
    out, buf = [], ""
    for line in block.split("\n"):
        if len(buf) + len(line) + 1 > limit:
            out.append(buf)
            buf = line
        else:
            buf = f"{buf}\n{line}" if buf else line
    if buf:
        out.append(buf)
    return out


def summary_line(postings: list[Posting]) -> str:
    """'기획 3 · 모델링 1 · 서버 0 · 클라이언트 5' 형태의 한 줄 요약."""
    parts = []
    for c in CATEGORIES:
        n = sum(1 for p in postings if p.category == c)
        parts.append(f"{c} {n}")
    line = " · ".join(parts)
    # 경력 공고를 안 받는 설정이면 '경력 0' 을 굳이 보여줄 필요가 없다.
    senior = sum(1 for p in postings if p.level == SENIOR)
    if senior:
        entry = sum(1 for p in postings if p.level == ENTRY)
        line += f"  |  🌱 신입 {entry} · 💼 경력 {senior}"
    return line

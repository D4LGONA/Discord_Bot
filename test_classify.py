"""분류 로직 점검. 네트워크를 타지 않으므로 언제든 바로 돌릴 수 있다.

    python test_classify.py
"""

from jobbot.classify import classify_level, parse_career_years
from jobbot.digest import _safe, build_embeds
from jobbot.models import ENTRY, SENIOR, Posting
from jobbot.relevance import is_relevant

fails = []


def check(label, got, want):
    if got != want:
        fails.append(f"{label}: got {got!r}, want {want!r}")


# ── 경력 표기 파싱 ──────────────────────────────────────────
for raw, want in [
    ("신입", 0),
    ("경력무관", 0),
    ("신입 · 경력무관", 0),
    ("경력1년↑", 1),
    ("경력3년↑", 3),
    ("경력10년↑", 10),
    ("경력 3~5년", 3),
    ("경력 5~15년", 5),
    ("경력 3-12년", 3),
    ("", None),
    ("학력무관", None),
]:
    check(f"parse({raw!r})", parse_career_years(raw), want)


# ── 신입 / 경력 판정 ────────────────────────────────────────
def p(career="", title="게임 기획자", employment="", career_min=None):
    return Posting(
        source="t", external_id="1", category="기획", title=title,
        company="c", url="u", career_raw=career, career_min=career_min,
        employment=employment,
    )


for label, posting, want in [
    ("신입", p("신입"), ENTRY),
    ("경력무관", p("경력무관"), ENTRY),
    ("경력1년", p("경력1년↑"), ENTRY),
    ("경력3년(경계)", p("경력3년↑"), ENTRY),
    ("경력4년(경계)", p("경력4년↑"), SENIOR),
    ("경력10년", p("경력10년↑"), SENIOR),
    ("인턴 고용형태", p("경력5년↑", employment="인턴직"), ENTRY),
    ("표기없음+평범한제목", p(""), SENIOR),
    ("표기없음+신입제목", p("", title="신입 게임 기획자 모집"), ENTRY),
    ("표기없음+주니어제목", p("", title="주니어 클라이언트 개발자"), ENTRY),
    ("범위 2~5년", p("경력 2~5년"), ENTRY),
    ("범위 5~12년", p("경력 5~12년"), SENIOR),
]:
    check(f"level({label})", classify_level(posting, 3), want)


# ── 키워드 소스 관련성 필터 ─────────────────────────────────
for label, args, want in [
    ("게임 기획자", ("기획", "게임 시스템 기획자 모집", "넥슨 게임기획"), True),
    ("경영기획 배제", ("기획", "메타보라 경영기획 담당자", "카카오게임즈"), False),
    ("UI 디자이너는 기획 아님", ("기획", "2026년 게임 UI 디자이너 모집", "게임"), False),
    ("3D 모델러", ("모델링", "AAA 배경 에셋 모델러", "NC 게임"), True),
    ("서버 개발", ("서버", "FC개발실 서버 프로그래머", "넥슨 게임"), True),
    ("튜터 배제", ("서버", "온라인 튜터 (Unreal) 백엔드", "팀스파르타"), False),
    ("클라 개발", ("클라이언트", "Unreal Engine 클라이언트 개발자", "게임"), True),
    ("게임 신호 없음", ("클라이언트", "클라이언트 개발자", "금융 솔루션"), False),
]:
    check(f"relevant({label})", is_relevant(*args), want)


# ── 임베드 안전성 ───────────────────────────────────────────
check("링크 깨는 대괄호", "[" in _safe("[넥슨] 서버"), False)
check("마크다운 이스케이프", _safe("*중요*"), r"\*중요\*")

many = [
    Posting(source="gamejob", external_id=str(i), category="기획",
            title=f"아주 긴 게임 기획자 공고 제목 {i} " * 3, company=f"회사{i}",
            url=f"https://example.com/{i}", career_raw="신입", career_min=0, level=ENTRY)
    for i in range(120)
]
embeds = build_embeds(many, max_per_section=100)
over = [e for e in embeds if len(e.description or "") > 4096]
check("임베드 4096자 제한", len(over), 0)
check("임베드 생성됨", len(embeds) > 0, True)

# ── 결과 ────────────────────────────────────────────────────
if fails:
    print(f"실패 {len(fails)}건")
    for f in fails:
        print("  ✗", f)
    raise SystemExit(1)
print("모든 검사 통과")

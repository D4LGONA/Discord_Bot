"""키워드 검색 기반 소스(사람인·잡코리아)에서 무관한 공고를 걸러내는 규칙.

게임잡과 원티드는 사이트 자체에 게임 직군 분류가 있어서 이 모듈을 쓰지 않는다.
키워드 검색은 "게임 기획"으로 검색해도 경영기획·UI디자이너가 딸려 오기 때문에
직군 판정은 '공고 제목'만 보고, 회사·직무태그는 게임 업계 여부 판단에만 쓴다.
"""

from __future__ import annotations

# 게임 업계 공고인지 판별하는 신호 (제목·회사·직무태그 전체에서 찾는다)
GAME_HINTS = (
    "게임", "유니티", "unity", "언리얼", "unreal", "game",
    "모바일게임", "rpg", "메타버스", "nc", "넥슨", "넷마블", "크래프톤",
)

# 직군별 (필수 용어, 제외 용어). 필수 용어는 제목에서만 찾는다.
CATEGORY_TERMS: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "기획": (
        ("기획", "레벨디자", "레벨 디자", "밸런스", "시나리오", "planner",
         "게임디자", "game design", "narrative", "pd "),
        ("경영기획", "사업기획", "전략기획", "영업기획", "마케팅기획",
         "재무", "인사", "회계", "홍보"),
    ),
    "모델링": (
        ("모델러", "모델링", "원화", "아티스트", "artist", "그래픽", "3d",
         "캐릭터", "배경", "애니메이", "이펙트", "컨셉", "일러스트", "vfx"),
        ("영업", "회계", "인사", "마케팅"),
    ),
    "서버": (
        ("서버", "백엔드", "backend", "server", "인프라", "풀스택",
         "full-stack", "fullstack", "devops"),
        ("영업", "고객", "상담", "튜터", "강사", "교육"),
    ),
    "클라이언트": (
        ("클라이언트", "client", "유니티", "unity", "언리얼", "unreal",
         "클라 ", "클라개발", "프론트"),
        ("영업", "고객", "상담", "튜터", "강사", "교육", "qa"),
    ),
}


def is_relevant(category: str, title: str, context: str = "") -> bool:
    """제목이 해당 직군 공고인지, 그리고 게임 업계 공고인지 판정."""
    t = title.lower()
    ctx = f"{title} {context}".lower()

    if not any(h in ctx for h in GAME_HINTS):
        return False

    must, never = CATEGORY_TERMS.get(category, ((), ()))
    if any(n in t for n in never):
        return False
    return any(m in t for m in must)

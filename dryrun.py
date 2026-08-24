"""디스코드 없이 수집 → 분류 → 임베드 조립까지 그대로 돌려보는 점검 도구.

    python dryrun.py            # 전체 소스로 수집, DB에 저장하지 않음
    python dryrun.py --save     # DB에 저장까지 (신규 판정 동작 확인용)
    python dryrun.py --source gamejob
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys

import yaml

from jobbot.collector import collect
from jobbot.digest import build_embeds, summary_line
from jobbot.models import CATEGORIES, ENTRY, SENIOR
from jobbot.store import Store

logging.basicConfig(level=logging.INFO, format="%(levelname)-7s %(message)s", stream=sys.stdout)
logging.getLogger("httpx").setLevel(logging.WARNING)


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", action="append", help="이 소스만 사용 (여러 번 지정 가능)")
    ap.add_argument("--save", action="store_true", help="DB에 저장까지 수행")
    ap.add_argument("--db", default="data/dryrun.db")
    args = ap.parse_args()

    cfg = yaml.safe_load(open("config.yaml", encoding="utf-8"))
    if args.source:
        cfg["sources"] = {k: (k in args.source) for k in cfg["sources"]}

    postings = await collect(cfg)

    print("\n" + "=" * 68)
    print(f"수집 결과 {len(postings)}건")
    print("=" * 68)
    print(f"{'직군':<12}{'신입/3년이하':>14}{'경력':>10}{'합계':>8}")
    for c in CATEGORIES:
        sub = [p for p in postings if p.category == c]
        e = sum(1 for p in sub if p.level == ENTRY)
        s = sum(1 for p in sub if p.level == SENIOR)
        print(f"{c:<12}{e:>14}{s:>10}{len(sub):>8}")
    print(f"\n{summary_line(postings)}")

    by_source: dict[str, int] = {}
    for p in postings:
        by_source[p.source] = by_source.get(p.source, 0) + 1
    print("소스별:", ", ".join(f"{k} {v}" for k, v in sorted(by_source.items())))

    store = Store(args.db)
    fresh = store.filter_new(postings)
    print(f"\nDB 대비 신규: {len(fresh)}건 (DB 누적 {store.total()}건)")
    if args.save:
        store.save(fresh, posted=True)
        print(f"저장 완료 → {args.db} (누적 {store.total()}건)")

    embeds = build_embeds(fresh or postings, max_per_section=int(cfg.get("max_per_section", 25)))
    print(f"\n임베드 {len(embeds)}장 생성")
    over = [e for e in embeds if len(e.description or "") > 4096]
    print("4096자 초과 임베드:", len(over), "(0이어야 정상)")
    for e in embeds:
        print(f"  · {e.title}  ({len(e.description or '')}자)")

    if embeds:
        print("\n" + "-" * 68)
        print("첫 임베드 미리보기")
        print("-" * 68)
        print(embeds[0].title)
        print((embeds[0].description or "")[:1400])
    store.close()


if __name__ == "__main__":
    asyncio.run(main())

"""한 번 실행하고 끝나는 발송 스크립트. GitHub Actions 용.

봇을 계속 띄워두는 대신, 게이트웨이 접속 없이 REST API 로 채널에 글만 올린다.
이미 올린 공고는 data/seen.txt 에 기록하고, 워크플로가 그 파일을 커밋해서
다음 실행 때 기억하게 한다.

    python run_once.py            # 수집 → 새 공고 발송
    python run_once.py --dry-run  # 발송하지 않고 콘솔에만 출력
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys

import httpx
import yaml
from dotenv import load_dotenv

from jobbot.collector import collect
from jobbot.digest import build_embeds, summary_line
from jobbot.models import CATEGORIES
from jobbot.store import SeenFile

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s | %(message)s",
    datefmt="%H:%M:%S",
    stream=sys.stdout,
)
logging.getLogger("httpx").setLevel(logging.WARNING)
log = logging.getLogger("jobbot")

API = "https://discord.com/api/v10"
# 첫 실행 때 기준선만 잡으면 화면에 아무것도 안 보여 답답하다. 맛보기로 몇 개만 보여준다.
SEED_PREVIEW_PER_CATEGORY = 5


async def post(client: httpx.AsyncClient, channel_id: str, token: str,
               content: str | None = None, embeds: list | None = None) -> None:
    payload: dict = {}
    if content:
        payload["content"] = content[:2000]
    if embeds:
        payload["embeds"] = [e.to_dict() for e in embeds[:10]]
    r = await client.post(
        f"{API}/channels/{channel_id}/messages",
        headers={"Authorization": f"Bot {token}"},
        json=payload,
        timeout=30.0,
    )
    if r.status_code == 429:
        wait = float(r.json().get("retry_after", 1))
        log.warning("레이트리밋. %.1f초 대기 후 재시도", wait)
        await asyncio.sleep(wait + 0.5)
        return await post(client, channel_id, token, content, embeds)
    if r.status_code >= 400:
        raise RuntimeError(f"디스코드 발송 실패 {r.status_code}: {r.text[:300]}")


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="발송하지 않고 콘솔에만 출력")
    args = ap.parse_args()

    load_dotenv()
    cfg = yaml.safe_load(open("config.yaml", encoding="utf-8"))
    token = os.getenv("DISCORD_TOKEN")
    channel_id = os.getenv("DISCORD_CHANNEL_ID")
    if not args.dry_run and not (token and channel_id):
        log.error("DISCORD_TOKEN / DISCORD_CHANNEL_ID 가 없습니다.")
        return 1

    store = SeenFile()
    first_run = store.is_empty
    log.info("기존 기록 %d건%s", store.total(), " (첫 실행)" if first_run else "")

    postings = await collect(cfg)
    if not postings:
        log.error("한 건도 수집하지 못했습니다. 사이트 구조가 바뀌었을 수 있습니다.")
        return 1

    fresh = store.filter_new(postings)
    log.info("신규 %d건 / 전체 %d건", len(fresh), len(postings))

    if first_run:
        # 전부 '신규'라 그대로 올리면 채널이 터진다. 기준선만 잡고 맛보기만 보낸다.
        preview = []
        for c in CATEGORIES:
            preview += [p for p in fresh if p.category == c][:SEED_PREVIEW_PER_CATEGORY]
        content = (
            f"**채용공고 봇 설정 완료** — 기존 공고 {len(fresh)}건을 기준선으로 저장했습니다.\n"
            f"{summary_line(fresh)}\n"
            f"내일부터 매일 오전 6시에 **새로 올라온 공고만** 보내드립니다. "
            f"아래는 맛보기 {len(preview)}건입니다."
        )
        embeds = build_embeds(preview, max_per_section=SEED_PREVIEW_PER_CATEGORY)
    elif fresh:
        content = f"**오늘의 신규 채용공고 {len(fresh)}건**\n{summary_line(fresh)}"
        embeds = build_embeds(fresh, max_per_section=int(cfg.get("max_per_section", 25)))
    else:
        content, embeds = "오늘 새로 올라온 공고가 없습니다.", []

    if args.dry_run:
        print("\n" + content)
        for e in embeds:
            print(f"\n── {e.title} ──\n{(e.description or '')[:600]}")
        log.info("--dry-run 이라 발송하지 않았고 기록도 남기지 않았습니다.")
        return 0

    async with httpx.AsyncClient() as client:
        for i in range(0, max(len(embeds), 1), 10):
            await post(
                client, channel_id, token,
                content=content if i == 0 else None,
                embeds=embeds[i : i + 10],
            )
            await asyncio.sleep(0.5)

    store.add(fresh)
    log.info("발송 완료. 기록 %d건으로 갱신", store.total())
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

"""게임 개발자 채용공고 디스코드 봇.

매일 정해진 시각(기본 오전 6시 KST)에 게임잡·원티드·사람인·잡코리아에서
기획 / 클라이언트 / 서버 / 아트 공고를 수집해, 각 직군을
'인턴·신입 지원가능(3년 이하)' 과 '경력' 으로 나눠 채널에 올린다.

이미 올린 공고는 SQLite 에 기억해 두고 매일 새로 올라온 것만 발송한다.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import logging
import os
import sys
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import discord
import yaml
from discord import app_commands
from discord.ext import tasks
from dotenv import load_dotenv

from jobbot.collector import collect
from jobbot.digest import build_embeds, plan_messages, summary_line
from jobbot.models import CATEGORIES, ENTRY, SENIOR, Posting
from jobbot.store import Store

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s | %(message)s",
    datefmt="%H:%M:%S",
    stream=sys.stdout,
)
logging.getLogger("httpx").setLevel(logging.WARNING)
log = logging.getLogger("jobbot")

load_dotenv()
CFG = yaml.safe_load(open("config.yaml", encoding="utf-8"))

TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = int(os.getenv("DISCORD_CHANNEL_ID") or 0)

_TZ_NAME = CFG["schedule"].get("timezone", "Asia/Seoul")
try:
    TZ = ZoneInfo(_TZ_NAME)
except ZoneInfoNotFoundError:
    # 윈도우에는 tz 데이터베이스가 없어서 tzdata 패키지가 있어야 한다.
    sys.exit(
        f"시간대 '{_TZ_NAME}' 를 찾을 수 없습니다.\n"
        "  pip install tzdata\n"
        "를 실행한 뒤 다시 시도해 주세요."
    )
RUN_AT = dt.time(
    hour=int(CFG["schedule"].get("hour", 6)),
    minute=int(CFG["schedule"].get("minute", 0)),
    tzinfo=TZ,
)


class JobBot(discord.Client):
    def __init__(self) -> None:
        super().__init__(intents=discord.Intents.default())
        self.tree = app_commands.CommandTree(self)
        self.store = Store()
        self._lock = asyncio.Lock()   # 수집이 겹쳐 도는 것을 막는다

    async def setup_hook(self) -> None:
        await self.tree.sync()
        self.daily_digest.start()
        log.info("슬래시 명령 동기화 완료. 매일 %02d:%02d (%s) 발송 예정",
                 RUN_AT.hour, RUN_AT.minute, TZ)

    async def on_ready(self) -> None:
        log.info("로그인: %s (누적 %d건 적재됨)", self.user, self.store.total())

    # ── 수집 → 신규 선별 → 저장 ──────────────────────────────
    async def gather_new(self):
        """새 공고만 골라 저장하고 (신규목록, 첫실행여부) 를 돌려준다."""
        async with self._lock:
            first_run = self.store.is_empty and CFG.get("schedule", {}).get(
                "seed_on_first_run", True
            )
            postings = await collect(CFG)
            fresh = self.store.filter_new(postings)
            # 첫 실행이면 기존 공고 수백 건을 쏟아내지 않고 조용히 적재만 한다.
            self.store.save(fresh, posted=not first_run)
            log.info("신규 %d건 (전체 %d건 조회)", len(fresh), len(postings))
            return fresh, first_run

    async def send_digest(self, fresh, *, only_channel=None) -> None:
        """직군별 채널로 흩어 보낸다.

        only_channel 을 주면 (슬래시 명령처럼) 그 채널 한 곳에만 보낸다.
        """
        if only_channel is not None:
            if not fresh:
                await only_channel.send("오늘 새로 올라온 공고가 없습니다.")
                return
            header = f"**신규 채용공고 {len(fresh)}건**\n{summary_line(fresh)}"
            embeds = build_embeds(
                fresh, max_per_section=int(CFG.get("max_per_section", 25))
            )
            # 헤더는 임베드가 아니라 메시지 본문으로 붙인다.
            # 임베드 description 에 끼워 넣으면 4096자 한도를 넘길 수 있다.
            for i in range(0, len(embeds), 10):
                # 디스코드는 한 메시지에 임베드 10개까지
                await only_channel.send(
                    content=header if i == 0 else None, embeds=embeds[i : i + 10]
                )
            return

        for target, content, embeds in plan_messages(
            fresh, CFG, CHANNEL_ID, int(CFG.get("max_per_section", 25))
        ):
            channel = self.get_channel(int(target))
            if channel is None:
                log.error("채널 %s 를 찾을 수 없습니다.", target)
                continue
            for i in range(0, max(len(embeds), 1), 10):
                await channel.send(
                    content=content if i == 0 else None, embeds=embeds[i : i + 10]
                )

    # ── 매일 정해진 시각 ────────────────────────────────────
    @tasks.loop(time=RUN_AT)
    async def daily_digest(self) -> None:
        try:
            fresh, first_run = await self.gather_new()
        except Exception:
            log.exception("수집 중 오류")
            return
        if first_run:
            log.info("첫 실행이라 %d건을 조용히 적재했습니다. 내일부터 신규분만 발송합니다.", len(fresh))
            channel = self.get_channel(CHANNEL_ID)
            if channel is not None:
                await channel.send(
                    f"채용공고 봇을 시작했습니다. 기존 공고 {len(fresh)}건을 기준으로 잡아두었고, "
                    f"내일 {RUN_AT.hour:02d}:{RUN_AT.minute:02d}부터 새로 올라온 공고만 알려드립니다."
                )
            return
        await self.send_digest(fresh)

    @daily_digest.before_loop
    async def _wait(self) -> None:
        await self.wait_until_ready()


client = JobBot()


# ── 슬래시 명령 ──────────────────────────────────────────────
CATEGORY_CHOICES = [app_commands.Choice(name=c, value=c) for c in CATEGORIES]
LEVEL_CHOICES = [
    app_commands.Choice(name="인턴·신입 지원가능 (3년 이하)", value=ENTRY),
    app_commands.Choice(name="경력", value=SENIOR),
]


@client.tree.command(name="공고", description="저장된 채용공고를 직군·경력별로 보여줍니다.")
@app_commands.describe(직군="보고 싶은 직군", 구분="신입/경력 구분", 개수="최대 표시 수 (기본 15)")
@app_commands.choices(직군=CATEGORY_CHOICES, 구분=LEVEL_CHOICES)
async def cmd_jobs(
    interaction: discord.Interaction,
    직군: app_commands.Choice[str] | None = None,
    구분: app_commands.Choice[str] | None = None,
    개수: app_commands.Range[int, 1, 40] = 15,
):
    await interaction.response.defer(thinking=True)
    rows = client.store.recent(
        category=직군.value if 직군 else None,
        level=구분.value if 구분 else None,
        limit=개수,
    )
    if not rows:
        await interaction.followup.send("조건에 맞는 공고가 아직 없습니다. `/수집`으로 먼저 모아주세요.")
        return

    postings = [
        Posting(
            source=r["source"], external_id=r["external_id"], category=r["category"],
            title=r["title"] or "", company=r["company"] or "", url=r["url"] or "",
            career_raw=r["career_raw"] or "", career_min=r["career_min"],
            location=r["location"] or "", employment=r["employment"] or "",
            deadline=r["deadline"] or "", level=r["level"] or SENIOR,
        )
        for r in rows
    ]
    embeds = build_embeds(postings, max_per_section=개수)
    await interaction.followup.send(embeds=embeds[:10])


@client.tree.command(name="수집", description="지금 바로 수집해서 새 공고를 이 채널에 올립니다.")
async def cmd_collect(interaction: discord.Interaction):
    await interaction.response.defer(thinking=True)
    try:
        fresh, first_run = await client.gather_new()
    except Exception as exc:  # noqa: BLE001
        log.exception("수동 수집 실패")
        await interaction.followup.send(f"수집 중 오류가 났습니다: `{exc}`")
        return

    if first_run:
        await interaction.followup.send(
            f"첫 수집이라 기존 공고 {len(fresh)}건을 기준으로 저장했습니다. "
            "다음 수집부터 새 공고만 올라갑니다."
        )
        return
    if not fresh:
        await interaction.followup.send("새로 올라온 공고가 없습니다.")
        return
    await interaction.followup.send(f"새 공고 {len(fresh)}건을 찾았습니다.")
    await client.send_digest(fresh, only_channel=interaction.channel)


@client.tree.command(name="현황", description="지금까지 모은 공고 통계를 보여줍니다.")
async def cmd_stats(interaction: discord.Interaction):
    stats = client.store.stats()
    if not stats:
        await interaction.response.send_message("아직 모은 공고가 없습니다.")
        return
    table = {c: {ENTRY: 0, SENIOR: 0} for c in CATEGORIES}
    for r in stats:
        # level 이 비어 있는 옛 레코드가 섞여 있어도 죽지 않게 한다.
        if r["category"] in table and r["level"] in (ENTRY, SENIOR):
            table[r["category"]][r["level"]] = r["n"]

    e = discord.Embed(title="📊 수집 현황", color=0x2B2D31)
    for c in CATEGORIES:
        e.add_field(
            name=c,
            value=f"🌱 신입 **{table[c][ENTRY]}**\n💼 경력 **{table[c][SENIOR]}**",
            inline=True,
        )
    e.set_footer(
        text=f"총 {client.store.total()}건 · 매일 {RUN_AT.hour:02d}:{RUN_AT.minute:02d} 자동 발송"
    )
    await interaction.response.send_message(embed=e)


def main() -> None:
    if not TOKEN:
        sys.exit("DISCORD_TOKEN 이 없습니다. .env 파일을 만들어 주세요 (.env.example 참고).")
    if not CHANNEL_ID:
        sys.exit("DISCORD_CHANNEL_ID 가 없습니다. .env 파일을 확인해 주세요.")
    client.run(TOKEN, log_handler=None)


if __name__ == "__main__":
    main()

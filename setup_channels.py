"""직군별 채널을 이름으로 찾아 config.yaml 에 채워 넣는다.

채널 ID 4개를 손으로 복사하지 않아도 되게, 봇이 볼 수 있는 채널 목록에서
직군 이름과 맞는 것을 찾아 준다. '기획', '공고-기획', '💼기획' 처럼
직군 이름이 들어가 있기만 하면 잡힌다.

    python setup_channels.py
"""

from __future__ import annotations

import os
import re
import sys

import discord
import yaml
from dotenv import load_dotenv

from jobbot.models import CATEGORIES

CONFIG = "config.yaml"


def normalize(name: str) -> str:
    """이모지·구분자를 걷어내고 한글만 남긴다."""
    return re.sub(r"[^가-힣a-z]", "", name.lower())


def match(category: str, channels: list) -> list:
    key = normalize(category)
    return [c for c in channels if key in normalize(c.name)]


async def run(token: str) -> int:
    client = discord.Client(intents=discord.Intents.default())
    result = {"code": 1}

    @client.event
    async def on_ready():
        try:
            text_channels = [
                c for g in client.guilds for c in g.text_channels
                if c.permissions_for(g.me).send_messages
            ]
            if not text_channels:
                print("글을 쓸 수 있는 채널이 하나도 없습니다. 봇 권한을 확인해 주세요.")
                return

            print(f"\n봇이 볼 수 있는 채널 {len(text_channels)}개:")
            for c in text_channels:
                print(f"    #{c.name}")

            cfg = yaml.safe_load(open(CONFIG, encoding="utf-8"))
            cfg.setdefault("channels", {})
            print("\n직군 매칭:")
            missing = []
            for cat in CATEGORIES:
                hits = match(cat, text_channels)
                if len(hits) == 1:
                    cfg["channels"][cat] = hits[0].id
                    print(f"    {cat:<6} -> #{hits[0].name}")
                elif not hits:
                    cfg["channels"][cat] = None
                    missing.append(cat)
                    print(f"    {cat:<6} -> (없음)")
                else:
                    cfg["channels"][cat] = hits[0].id
                    names = ", ".join(f"#{c.name}" for c in hits)
                    print(f"    {cat:<6} -> #{hits[0].name}  (후보 여러 개: {names})")

            if missing:
                print(f"\n못 찾은 직군: {', '.join(missing)}")
                print("이름에 직군이 들어간 채널을 만들고 다시 실행해 주세요.")
                print("못 찾은 직군은 기본 채널로 발송됩니다.")

            with open(CONFIG, "w", encoding="utf-8") as f:
                yaml.safe_dump(cfg, f, allow_unicode=True, sort_keys=False)
            print(f"\n{CONFIG} 에 저장했습니다.")
            print("\n다음 단계:")
            print("    git add config.yaml")
            print('    git commit -m "직군별 채널 연결"')
            print("    git push")
            result["code"] = 0
        finally:
            await client.close()

    try:
        await client.start(token)
    except discord.LoginFailure:
        print("토큰이 올바르지 않습니다.")
    except Exception as exc:  # noqa: BLE001
        print(f"접속 실패: {exc}")
    finally:
        if not client.is_closed():
            await client.close()
    return result["code"]


def main() -> None:
    load_dotenv()
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        sys.exit("DISCORD_TOKEN 이 없습니다. python setup.py 를 먼저 실행해 주세요.")
    import asyncio

    sys.exit(asyncio.run(run(token)))


if __name__ == "__main__":
    main()

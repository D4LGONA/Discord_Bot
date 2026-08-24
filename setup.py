"""봇 최초 설정 도우미.

토큰과 채널 ID만 붙여넣으면 .env 를 만들고, 실제로 디스코드에 접속해서
- 토큰이 맞는지
- 그 채널이 보이는지
- 그 채널에 글 쓸 권한이 있는지
까지 확인해 준다.

    python setup.py
"""

from __future__ import annotations

import asyncio
import re
import sys
from pathlib import Path

try:
    import discord
except ImportError:
    sys.exit("먼저 설치해 주세요:  pip install -r requirements.txt")

ENV = Path(".env")


def ask(prompt: str, validate, hint: str) -> str:
    while True:
        try:
            value = input(prompt).strip()
        except (EOFError, KeyboardInterrupt):
            sys.exit("\n취소했습니다.")
        if not value:
            print("   비어 있습니다. 다시 입력해 주세요.\n")
            continue
        if not validate(value):
            print(f"   {hint}\n")
            continue
        return value


async def verify(token: str, channel_id: int) -> bool:
    """실제로 접속해서 채널과 권한까지 확인한다."""
    client = discord.Client(intents=discord.Intents.default())
    result = {"ok": False}

    @client.event
    async def on_ready():
        try:
            print(f"\n   ✓ 로그인 성공: {client.user}")
            channel = client.get_channel(channel_id)
            if channel is None:
                try:
                    channel = await client.fetch_channel(channel_id)
                except Exception:
                    channel = None
            if channel is None:
                print("   ✗ 그 채널을 찾을 수 없습니다.")
                print("     · 채널 ID를 잘못 복사했거나")
                print("     · 봇이 아직 그 서버에 초대되지 않았습니다.")
                return

            print(f"   ✓ 채널 확인: #{getattr(channel, 'name', channel_id)}")
            perms = channel.permissions_for(channel.guild.me)
            if not perms.send_messages:
                print("   ✗ 이 채널에 메시지를 보낼 권한이 없습니다. (Send Messages)")
                return
            if not perms.embed_links:
                print("   ✗ 임베드 권한이 없습니다. (Embed Links)")
                return
            print("   ✓ 메시지·임베드 권한 있음")

            await channel.send("✅ 채용공고 봇 설정 완료. 이 채널로 공고를 보내겠습니다.")
            print("   ✓ 테스트 메시지 발송 (채널을 확인해 보세요)")
            result["ok"] = True
        finally:
            await client.close()

    try:
        await client.start(token)
    except discord.LoginFailure:
        print("\n   ✗ 토큰이 올바르지 않습니다. Reset Token 후 다시 복사해 주세요.")
    except Exception as exc:  # noqa: BLE001
        print(f"\n   ✗ 접속 실패: {exc}")
    finally:
        # 로그인 실패로 빠져나오면 커넥터가 열린 채 남아 경고가 찍힌다.
        if not client.is_closed():
            await client.close()
        await asyncio.sleep(0.25)
    return result["ok"]


def main() -> None:
    print("=" * 60)
    print("  게임 채용공고 봇 설정")
    print("=" * 60)

    if ENV.exists():
        if input("\n.env 가 이미 있습니다. 새로 만들까요? (y/N) ").strip().lower() != "y":
            sys.exit("그대로 두었습니다.")

    print("""
[1] 봇 토큰
    https://discord.com/developers/applications
    → New Application → 왼쪽 Bot → Reset Token → 복사
""")
    token = ask(
        "    토큰 붙여넣기: ",
        lambda v: len(v) > 50 and "." in v,
        "토큰 형식이 아닙니다. 보통 70자 안팎이고 점(.)이 들어 있습니다.",
    )

    print("""
[2] 봇을 서버에 초대했나요?
    OAuth2 → URL Generator
      SCOPES         : bot, applications.commands
      BOT PERMISSIONS: Send Messages, Embed Links
    생성된 URL로 접속 → 내 서버 선택 → 승인
""")
    input("    초대를 마쳤으면 Enter: ")

    print("""
[3] 채널 ID
    디스코드 설정 → 고급 → 개발자 모드 켜기
    → 공고 받을 채널 우클릭 → 채널 ID 복사
""")
    channel_id = ask(
        "    채널 ID 붙여넣기: ",
        lambda v: re.fullmatch(r"\d{17,20}", v) is not None,
        "채널 ID는 숫자만 17~20자리입니다. 채널 '이름'이 아니라 '아이디'를 복사해 주세요.",
    )

    print("\n[4] 디스코드에 접속해서 확인하는 중...")
    ok = asyncio.run(verify(token, int(channel_id)))

    if not ok:
        print("\n확인에 실패했습니다. .env 는 만들지 않았습니다.")
        print("위 메시지를 보고 고친 뒤 다시 실행해 주세요:  python setup.py")
        sys.exit(1)

    ENV.write_text(
        f"DISCORD_TOKEN={token}\nDISCORD_CHANNEL_ID={channel_id}\n", encoding="utf-8"
    )
    print(f"\n   ✓ {ENV.resolve()} 저장 완료")
    print("""
설정이 끝났습니다. 이제 봇을 켜세요:

    python bot.py

첫 실행은 기존 공고를 조용히 저장만 하고, 내일 오전 6시부터 새 공고를 보냅니다.
바로 보고 싶으면 디스코드 채널에서  /수집  을 입력하세요.
""")


if __name__ == "__main__":
    main()

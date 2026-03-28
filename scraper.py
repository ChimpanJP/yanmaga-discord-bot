"""
ヤンマガWeb 曜日別 Discord投稿スクリプト
GitHub Actions で毎日 JST 0:01 に実行される
"""

import os
import asyncio
import httpx
from datetime import datetime, timezone, timedelta

DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "")
BASE_URL = "https://yanmaga.jp/comics/series"
EMBED_COLOR = 0x1E90FF

DAY_MAP = {
    0: ("monday",    "月曜日"),
    1: ("tuesday",   "火曜日"),
    2: ("wednesday", "水曜日"),
    3: ("thursday",  "木曜日"),
    4: ("friday",    "金曜日"),
    5: ("saturday",  "土曜日"),
    6: ("sunday",    "日曜日"),
}


async def main():
    jst = timezone(timedelta(hours=9))
    now_jst = datetime.now(jst)
    day_slug, day_label = DAY_MAP[now_jst.weekday()]

    print(f"🕐 実行時刻 (JST): {now_jst.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"📅 曜日: {day_label}")

    if not DISCORD_WEBHOOK_URL:
        print("⚠️  DISCORD_WEBHOOK_URL が設定されていません")
        return

    payload = {
        "embeds": [{
            "title": f"📅 {day_label}の連載作品",
            "description": f"[ヤンマガWeb]({BASE_URL}#{day_slug})",
            "color": EMBED_COLOR,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "footer": {"text": "ヤンマガWeb 自動投稿Bot"},
        }]
    }

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(DISCORD_WEBHOOK_URL, json=payload)
        if resp.status_code in (200, 204):
            print("✅ Discord 送信成功")
        else:
            print(f"❌ Discord 送信失敗 [{resp.status_code}]: {resp.text}")


if __name__ == "__main__":
    asyncio.run(main())

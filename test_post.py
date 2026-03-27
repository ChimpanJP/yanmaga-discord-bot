"""
疎通確認用テストスクリプト

使い方:
  DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/... python test_post.py

または .env ファイルに書いておく場合:
  python test_post.py
"""

import os
import asyncio
import httpx
from datetime import datetime, timezone

# .env ファイルがあれば読み込む（python-dotenv が入っていれば）
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "")


async def test_webhook():
    if not DISCORD_WEBHOOK_URL:
        print("❌ DISCORD_WEBHOOK_URL が設定されていません")
        print("   例: DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/... python test_post.py")
        return

    print("📤 Discord へテストメッセージを送信中...")

    payload = {
        "embeds": [{
            "title": "✅ ヤンマガBot 疎通確認",
            "description": "このメッセージが届いていれば設定は正常です！\n本番では毎日 **JST 0:01** に自動投稿されます。",
            "color": 0x1E90FF,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "footer": {"text": "ヤンマガWeb 自動投稿Bot - テスト"},
            "fields": [
                {"name": "Webhook URL", "value": DISCORD_WEBHOOK_URL[:40] + "...", "inline": False},
                {"name": "実行時刻", "value": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "inline": True},
            ]
        }]
    }

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(DISCORD_WEBHOOK_URL, json=payload)

    if resp.status_code in (200, 204):
        print("✅ 成功！Discordチャンネルを確認してください")
    else:
        print(f"❌ 失敗 [{resp.status_code}]: {resp.text}")


if __name__ == "__main__":
    asyncio.run(test_webhook())

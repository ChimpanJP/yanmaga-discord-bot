"""
ヤンマガWeb 曜日別連載スクレイパー & Discord投稿スクリプト
GitHub Actions で毎日 JST 0:01 に実行される
"""

import os
import re
import json
import asyncio
import httpx
from datetime import datetime, timezone, timedelta
from playwright.async_api import async_playwright

# ========== 設定 ==========
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "")
BASE_URL = "https://yanmaga.jp/comics/series"

DAY_MAP = {
    0: ("monday",    "月曜日"),
    1: ("tuesday",   "火曜日"),
    2: ("wednesday", "水曜日"),
    3: ("thursday",  "木曜日"),
    4: ("friday",    "金曜日"),
    5: ("saturday",  "土曜日"),
    6: ("sunday",    "日曜日"),
}

EMBED_COLOR = 0x1E90FF  # ヤンマガカラー（青）


# ========== スクレイピング ==========

# 曜日ラベル → slug の逆引きマップ
LABEL_TO_SLUG = {label: slug for slug, label in DAY_MAP.values()}


async def scrape_all_by_day() -> dict[str, list[dict]]:
    """
    全曜日の作品を一括取得し {day_slug: [comics]} を返す。
    ページに含まれる全作品を取得してから曜日ごとに分類する。
    """
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox",
                  "--disable-dev-shm-usage", "--disable-gpu"],
        )
        page = await (await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 900},
        )).new_page()

        await page.goto(BASE_URL, wait_until="networkidle", timeout=60000)

        # ポップアップを閉じる
        try:
            await page.evaluate(
                "const p=document.getElementById('popup');if(p)p.style.display='none';"
            )
            await page.keyboard.press("Escape")
            await page.wait_for_timeout(500)
        except Exception:
            pass

        # 各曜日の「もっと見る」ボタンを全て押して全件展開する
        for slug, _label in DAY_MAP.values():
            while True:
                btn = page.locator(
                    f'button.week-episode-more-button[data-week="{slug}"]'
                )
                try:
                    if not await btn.count():
                        break
                    if not await btn.is_visible(timeout=2000):
                        break
                    await btn.evaluate("el => el.scrollIntoView({block:'center'})")
                    await page.wait_for_timeout(300)
                    await btn.evaluate("el => el.click()")
                    await page.wait_for_timeout(1500)
                except Exception:
                    break

        # DOM から「曜日ラベル → 直後のコミックリンク群」を収集する
        # 曜日ラベル要素を順番に見つけ、次の曜日ラベルまでの <a href="/comics/..."> を割り当てる
        day_labels_js = json.dumps(list(LABEL_TO_SLUG.keys()))
        raw = await page.evaluate(f"""
            () => {{
                const LABELS = {day_labels_js};
                const SKIP = ['/comics/series', '/comics/authors', '/comics/books',
                              '/tags', '/ranking'];

                // 全テキストノードを走査し、曜日ラベルが何番目の「区切り」か記録する
                // 戦略: body 内の全 <a href*=/comics/> を順番に取り出し、
                //        直前に現れた曜日ラベルのテキストをキーとして紐付ける
                const result = {{}};
                for (const l of LABELS) result[l] = [];

                // すべての要素を DFS 順で走査
                const walker = document.createTreeWalker(
                    document.body,
                    NodeFilter.SHOW_ELEMENT,
                    null
                );

                let currentLabel = null;
                const seen = new Set();

                while (walker.nextNode()) {{
                    const el = walker.currentNode;

                    // 曜日ラベル検出（テキストが完全一致 & <a> ではない）
                    if (el.tagName !== 'A' && el.children.length === 0) {{
                        const t = el.textContent.trim();
                        if (LABELS.includes(t)) {{
                            currentLabel = t;
                            continue;
                        }}
                    }}

                    // コミックリンク検出
                    if (el.tagName === 'A' && currentLabel) {{
                        const href = el.getAttribute('href') || '';
                        if (!href.includes('/comics/')) continue;
                        if (SKIP.some(s => href === s || href.startsWith(s + '#'))) continue;
                        if (href === '/comics' || href === '/comics/') continue;
                        if (seen.has(href)) continue;
                        seen.add(href);

                        const img = el.querySelector('img');
                        const bgDiv = el.querySelector('[data-bg]');
                        const src = img
                            ? (img.getAttribute('src') || img.getAttribute('data-src') || '')
                            : (bgDiv ? (bgDiv.getAttribute('data-bg') || '') : '');
                        const alt = img ? (img.getAttribute('alt') || '') : '';

                        let title = '';
                        const h2 = el.querySelector('h2,h3,h4');
                        if (h2) title = h2.textContent.trim();
                        if (!title) title = alt;
                        if (!title) title = el.textContent.trim().split('\\n')[0].trim();

                        const fullUrl = href.startsWith('http') ? href : 'https://yanmaga.jp' + href;
                        const fullImg = src.startsWith('http') ? src
                            : (src ? 'https://yanmaga.jp' + src : '');

                        if (title) result[currentLabel].push({{ title, url: fullUrl, image_url: fullImg }});
                    }}
                }}

                return result;
            }}
        """)

        await browser.close()

    # ラベル → slug に変換
    results = {}
    for label, slug in LABEL_TO_SLUG.items():
        comics = raw.get(label, [])
        results[slug] = comics
        print(f"  {label} ({slug}): {len(comics)} 作品")

    return results


# ========== Discord 投稿 ==========

def build_embeds(day_label: str, day_slug: str, comics: list[dict]) -> list[dict]:
    """
    Discord Embed リストを構築する。
    Discord は 1メッセージあたり最大 10 Embed。
    各 Embed に作品1つ（画像+タイトル+URL）を入れる。
    """
    embeds = []

    # 先頭に曜日ヘッダー Embed
    header = {
        "title": f"📅 {day_label}の連載作品",
        "description": f"{len(comics)} 作品 | [ヤンマガWeb]({BASE_URL}#{day_slug})",
        "color": EMBED_COLOR,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "footer": {"text": "ヤンマガWeb 自動投稿Bot"},
    }
    embeds.append(header)

    for comic in comics:
        embed = {
            "title": comic["title"] or "（タイトル不明）",
            "url": comic["url"],
            "color": EMBED_COLOR,
            "image": {"url": comic["image_url"]},
        }
        embeds.append(embed)

    return embeds


async def post_to_discord(embeds: list[dict]) -> None:
    """
    Discord Webhook へ投稿。
    1回あたり最大10 Embed に分割して送信。
    """
    if not DISCORD_WEBHOOK_URL:
        print("  ⚠️  DISCORD_WEBHOOK_URL が設定されていません")
        return

    chunk_size = 10
    async with httpx.AsyncClient(timeout=30) as client:
        for i in range(0, len(embeds), chunk_size):
            chunk = embeds[i:i + chunk_size]
            payload = {"embeds": chunk}
            resp = await client.post(DISCORD_WEBHOOK_URL, json=payload)

            if resp.status_code in (200, 204):
                print(f"    ✅  Discord 送信成功 ({i+1}〜{i+len(chunk)})")
            else:
                print(f"    ❌  Discord 送信失敗 [{resp.status_code}]: {resp.text}")

            # レートリミット対策（Discord: 5リクエスト/2秒）
            await asyncio.sleep(0.5)


# ========== メイン ==========

async def main():
    # JST の現在曜日を取得
    jst = timezone(timedelta(hours=9))
    now_jst = datetime.now(jst)
    day_of_week = now_jst.weekday()  # 0=月, 6=日

    print(f"🕐 実行時刻 (JST): {now_jst.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"📅 曜日: {DAY_MAP[day_of_week][1]} (slug: {DAY_MAP[day_of_week][0]})")

    day_slug, day_label = DAY_MAP[day_of_week]

    # --- スクレイピング（全曜日取得 → 当日フィルタ）---
    print("\n🔍 スクレイピング開始...")
    all_data = await scrape_all_by_day()

    comics = all_data.get(day_slug, [])
    print(f"\n📚 本日({day_label})の取得結果: {len(comics)} 作品")

    # デバッグ出力
    if os.environ.get("DEBUG"):
        print(json.dumps(all_data, ensure_ascii=False, indent=2))

    if not comics:
        print("⚠️  作品データが取得できませんでした。Discordへの投稿をスキップします。")
        # 空の場合もエラーとして通知
        if DISCORD_WEBHOOK_URL:
            async with httpx.AsyncClient(timeout=30) as client:
                await client.post(DISCORD_WEBHOOK_URL, json={
                    "embeds": [{
                        "title": f"⚠️ {day_label}の連載取得失敗",
                        "description": "ヤンマガWebからデータを取得できませんでした。",
                        "color": 0xFF6B6B,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }]
                })
        return

    # --- Discord 投稿 ---
    print("\n📤 Discord への投稿開始...")
    embeds = build_embeds(day_label, day_slug, comics)
    await post_to_discord(embeds)

    print("\n✅ 完了！")


if __name__ == "__main__":
    asyncio.run(main())

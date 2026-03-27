# ヤンマガWeb → Discord 自動投稿Bot

毎日 **JST 0:01** にヤンマガWebをスクレイピングし、
その曜日の連載作品（サムネイル画像＋作品URL）を Discord に自動投稿します。

**運用コスト: 完全無料**（GitHub Actions 使用）

---

## 📁 ファイル構成

```
yanmaga-discord-bot/
├── scraper.py                        # メインスクリプト（本番用）
├── test_post.py                      # 疎通確認用テストスクリプト
├── requirements.txt                  # Python依存パッケージ
├── .github/
│   └── workflows/
│       └── yanmaga-post.yml          # GitHub Actions ワークフロー
└── README.md                         # この手順書
```

---

## 🚀 セットアップ手順

### STEP 1｜Discord Webhook URLを取得

1. Discordサーバーの投稿したいチャンネルを開く
2. チャンネル名を右クリック → **チャンネルの編集**
3. 左メニュー **連携サービス** → **ウェブフック**
4. **新しいウェブフック** を作成
5. **ウェブフックURLをコピー** をクリック（後で使うので控えておく）

---

### STEP 2｜疎通確認（ローカルで動作テスト）

GitHubにpushする前に、まずDiscordへの接続が正しいか確認します。

```bash
# 依存パッケージをインストール
pip install httpx

# テスト実行（YOUR_WEBHOOK_URL を実際のURLに置き換える）
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/xxx/yyy py test_post.py
```

Discordチャンネルに「✅ ヤンマガBot 疎通確認」が届けば成功です。

---

### STEP 3｜GitHubリポジトリを作成してpush

```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/YOUR_USERNAME/yanmaga-discord-bot.git
git push -u origin master
```

> **注意**: `.github/workflows/` のフォルダ階層をそのまま維持してください。
> この階層が崩れると GitHub Actions が認識されません。

---

### STEP 4｜GitHub Secrets に Webhook URL を登録

1. GitHubリポジトリの **Settings** タブを開く
2. 左メニュー **Secrets and variables** → **Actions**
3. **New repository secret** をクリック
4. 以下を入力して **Add secret**：

| Name | Value |
|------|-------|
| `DISCORD_WEBHOOK_URL` | STEP 1 でコピーした Webhook URL |

---

### STEP 5｜GitHub Actions で動作確認

1. リポジトリの **Actions** タブを開く
2. 左メニューから「ヤンマガWeb → Discord 毎日投稿」を選択
3. 右側の **Run workflow** → **Run workflow** をクリック
4. 数分後、Discordチャンネルに作品一覧が投稿されれば完了！

---

## ⏰ 実行スケジュール

自動実行のため、何もしなくてもGitHubが毎日起動してくれます。

| タイムゾーン | 時刻 |
|---|---|
| JST（日本標準時） | 毎日 0:01 |
| UTC（世界協定時） | 毎日 15:01（前日） |

cron 式: `1 15 * * *`

> GitHub Actions のスケジュール実行は高負荷時に最大30分程度遅延する場合があります。

---

## 💡 無料枠の目安

| リポジトリ種別 | 無料枠 | 本Botの消費 |
|---|---|---|
| パブリック | **無制限** | 無制限 |
| プライベート | 2,000分/月 | 約90分/月（余裕あり） |

**常時稼働ではありません。** 1回あたり約2〜3分で起動・処理・停止するため、待機中は一切消費しません。

---

## 🔧 トラブル時：セレクタの調整

ヤンマガWebのHTML構造が変わった場合、`scraper.py` の `page.evaluate(...)` 内の
セレクタを修正する必要があります。

ブラウザの開発者ツール（F12 → Console）で以下を実行して構造を確認してください：

```javascript
document.getElementById('monday')
```

---

## ⚠️ 注意事項

- ヤンマガWebの利用規約を遵守してください
- 過度なアクセスを避けるため、1日1回の実行に留めています
- サイト構造の変更により動作しなくなる場合があります（その際はセレクタを修正）

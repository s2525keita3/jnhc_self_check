# JNHC-MRA｜現在地スコアチェック PWA

訪問看護ステーションの営業・採用・教育の3部門を5分でチェックできる
PWA（Progressive Web App）です。

## 📂 ファイル構成

```
jnhc_pwa/
├── index.html              ← メインHTML（PWA対応済み）
├── manifest.json           ← PWA設定ファイル
├── sw.js                   ← Service Worker（オフライン対応）
├── vercel.json             ← Vercelデプロイ設定
├── icon.svg                ← アイコンソース（編集可能）
├── icon-192.png            ← Android用アイコン
├── icon-512.png            ← Android用アイコン（大）
├── icon-maskable.png       ← Android maskable用
├── apple-touch-icon.png    ← iOS用ホーム画面アイコン
└── favicon-32.png          ← ファビコン
```

## 🚀 Vercelへのデプロイ手順

### 方法A：Vercel CLI を使う（最速）

```bash
# Vercel CLI をインストール（初回のみ）
npm i -g vercel

# このフォルダで実行
cd jnhc_pwa
vercel

# 質問にすべてEnterで答えると数十秒でデプロイ完了
# 表示されるURLでアクセス可能
```

### 方法B：Vercel管理画面からドラッグ&ドロップ

1. https://vercel.com にログイン
2. 「Add New...」→「Project」
3. 「Deploy a static site」を選択
4. このフォルダを丸ごとドラッグ&ドロップ
5. デプロイ完了

### 方法C：GitHubと連携（推奨・長期運用）

1. GitHubにリポジトリ作成
2. このフォルダの中身をプッシュ
3. Vercelで「Import Project」から選択
4. 以降、プッシュするたび自動デプロイ

## 📱 ユーザーの使い方

### iPhone（Safari）
1. デプロイされたURLをSafariで開く
2. 画面下部「📱 ホーム画面に追加できます」バナーが表示
3. 共有ボタン → 「ホーム画面に追加」
4. ホーム画面にJNHC-MRAアイコンが追加される

### Android（Chrome）
1. デプロイされたURLをChromeで開く
2. 画面下部「📱 アプリとして追加」バナーが表示
3. 「追加する」ボタンをタップ
4. ホーム画面にアイコンが追加される

## 🔄 アップデート方法

ファイルを修正したら再デプロイ：
```bash
vercel --prod
```

Service Workerのキャッシュを更新したい場合、`sw.js` の
`CACHE_NAME` を `jnhc-self-check-v2` のようにバージョン番号を上げる。

## 🎨 カスタマイズ

### アイコンを変える
`icon.svg` を編集してから、各サイズのPNGを再生成：
```bash
# Python + cairosvg を使う場合
python3 -c "
import cairosvg
for s in [192, 512]:
    cairosvg.svg2png(url='icon.svg', write_to=f'icon-{s}.png', output_width=s, output_height=s)
cairosvg.svg2png(url='icon.svg', write_to='apple-touch-icon.png', output_width=180, output_height=180)
cairosvg.svg2png(url='icon.svg', write_to='favicon-32.png', output_width=32, output_height=32)
"
```

### アプリ名を変える
`manifest.json` の `name` と `short_name` を編集。
HTML の `apple-mobile-web-app-title` も同時に変更。

### 質問内容を変える
`index.html` の各セクションを編集。
Lv判定ロジックは末尾のJavaScript内 `submitBtn` クリックハンドラーで定義。

## 📞 配布フロー（協会会員28社向け）

1. Vercelにデプロイ → URL取得（例：jnhc-check.vercel.app）
2. 独自ドメイン設定（任意）：check.jnhc-mra.or.jp など
3. URLを協会LINEで一斉配信
4. 会員が各自スマホでアクセス → ホーム画面に追加
5. 必要なときにいつでもアプリ感覚で起動・チェック可能

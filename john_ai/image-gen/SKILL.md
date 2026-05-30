---
name: image-gen
description: >-
  gpt-image を使って画像を生成・編集するスキル。研修/セールスのスライド画像、
  YouTube サムネイル、アイコン、バナー等の「新規生成」と、既存画像の「編集
  (差し替え・要素追加/削除・テキスト修正・マスク編集)」の両方に対応する。
  ユーザーが画像を作りたい / 直したいとき、または gpt-image / DALL·E 相当の
  画像生成を求めたときに使う。
---

# image-gen

gpt-image(OpenAI Images API)を叩いて画像を**生成**・**編集**するためのスキル。

このスキルの目的は、人間が拙いプロンプトで API を直叩きするのではなく、
**エージェントが間に入って意図を汲み取り、質の高いプロンプトに翻訳してから**
画像モデルを呼ぶこと。特に編集系タスクは、何を残し・何を変えるかを言語化して
渡せるかどうかで結果が大きく変わる。

## 前提

- 環境変数 `OPENAI_API_KEY` が必要。
- モデルは環境変数 `OPENAI_IMAGE_MODEL` で切替可能(デフォルト `gpt-image-1`)。
  利用可能なら `gpt-image-2` 等を指定してよい。
- 依存パッケージのインストール:

  ```bash
  pip install -r john_ai/image-gen/requirements.txt
  ```

## 使い方の流れ(エージェント向け)

1. **意図を確認する。** 用途(スライド / YouTube サムネ / アイコン等)、
   アスペクト比、入れたい文字、雰囲気、NG を把握する。曖昧なら 1〜2 個だけ質問。
2. **トンマナを読む。** まず [`styles/jnhc-brand.md`](styles/jnhc-brand.md)（JNHC
   マスター）を読み、用途に応じてチャネル別プリセットを継承する:
   - 営業資料 → [`styles/sales-slide.md`](styles/sales-slide.md)
     （型・流れ・図解は [`docs/sales-deck-blueprint.md`](docs/sales-deck-blueprint.md)）
   - YouTube サムネ → [`styles/youtube-thumb.md`](styles/youtube-thumb.md)
   - SNS 投稿 → [`styles/sns-post.md`](styles/sns-post.md)

   カラー(HEX)・フォント・構図・NG・植物モチーフをプロンプトに織り込む。
3. **プロンプトを作文する。** 短い指示ではなく、被写体・構図・色(HEX)・質感・
   避けたい要素まで具体的に書く。コピペ用の完成プロンプトは
   [`prompts/`](prompts/README.md)（営業/YouTube/SNS別）にある。
4. **スクリプトを実行する**(下記)。
5. **結果を確認し、必要なら編集で詰める。** 一発で決まらない場合は、出力画像を
   `edit` の入力にして差分修正を重ねる。

## コマンド

スクリプト: `john_ai/image-gen/scripts/image_gen.py`

### 生成(text → image)

```bash
python john_ai/image-gen/scripts/image_gen.py generate \
  --prompt "（具体的で完結したプロンプト）" \
  --size landscape \
  --quality high \
  --out john_ai/image-gen/out/thumb.png
```

### 編集(image[+mask] → image)

```bash
python john_ai/image-gen/scripts/image_gen.py edit \
  --image base.png \
  --prompt "（何をどう変えるか。残す要素も明示）" \
  --out john_ai/image-gen/out/edited.png
```

- 複数画像を渡して合成・参照させる場合は `--image a.png b.png`(先頭がベース)。
- 部分編集はマスクを使う: `--mask mask.png`。
  **マスクの透明(alpha=0)部分が編集対象**、不透明部分は保持される。

### 合成(背景 ＋ 人物切り抜き ＋ ロゴ)

`scripts/compose.py`。**出演者(じょん)サムネの既定の作り方**。gpt-image で背景を
作り、本人の実写切り抜きとロゴを重ねる(顔は生成しない)。

```bash
python john_ai/image-gen/scripts/compose.py \
  --bg out/yt-bg.png \
  --fg john_ai/image-gen/assets/people/jon/jon-suit-cutout.png \
  --fg-anchor bottom-right --fg-scale 0.98 \
  --logo john_ai/image-gen/assets/logo/jnhc-horizontal-reverse.png \
  --logo-anchor top-left --logo-scale 0.15 \
  --size 1280x720 --out out/yt-thumb-base.png
```

> **人物(本人)の顔は gpt-image で生成・改変しない。** 実写の切り抜きを合成する。
> 詳細: [`assets/people/jon/README.md`](assets/people/jon/README.md)。

## サイズ・プリセット

| プリセット   | 実サイズ     | 用途の目安                         |
| ------------ | ------------ | ---------------------------------- |
| `square`     | 1024x1024    | アイコン / アバター / SNS 正方形    |
| `landscape`  | 1536x1024    | スライド / YouTube サムネ(16:9寄り)|
| `portrait`   | 1024x1536    | 縦ポスター / ストーリーズ           |
| `auto`       | auto         | モデルに任せる                      |

`--size 1024x1024` のように実寸を直接指定してもよい。

## 主なオプション

- `--quality` : `low|medium|high|auto`(既定 `high`)
- `--n`       : 生成枚数(複数時は `-1, -2 ...` を付けて保存)
- `--format`  : `png|jpeg|webp`(透過は `png`/`webp`)
- `--background transparent` : 透過背景(generate のみ、png/webp 推奨)
- `--out`     : 出力先。未指定なら `out/<gen|edit>-<timestamp>.<fmt>`

## 用途別のコツ

- **YouTube サムネ**: `--size landscape`。視認性最優先。被写体は中央〜やや寄せ、
  文字は短く特大。背景と文字のコントラストを強く指示する。
- **研修 / セールススライド**: `--size landscape`。情報過多を避け、1スライド1メッセージ。
  余白・図解中心。トンマナ(色/フォント)を `styles/` から必ず反映。
- **アイコン / ロゴ調**: `--size square` + `--background transparent`。

## 重要な運用ルール（JNHC）

- **文字は画像に焼き込まない。** gpt-image は日本語・数字を正確に描けない。
  背景・図像・装飾だけを生成し、コピー/数値/表は編集ソフト・コードで後乗せする。
  → 営業スライドを「まるごと gpt-image で出す」のは禁止（破綻する）。
- **ロゴは再生成しない。** [`assets/logo/`](assets/logo/README.md) の公式PNGを合成する。
- **色は HEX を明記。** ブランド色は `styles/jnhc-brand.md` の表に従う。
- 右下の植物モチーフ＋左上の淡い光は JNHC のシグネチャー。共通装飾として敷く。

## 注意

- gpt-image はレスポンスを base64 で返す(URL は返らない)。スクリプトが
  自動でデコードして保存する。
- 生成物は `out/`(gitignore 済み)に出る。必要なものだけ正規の場所へ移す。
- 著作権・肖像権・商標に触れる依頼は避ける。実在人物のなりすまし生成はしない。
  赤十字は医療記号として使わない（国際赤十字の商標）。

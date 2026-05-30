# JNHC ブランド トンマナ（マスター）

一般社団法人 全国訪問看護経営研究協会（**JNHC** / 事業ブランド **JNHC-MRA**）の
画像制作で常に守る基準。各チャネル用プリセット（`sales-slide.md` /
`youtube-thumb.md` / `sns-post.md`）はこのファイルを継承し、差分だけを定義する。

> ブランドの約束（タグライン）: **「人と組織の可能性を、訪問看護の未来へ。」**
> 性格: 誠実 / 信頼 / 専門的 / 前向き。医療・経営の堅さ × 人の温かさ。
> 「煽らない説得」。数字と設計で語る。チャラさ・過度な装飾・ストックフォト感はNG。

---

## 1. カラーパレット

実資料から抽出した正規パレット。`#` 値はプロンプトに明記して色ブレを防ぐ。

| 役割 | 名称 | HEX | 用途 |
| ---- | ---- | --- | ---- |
| Ink | ネイビー | `#13294B` | 大見出し・本文・基準色 |
| Primary | JNHC ブルー | `#10408F` | 構造・図解の主役・帯 |
| Accent | アクセントブルー | `#2E7DD1` | 強調語・「攻める」側・CTA |
| Brand Dark | ティールグリーン | `#2E4A47` | ロゴ地・ダーク面・締めの帯 |
| Sage | セージ（植物） | `#9DBFA8` | 植物モチーフ・余白の彩り |
| Mist | パウダーブルー | `#CFE6E8` | 植物モチーフのにじみ・背景 |
| Surface | カードブルー | `#EAF2FB` | カード/ボックス地 |
| Line | ライン | `#D0E0F0` | 罫線・区切り |
| Paper | ホワイト | `#FFFFFF` | 基本背景 |
| Black | ブラック | `#1A1A1A` | モノロゴ・極限のコントラスト |

配色比率の目安: **白70% / ブルー系20% / 植物・締め色10%**。
広い面は白。ブルーは構造とアクセントに絞る。1画面で主役の強調色は1つ。

---

## 2. シグネチャー（必ず入れるブランド装置）

この3点が JNHC らしさの正体。新規画像にも踏襲する。

1. **植物モチーフ**: 半透明の水彩タッチで、ユーカリ/オリーブ風の細い枝葉を
   **右下コーナー**に低彩度・低不透明度（15〜30%）で配置。色はセージ `#9DBFA8`
   とパウダーブルー `#CFE6E8` のにじみ。やり過ぎない。お守り程度。
2. **ブルーの光のグラデーション**: **左上**から淡いブルーの波/光が差すような
   ごく薄いグラデーション。清潔感と「ひらける未来」の含意。
3. **余白と整列**: 情報を詰めない。グリッドに正確に整列。角丸は小さめ（8〜12px）。
   medical らしい清潔・端正さ。

---

## 3. タイポグラフィ

- 和文: **游ゴシック / Yu Gothic（太め）**。代替: Noto Sans JP, Hiragino Kaku Gothic。
- 欧文・数字: 同系のヒューマニストサンセリフ（Yu Gothic / Inter 系）。
- 「JNHC」ロゴタイプはセリフ（明朝/ローマン）で、ブランドの格を担う要素。
- 見出しは大きく短く。**キーワードだけ `#2E7DD1` で色変え**して視線誘導。
- 数字は特大で主役にする（例: 「**3ヶ月**」「約**260万円**」）。

> ⚠️ gpt-image は日本語テキストを正確に描けない。**文字は画像に焼き込まず**、
> 背景・図像だけ生成して、テキストは編集ソフト/コードのオーバーレイで載せる。
> 詳細は各チャネルプリセットの「テキストの扱い」を参照。

---

## 4. ロゴ

公式ロゴ素材は `assets/logo/`（命名規則はそこの README 参照）。**改変・再生成しない**。
gpt-image で“それっぽいロゴ”を作らない。必ず公式ファイルを後乗せ合成する。

ロゴの構成: 六角形の中に十字（医療＋訪問のシールド）＝シンボル ＋ 「JNHC」＋
「一般社団法人 全国訪問看護経営研究協会」。

| 背景 | 使うロゴ |
| ---- | -------- |
| 白・淡色 | モノ（ブラック/ネイビー）版 |
| ティールグリーン `#2E4A47`・ダーク面・写真上 | 白の反転版 |

最小余白: シンボル高さの 1/2 を四辺に確保。十字シンボル単体はアイコン/ファビコン用途のみ。

---

## 5. ビジュアルの作法（被写体・トーン）

- 人物を出すなら: 訪問看護の現場（在宅・地域）/ 管理者・スタッフ。
  明るく自然光、清潔、誠実な表情。過度な笑顔の作り込み・営業臭はNG。
- イラストを使うなら: **フラットで端正なライン＋面**の図解アイコン。
  ネイビー＋ブルーのダクトーン。線は均一、装飾過多にしない。
- 写真を使うなら: 明るく軽い、青みのある自然光。彩度は控えめ。
- 禁則: 赤十字（国際赤十字の商標）を医療記号として使わない。煽り表現の赤、
  炎・札束などの過激な金儲け表現、ホラー/不安を過度に煽る画。

---

## 6. プロンプトに毎回差し込むブランド句（コピー用）

英語プロンプト末尾に付けるブランド・スタイル節（テキストは焼き込まない前提）:

```
STYLE: clean, calm, trustworthy Japanese corporate healthcare brand. Generous
white space, precise grid alignment, soft small-radius rounded cards. Palette
strictly: deep navy #13294B, brand blue #10408F, accent blue #2E7DD1, sage
green #9DBFA8, powder blue #CFE6E8, white #FFFFFF. Signature: faint translucent
watercolor botanical sprig (eucalyptus/olive leaves, low opacity) in the
BOTTOM-RIGHT corner, and a very soft blue light gradient from the TOP-LEFT.
Flat, tidy duotone line-and-fill illustration style. Medical-grade tidy and
professional, warm but understated. No text, no lettering, no logos, no red
cross symbol, no garish colors, no stock-photo cheesiness.
```

> 文字を一切入れたくないときは `no text, no lettering, no captions, no UI` を必ず付ける。

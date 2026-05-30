# SNS 運用スタイル（Instagram / X / Facebook）

> 継承元: [`jnhc-brand.md`](./jnhc-brand.md) ／ プロンプト全文: [`../prompts/sns.md`](../prompts/sns.md)

JNHC-MRA の SNS 投稿画像の作法。「世界一の SNS 運用チーム」の結論を仕様化。
主戦場は **Instagram（カルーセル教育投稿）** と **X（図解1枚 / 告知）**。

---

## 0. 大前提 — 文字は焼き込まない

SNS の教育投稿は文字量が多い。gpt-image に日本語を描かせると破綻するので、
**テンプレ枠とテキストはデザインツール/コードで作り、gpt-image は背景・装飾・
スポットイラストだけ**を担当する。表紙の主役コピーも後乗せ。

---

## 1. フォーマットとサイズ

| 用途 | 比率 | 生成プリセット |
| ---- | ---- | -------------- |
| Instagram フィード/カルーセル | 4:5（1080×1350） | `--size portrait`→4:5トリミング |
| Instagram 正方形 | 1:1（1080×1080） | `--size square` |
| Instagram ストーリーズ/リール表紙 | 9:16（1080×1920） | `--size portrait` |
| X 横長カード | 16:9（1200×675） | `--size landscape` |

## 2. 投稿の型

1. **カルーセル教育**（保存される投稿）: 表紙＝強い問い/結論、2枚目以降＝
   ステップ図解（番号カード）、最終枚＝まとめ＋CTA（フォロー/プロフへ）。
   `docs/sales-deck-blueprint.md` の図解6型がそのまま使える。
2. **1枚図解**: 比較表 / Before→After / チェックリストを1枚に。Xで伸びる。
3. **名言・キーメッセージ**: 余白×植物モチーフ×短文。ブランド想起用。
4. **告知**（セミナー/動画/資料DL）: 日時・申込をはっきり、CTA明確に。

## 3. デザイン規律（フィードの統一感）

- グリッドで世界観を統一: 同じ枠・同じ余白・同じ植物モチーフ位置。
- 1投稿1メッセージ。文字は大きく少なく。キーワードのみ `#2E7DD1`。
- 白基調＋ブルー＋植物。彩度は上げすぎない（医療の信頼感）。
- ロゴは小さく端に。`assets/logo/` の公式PNGを合成。

## 4. 背景/装飾の生成プロンプト（文字なし）

代表例（全文は `prompts/sns.md`）:

```
A clean Instagram carousel background (4:5, vertical) for a Japanese home-visit
nursing management brand. Mostly white with a soft pale-blue light gradient
from the top, and a delicate translucent watercolor botanical sprig
(eucalyptus/olive leaves) in muted sage #9DBFA8 and powder blue #CFE6E8 in the
bottom-right corner, low opacity. Calm, trustworthy, lots of empty space in the
center for text to be added later. No text, no lettering, no logo, no people.
Palette: white, navy #13294B, blue #2E7DD1.
```

```
A flat tidy duotone spot illustration for a healthcare management SNS post:
[テーマ例: 採用面接 / 訪問看護師がタブレットで記録 / 地域ネットワーク]. Navy
#13294B and blue #2E7DD1 with sage accents, generous white space, calm and
professional flat line-and-fill style, centered with margin. No text, no logo.
4:5 vertical.
```

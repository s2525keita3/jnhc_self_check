# プロンプト・ライブラリ

JNHC 用の gpt-image プロンプト集。**意図(日本語) → 実プロンプト(英語)** の形で、
コピペしてすぐ使える。チャネル別:

- [`sales.md`](./sales.md) — 営業資料の背景・章扉・概念図・植物モチーフ
- [`youtube.md`](./youtube.md) — サムネ背景・被写体
- [`sns.md`](./sns.md) — SNS 投稿の背景・スポットイラスト

## 共通ルール（必読）

1. **文字は焼き込まない。** どのプロンプトも `no text, no lettering, no logo` を含む。
   日本語コピー・数字・ロゴは編集ソフト/コードで後乗せする。
2. **色は HEX を明記。** ブランド色: navy `#13294B` / blue `#10408F` /
   accent `#2E7DD1` / teal `#2E4A47` / sage `#9DBFA8` / powder blue `#CFE6E8`。
3. **末尾に必ずブランド・スタイル節**（`styles/jnhc-brand.md` §6）を付ける。
4. 一発で決まらなければ、出力を `edit` の入力にして差分修正（被写体の位置・余白・
   色の強さ）を重ねる。「左を空けて」「もっと余白」「植物を薄く」等を言語化。

## 実行例

```bash
# 背景生成
python ../scripts/image_gen.py generate \
  --prompt "<下のプロンプト>" --size landscape --quality high \
  --out out/sales-cover-bg.png

# 透過の被写体だけ
python ../scripts/image_gen.py generate \
  --prompt "<人物/図像のプロンプト>" --background transparent --format png \
  --size portrait --out out/subject.png

# 既存画像を編集（余白を足す・色を寄せる・要素を消す）
python ../scripts/image_gen.py edit \
  --image out/sales-cover-bg.png \
  --prompt "Make the bottom-right botanical sprig fainter; add more empty white space on the left half." \
  --out out/sales-cover-bg-v2.png
```

# YouTube 運用スタイル（サムネイル）

> 継承元: [`jnhc-brand.md`](./jnhc-brand.md) ／ プロンプト全文: [`../prompts/youtube.md`](../prompts/youtube.md)

訪問看護の経営者・管理者・看護師に向けた、JNHC-MRA の YouTube サムネ作法。
「世界一の YouTube 運用チーム」の結論を仕様に落としたもの。

---

## 0. 大前提 — 文字は焼き込まない

gpt-image は日本語の大見出しを正確に描けない。サムネの命は**短く強い日本語**
なので、運用はこう分ける:

1. **gpt-image**: 背景・人物・図像（被写体）だけを生成。`no text` を明記。
2. **文字（特大コピー）**: 編集ソフト（Canva/Figma/Photoshop/Pillow）で後乗せ。
3. これにより「狙った訴求文 × 崩れない日本語 × 高い CTR」を両立。

---

## 1. サムネの設計（CTR を取る型）

- サイズ: **1280×720（16:9）**。生成は `--size landscape`（1536×1024）→ 16:9にトリミング。
- **要素は3つまで**: ①特大コピー（13文字以内目安）②被写体（人物 or 図像）③ロゴ小。
- **コントラスト最優先**: 背景と文字は明暗をはっきり。文字は白 or ネイビーに
  太い縁取り/ベタ帯。スマホの小さい表示で1秒で読めること。
- **視線**: 人物は視線をコピー側 or レンズへ。表情は「真剣 / 安心 / 発見」。
- **色**: ブランド3色を基調にしつつ、サムネは**彩度を一段上げて**目立たせてよい
  （ただしティール/ブルーの範囲内。原色の赤や毒々しい色は使わない）。
- **数字を主役に**: 「3ヶ月」「260万円」「採用5名」等はサムネでも特大が効く。

## 2. サムネの型（使い回し）

1. **人物アップ＋左右コピー**: 経営者/看護師の上半身、片側にコピー帯。王道・高CTR。
2. **Before→After**: 画面2分割。左=暗い現状／右=明るい理想。矢印。
3. **数字ドン**: 中央に特大数字＋一言。図解アイコンを背景に薄く。
4. **図解レク系**: 「採用の設計図」など、ホワイトボード/図解を背景にした解説回。

## 3. 背景生成プロンプト（被写体だけ・文字なし）

代表例（全文は `prompts/youtube.md`）:

```
A high-contrast YouTube thumbnail BACKGROUND (16:9) for a Japanese home-visit
nursing management channel. A confident, friendly Japanese nurse-manager in
clean scrubs on the RIGHT third, soft natural light, looking toward the
left. The LEFT two-thirds is a clean, slightly punchy gradient of brand blue
#10408F to teal-green #2E4A47 with a faint hexagon and botanical motif, leaving
clear empty space for large text to be added later. Crisp, modern, trustworthy.
No text, no lettering, no logo, no watermark. Leave the left area uncluttered.
```

> 透過の被写体だけ欲しいときは `--background transparent --format png` で人物/図像を
> 単体生成し、背景は別レイヤーで合成すると編集が楽。

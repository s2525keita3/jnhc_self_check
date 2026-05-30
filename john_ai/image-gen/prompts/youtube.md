# YouTube サムネ プロンプト集（背景・被写体／文字なし）

特大コピーは後乗せ。ここでは背景・被写体だけを生成。`--size landscape`→16:9。
コントラスト重視・左右どちらかに必ずコピー用の空きを作る。

〔BRAND〕は `prompts/sales.md` 冒頭のブランド節と同じ。サムネは彩度を一段上げてOK
（ただしティール/ブルー域内、原色赤は禁止）。

---

## 1. 人物アップ＋コピー空き（王道・高CTR）
```
A high-contrast YouTube thumbnail BACKGROUND (16:9) for a Japanese home-visit
nursing management channel. A confident, friendly Japanese nurse-manager in
clean scrubs placed on the RIGHT third, soft natural light, looking toward the
left. The LEFT two-thirds is a punchy clean gradient from brand blue #10408F to
teal-green #2E4A47 with a faint hexagon + botanical motif, kept empty and
uncluttered for large text later. Crisp, modern, trustworthy. No text, no logo,
no watermark.
```

## 2. Before→After 2分割
```
A 16:9 YouTube thumbnail BACKGROUND split into two halves: LEFT half dim and
desaturated (a tired, struggling office mood), RIGHT half bright and hopeful in
brand blue #2E7DD1 and white (an organized, successful mood), a subtle arrow
implied between them. Keep both halves with empty space for short text. Clean,
high contrast. No text, no logo.
```

## 3. 数字ドン（中央特大数字用の余白）
```
A bold 16:9 YouTube thumbnail BACKGROUND with a strong central empty area for a
huge number to be placed later, surrounded by faint flat duotone icons of
recruiting / nursing / growth charts, on a clean gradient of navy #13294B and
blue #10408F with sage accents. High contrast, modern, uncluttered center. No
text, no numbers, no logo.
```

## 4. 図解レク系（解説回）
```
A 16:9 YouTube thumbnail BACKGROUND evoking a clean whiteboard / blueprint of a
recruiting system: faint flat duotone diagram of connected boxes and arrows in
navy #13294B and blue #2E7DD1 on near-white, a soft botanical sprig bottom-
right, wide empty space on the left for a big title. Tidy, smart, trustworthy.
No text, no logo.
```

## 5. 透過の被写体だけ（合成用）
意図: 人物 or 図像を単体で抜き、背景は別レイヤーで合成。
```
A confident friendly Japanese nurse-manager in clean scrubs, upper body, soft
natural light, sincere expression looking slightly to the side, isolated on a
fully transparent background. Crisp edges, no shadow on background. No text, no
logo.
```
> 実行: `--background transparent --format png --size portrait`

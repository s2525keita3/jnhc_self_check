# 営業資料プロンプト集（背景・装飾・概念図）

文字・数値・表・図解アイコンは編集ソフトで作る。ここで生成するのは
**背景 / 章扉 / 植物モチーフ / 概念イメージ**のみ。すべて `no text`。
`--size landscape`（16:9）、`--quality high` 基準。

末尾共通（ブランド節・略記 = 〔BRAND〕）:
```
STYLE: clean calm trustworthy Japanese healthcare corporate brand, generous
white space, precise alignment, small-radius rounded shapes, palette strictly
navy #13294B / blue #10408F / accent blue #2E7DD1 / teal-green #2E4A47 / sage
#9DBFA8 / powder blue #CFE6E8 / white. Signature faint translucent watercolor
botanical sprig bottom-right + soft blue light gradient top-left. Flat tidy
duotone. No text, no lettering, no logo, no red cross symbol, no cheesy stock
look.
```

---

## 1. 表紙の背景（明・余白多め）
意図: タイトルと監修者を後で置く、清潔で余白の多い表紙。
```
A clean airy corporate cover background, mostly white, with a very soft pale-
blue light gradient sweeping from the top-left and a delicate translucent
watercolor botanical sprig (eucalyptus/olive leaves) low-opacity in the bottom-
right corner. Keep the center-left wide open and empty for a headline and a
presenter card to be placed later. 16:9. 〔BRAND〕
```

## 2. 章扉 / 締め帯（ダーク・ティール）
意図: セクション区切り、締めの結論帯のダーク背景。
```
A calm dark section-divider background in deep teal-green #2E4A47 with a subtle
vignette, a barely-visible geometric hexagon line motif, and a low-opacity
sage/powder-blue botanical sprig in the bottom-right. Wide empty space for a
large title later. 16:9. 〔BRAND〕
```

## 3. 全スライド共通の装飾レイヤー（透過PNG）
意図: 左上の光＋右下の植物だけを透過で書き出し、全ページに敷く。
```
Transparent PNG decorative overlay only: a soft pale-blue light glow in the
top-left corner and a delicate translucent watercolor botanical sprig
(eucalyptus/olive leaves, sage #9DBFA8 + powder blue #CFE6E8, low opacity) in
the bottom-right corner. The entire center is fully transparent and empty.
16:9. 〔BRAND〕
```
> 実行: `--background transparent --format png`

## 4. 概念イメージ — Before（くすんだ現状）
```
A muted flat editorial illustration representing struggling, luck-based hiring
in home-visit nursing: scattered disconnected elements, a flat downward feeling,
desaturated navy and grey with a hint of cold blue, plenty of empty space.
Subtle, not gloomy. 16:9. 〔BRAND〕
```

## 5. 概念イメージ — After（明るい理想）
```
A bright hopeful flat editorial illustration of a well-designed proactive
recruiting system in home-visit nursing: tidy connected nodes, a gentle upward
trend, calm professional nurses, clean duotone navy #13294B and blue #2E7DD1
with sage accents, generous white space, flat tidy line-and-fill style. 16:9.
〔BRAND〕
```

## 6. 実績ページの背景（信頼・実直）
```
A quiet professional background for a results/testimonials slide: mostly white,
a faint blue baseline gradient at the bottom, a low-opacity botanical sprig
bottom-right. Calm and credible, wide empty space for cards and big numbers.
16:9. 〔BRAND〕
```

## 7. 現場の写真調イメージ（人物・在宅看護）
意図: 表紙や章扉に敷く、温かく清潔な訪問看護の現場。
```
A bright, warm, natural-light photographic-style image of a Japanese home-visit
nurse in clean uniform gently supporting an elderly patient at home, soft blue-
toned daylight, low saturation, tidy and reassuring, shallow depth of field,
plenty of clean empty space on one side for text later. Documentary, sincere,
not staged or salesy. 16:9. No text, no logo.
```

# セールス特化スタイル（営業資料スライド）

> 継承元: [`jnhc-brand.md`](./jnhc-brand.md) ／ 型の全体像: [`../docs/sales-deck-blueprint.md`](../docs/sales-deck-blueprint.md)

JNHC-MRA の営業資料（例: 「訪問看護 採用の教科書 3ヶ月マスタープログラム」）の
作法。実資料の型・流れ・図解をそのまま再現できるようにする。

---

## 0. 最重要原則 — gpt-image の使いどころ

営業スライドは**情報密度が高く、正確な日本語と図解**が命。これは gpt-image の
苦手領域（日本語が崩れ、数字がデタラメになる）。だから役割を分ける:

| 要素 | 作り方 |
| ---- | ------ |
| 文字・数値・表・KPI・箇条書き | **編集ソフト/HTML/コードで作る**（gpt-image 禁止） |
| 図解アイコン（線＋面のダクトーン） | ベクター素材 or 既存アイコンセット推奨。gpt-imageは補助 |
| 表紙・章扉の背景ビジュアル | **gpt-image で生成** |
| 右下の植物モチーフ / 左上の光 | **gpt-image で生成**（透過PNG）して全スライド共通で敷く |
| Before/After 等の概念イメージ | gpt-image で“雰囲気”を作り、文字は後乗せ |
| 人物・現場の写真調イメージ | gpt-image で生成 or 権利クリアなフォト |

→ **「スライドまるごとを gpt-image で出す」のは禁止。** 背景・装飾・概念図だけを
生成し、テキストレイヤーは別で重ねる。これが破綻しない唯一の運用。

---

## 1. レイアウトの型（実資料準拠）

全スライド共通の枠:

- **ヘッダー左上**: JNHC ロゴ（モノ）＋ 事業名「JNHC-MRA」。
- **ヘッダー右上**: タグライン「人と組織の可能性を、訪問看護の未来へ。」（小さく薄く）。
- **左上 or 上部**: 章ラベル（例: `Chapter 07` / `スライド 3`）。
- **見出し**: 大きな和文。キーワードだけ `#2E7DD1`。直下に1行サブ。
- **本文エリア**: カード/表/タイムライン/Before→After のいずれか（下記「図解の型」）。
- **フッター帯（締め）**: 角丸の塗り帯（白 or ネイビー or ティール）＋丸アイコン＋
  そのスライドの結論を1文。例: 『待った結果が今』なら、設計を変えるしかない。
- 右下に植物モチーフ、左上に淡い光。ページ番号。

スライド比率: **16:9**（実寸 1672×941 相当。生成は `--size landscape` = 1536×1024、
最終はスライド枠に合わせてトリミング/配置）。

---

## 2. 図解の型（このパターンを使い回す）

実資料で確認できた“勝ちパターン”。新規スライドもこの語彙で組む。

1. **番号付きカード横並び（1〜5）**: 課題列挙・特徴列挙。丸番号バッジ＋アイコン＋
   見出し＋短文。例: 「こんな課題はありませんか？」。
2. **2軸比較表**: 「待つ採用 vs 攻める採用」。左に項目、右2列で対比。
   ネガ側はグレー、ポジ側はブルー。
3. **3カラム・タイムライン**: 「1ヶ月目 → 2ヶ月目 → 3ヶ月目」。各列に
   トピック／アウトプットを縦に。矢印で前進を示す。
4. **Before / After（矢印遷移）**: 左=現状（くすみ）／右=理想（ブルー）。
   行ごとに → で対応づけ。締めに一文。
5. **数値ハイライト**: 投資対効果・実績。特大数字＋単位＋小さな注。
   例: 約120万円 / 約260万円 / 33万円。
6. **アイコングリッド（10点など）**: 付属ツール一覧。2行×5列の整列。

色の使い分け: 現状/ネガ=グレー〜ネイビー低彩度、理想/ポジ=`#2E7DD1`、
締め帯=ネイビー or ティール `#2E4A47`。

---

## 3. テキストの扱い（焼き込み禁止の運用）

1. gpt-image には**背景と図像だけ**を作らせる（`no text` を明記）。
2. 文字は PowerPoint / Keynote / Figma / HTML+CSS / Pillow 等で**後乗せ**。
3. フォントは游ゴシック太め、見出しのキーワードのみ `#2E7DD1`。
4. ロゴは `assets/logo/` の公式PNGを合成（再生成しない）。

---

## 4. すぐ使える生成プロンプト（背景・装飾・概念図）

いずれも文字なし。`--size landscape`、`--quality high`。具体は
[`../prompts/sales.md`](../prompts/sales.md) に全文。代表例:

**表紙の背景**
```
A clean, airy corporate cover background for a Japanese healthcare/management
brand. Mostly white. A very soft pale-blue light gradient sweeping from the
top-left. In the bottom-right corner, a delicate translucent watercolor
botanical sprig (eucalyptus/olive leaves) in muted sage green #9DBFA8 and
powder blue #CFE6E8, low opacity. Calm, trustworthy, lots of empty space in the
center-left for a headline to be placed later. No text, no logo, no people.
Palette: white, navy #13294B, blue #10408F. 16:9.
```

**章扉 / 締め帯用のダーク背景**
```
A calm dark section-divider background in deep teal-green #2E4A47, subtle
darker vignette, a faint geometric hexagon line motif barely visible, and a
low-opacity sage/powder-blue botanical sprig in the bottom-right corner. Lots
of empty space for a large title later. No text, no logo. 16:9.
```

**概念イメージ（Before/After の After 側など）**
```
A bright, hopeful flat editorial illustration representing a well-designed,
proactive recruiting system in home-visit nursing: tidy connected nodes,
upward trend, calm professional nurses, clean duotone of navy #13294B and blue
#2E7DD1 with sage accents, generous white space, flat tidy line-and-fill style.
No text, no numbers, no logo. 16:9.
```

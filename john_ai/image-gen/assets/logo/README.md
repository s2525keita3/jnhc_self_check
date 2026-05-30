# 公式ロゴ素材

JNHC（一般社団法人 全国訪問看護経営研究協会）の公式ロゴはここに置く。
**ロゴは gpt-image で再生成しない。** 生成した背景に、ここの公式PNGを後乗せ合成する。

> ⚠️ チャットに貼られたロゴ画像はファイルとして保存できなかったため、
> 下記の名前で**この `assets/logo/` フォルダに手動でドロップ**してください。
> 揃えば各プロンプト/プリセットがそのまま参照できます。

## 命名規則（推奨）

| ファイル名 | 内容 | 使う場面 |
| ---------- | ---- | -------- |
| `jnhc-vertical-mono.png` | 縦組み・モノ（黒/ネイビー）。シンボル＋JNHC＋協会名 | 白・淡色背景、表紙 |
| `jnhc-vertical-reverse.png` | 縦組み・白抜き（反転） | ティール/ダーク/写真上 |
| `jnhc-horizontal-mono.png` | 横組み・モノ | ヘッダー、フッター |
| `jnhc-horizontal-reverse.png` | 横組み・白抜き | ダーク帯、サムネ |
| `jnhc-mark-mono.png` | 六角＋十字シンボルのみ・モノ | アイコン/ファビコン/SNSアイコン |
| `jnhc-mark-reverse.png` | シンボルのみ・白抜き | ダーク面の小ロゴ |

- 形式: **透過PNG**（推奨）。可能なら `jnhc-logo.svg` も置くと拡大に強い。
- 余白（アイソレーション）: シンボル高さの 1/2 を四辺に確保して配置。
- 背景に応じてモノ/反転を選ぶ（`../styles/jnhc-brand.md` §4）。

## 合成のしかた（例）

```bash
# 生成した背景の右下にロゴを小さく合成（Pillow）
python - <<'PY'
from PIL import Image
bg = Image.open("out/sales-cover-bg.png").convert("RGBA")
logo = Image.open("assets/logo/jnhc-vertical-mono.png").convert("RGBA")
w = bg.width // 6
logo = logo.resize((w, int(w*logo.height/logo.width)))
bg.alpha_composite(logo, (40, 40))   # 左上に配置
bg.convert("RGB").save("out/sales-cover-final.png")
PY
```

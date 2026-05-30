# john_ai

Codex などのエージェントに使わせる前提のスキル置き場。
ブランドは **JNHC / JNHC-MRA**（一般社団法人 全国訪問看護経営研究協会）。

## skills

### [`image-gen/`](./image-gen/SKILL.md) — gpt-image による画像の生成・編集

営業資料・YouTube サムネ・SNS 投稿などの画像を、エージェントが意図を汲んで
ブランド準拠で作るためのスキル。

```
image-gen/
├── SKILL.md                      # エージェント向けの使い方（入口）
├── scripts/
│   ├── image_gen.py              # gpt-image CLI（generate / edit）
│   └── compose.py                # 背景＋人物切り抜き＋ロゴの合成
├── styles/
│   ├── jnhc-brand.md             # ★マスターのトンマナ（配色・フォント・ロゴ・植物モチーフ）
│   ├── sales-slide.md            # セールス特化
│   ├── youtube-thumb.md          # YouTube 運用
│   └── sns-post.md               # SNS 運用
├── docs/sales-deck-blueprint.md  # 営業資料の型・流れ（8ブロック）
├── prompts/                      # コピペ用プロンプト集（営業/YouTube/SNS）
└── assets/
    ├── logo/                     # 公式ロゴ素材（手動ドロップ）
    └── people/jon/               # 出演者 じょん の写真素材（手動ドロップ）
```

**鉄則**:
- 文字・数字・表は焼き込まず編集ソフトで後乗せ。gpt-image は背景・装飾・概念図のみ。
- **出演者(じょん)の顔は gpt-image で生成しない。** 実写を切り抜き、ブランド背景に
  `compose.py` で合成する。
- ロゴは公式PNGを合成（再生成しない）。色は HEX 厳守。

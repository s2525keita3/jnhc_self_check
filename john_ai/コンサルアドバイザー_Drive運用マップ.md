# コンサルアドバイザー — Googleドライブ運用マップ

このシステムの**実データはGoogleドライブ**にあります（このリポジトリは設計図と人格定義の保管庫）。
アドバイザーは「コンサルアドバイザーを起動してください」で立ち上がり、毎回ドライブを読み→会話→末尾でドライブに追記します。
**保存するたびにログ（行）が増え、次回の文脈が濃くなる＝成長する**仕組みです。

---

## 全体像

```
あなた（チャット）
   │  「コンサルアドバイザーを起動して」
   ▼
consult_advisor_SKILL（＝アドバイザーの脳／人格・手順）
   │  起動時に読む                 末尾で書く
   ▼                                  ▲
Googleドライブ「コンサルアドバイザー/」（＝記憶の倉庫）
   ├ 各クライアントフォルダ
   │   ├ ○○_プロフィール（背景・変わりにくい情報／Doc）
   │   └ ○○_コンサルログ（議事録・課題・PDCAを時系列で追記／Sheet）
   └ _ナレッジベース（全社横断の知見／Sheet）→ SNS・協会・起業塾・商品へ二次活用
```

---

## ドライブのファイルID一覧（保守用）

親フォルダ「コンサルアドバイザー」: `18N0F8sU6cLnLqkUWWqchi1gUUbqJjBzU`

| 区分 | 名前 | 種類 | ID |
|---|---|---|---|
| 脳 | consult_advisor_SKILL（最新・これを使う） | Doc | `1jaMdPv05_JQRLIYsAS_C-9oaTx_uFWvJfAgkn6k2yOc` |
| Re:Size | フォルダ | Folder | `1LuiKmv5xcJXRocpCco7iS0jG8_R8sr7a` |
| Re:Size | Re_Size_プロフィール | Doc | `1m7iKSMWVZqoHdXUkoQbkPbtoor8McpPvqJ1AAO1pcsg` |
| Re:Size | Re_Size_コンサルログ | Sheet | `1wNxPCE4_PZZfRtVePYlcLPLCy3NYG0-UQLOUIVz3vKY` |
| COM | フォルダ | Folder | `174HLJAXG4HrArCy-tya4driKa9nPcXKI` |
| COM | COM_プロフィール | Doc | `1z6n7xrgzjRGcE75joMDoYMqo2YTFB5JzXfMh23usdo8` |
| COM | COM_コンサルログ | Sheet | `1M6Fk2Y_snDDW4U5YM-1d1oMgNB8GdCYRhqoy2OaQLj4` |
| Tisser | フォルダ | Folder | `1YaGv3eUE1n4hrC3EARIR7iZCPBAc6ZHA` |
| Tisser | Tisser_プロフィール | Doc | `1SKuf6H7PlwISUXzUSnUfao3WSFqgBYkTr7LwsD1W3jQ` |
| Tisser | Tisser_コンサルログ | Sheet | `1NTpu6qxaSTIZjZYATnFRJrIEGOxCKLN2y_mrLLyRzB0` |
| 横断 | _ナレッジベース（フォルダ） | Folder | `137RSkxWJrIC-rXirAhLB4Y47_Je_NFPI` |
| 横断 | コンサル_ナレッジベース（全社横断） | Sheet | `1ENLM-w9Hxnyd9JViprZQjd0LyBGUqyONGX8fsaVIc2A` |

---

## コンサルログ（Sheet）の列構成

`日付 / 種別 / タイトル / 内容(要点) / 決定事項 / ToDo(担当・期限) / ステータス / クライアントの生の声 / ナレッジ候補・メモ`

- **種別**＝ 議事録 / 課題 / PDCA / 更新 を使い分け、1ファイルで全部を時系列管理。
- 上書きせず**追記**していく（履歴が学習資産になる）。

## ナレッジベース（Sheet）の列構成

`ID / 種別 / タイトル / いつ使う(When) / やり方・内容(How) / なぜ効く・教訓(Why) / タグ / 元ネタ(社名・日付) / 転用候補 / ステータス`

- 種別略号：KH=ノウハウ, QA=QA, FL=失敗点・教訓, FW=フレームワーク, MN=マニュアル
- **転用候補**に SNS / 協会 / 起業塾 / 商品 を書いておき、二次活用時に拾う。

---

## 新しいクライアントを追加する手順

1. ドライブ「コンサルアドバイザー/」に `<社名>` フォルダを作る。
2. その中に `<社名>_プロフィール`（Doc. 背景）と `<社名>_コンサルログ`（Sheet. 上の列構成）を作る。
3. `consult_advisor_SKILL` の A-1/A-2 の表に1行追加（フォルダID・2ファイルのID）。
4. 以後、起動時に自動で読まれ、末尾で追記される。

---

## 使い方（ふだんの1回）

1. チャットで **「コンサルアドバイザーを起動してください」** と打つ。
2. 「今日はどのクライアント？」に答える（例：Tisser）。
3. アドバイザーが現状サマリー＋オープン課題を提示 → 相談・分析する。
4. 終わりに「今日の内容をログに追記して」と言えば、コンサルログに新しい行が足される＝記憶・成長。

> ⚠️ 旧版で誤って残った可能性のあるファイル（マイドライブ直下の `consult_advisor_SKILL_v1.md` と中身が途中までの `Untitled`、各クライアントフォルダの `Re_Size_コンサル台帳`(.xlsx) など）は、混乱を避けるため手動削除推奨。**正は上の表のIDのものだけ**。

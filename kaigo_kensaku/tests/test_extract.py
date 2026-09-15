"""抽出エンジンの単体テスト（ネットワーク不要）。"""
import os
import sys
import unittest

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

from src.config import load_fields  # noqa: E402
from src.extract import build_row, harvest_html, missing_columns, norm_label  # noqa: E402


def load_sample():
    p = os.path.join(BASE, "tests", "fixtures", "sample_detail.html")
    with open(p, encoding="utf-8") as f:
        return f.read()


class TestHarvest(unittest.TestCase):
    def setUp(self):
        self.h = harvest_html(load_sample())

    def test_kv_basic(self):
        self.assertEqual(self.h.kv[norm_label("所在地")], "〒662-0073\u3000西宮市松風町1-3")
        self.assertEqual(self.h.kv[norm_label("連絡先")], "Tel：0798-31-1255／Fax：0798-31-1266")
        self.assertEqual(self.h.kv[norm_label("通常の事業の実施地域")], "西宮市・芦屋市")

    def test_noise_removed(self):
        self.assertNotIn("地図を開く", self.h.kv[norm_label("所在地")])
        self.assertNotIn("ホームページを開く", self.h.kv[norm_label("連絡先")])

    def test_matrix_staff(self):
        self.assertEqual(self.h.matrix[(norm_label("介護支援専門員"), norm_label("常勤"))], "4人")
        self.assertEqual(self.h.matrix[(norm_label("介護支援専門員"), norm_label("非常勤"))], "0人")

    def test_matrix_users(self):
        self.assertEqual(self.h.matrix[(norm_label("要介護２"), norm_label("人数"))], "19")

    def test_th_td_pairs(self):
        self.assertEqual(self.h.kv[norm_label("管理者の氏名")], "森田\u3000愛")


class TestBuildRow(unittest.TestCase):
    def setUp(self):
        self.fields = load_fields(BASE, "fields_kyotaku.csv")
        h = harvest_html(load_sample())
        ctx = {
            "city": "西宮市",
            "service": "居宅介護支援",
            "name": "スマートケア",
            "pref": "兵庫県",
            "jigyosyo_cd": "2871234567-00",
            "url": "https://example.invalid/detail",
        }
        self.row = build_row(self.fields, h, ctx, normalize=True)

    def test_context_columns(self):
        self.assertEqual(self.row["市区町村"], "西宮市")
        self.assertEqual(self.row["サービス種別"], "居宅介護支援")
        self.assertEqual(self.row["事業所名"], "スマートケア")
        self.assertEqual(self.row["事業所番号"], "2871234567-00")

    def test_address_normalized(self):
        # 〒を除去し、都道府県名を付与（旧ツールの出力形式に合わせる）
        self.assertEqual(self.row["所在地"], "兵庫県西宮市松風町1-3")

    def test_date_normalized(self):
        self.assertEqual(self.row["事業開始年月日"], "2014/10/01")

    def test_hours(self):
        self.assertEqual(self.row["平日"], "8時30分～17時30分")
        self.assertEqual(self.row["土曜"], "9時00分～12時00分")
        # 「時分～時分」は空欄化
        self.assertEqual(self.row["日曜"], "")
        self.assertEqual(self.row["祝日"], "")
        self.assertEqual(self.row["定休日"], "土・日、年始年末")

    def test_staff_counts_are_int(self):
        self.assertEqual(self.row["常勤"], 4)
        self.assertEqual(self.row["非常勤"], 0)

    def test_user_counts(self):
        self.assertEqual(
            [self.row[k] for k in ["要支援１", "要支援２", "要介護１", "要介護２", "要介護３", "要介護４", "要介護５"]],
            [0, 0, 11, 19, 5, 9, 3],
        )

    def test_manager(self):
        self.assertEqual(self.row["氏名"], "森田　愛")

    def test_kasan(self):
        self.assertEqual(self.row["（Ⅰ）"], "なし")
        self.assertEqual(self.row["（Ⅱ）"], "あり")
        self.assertEqual(self.row["（Ⅲ）"], "なし")
        self.assertEqual(self.row["（Ａ）"], "なし")

    def test_no_missing_columns(self):
        # 値0や空欄が正の列は除いて、取りこぼしが無いこと
        allowed_empty = {"要支援１", "要支援２", "日曜", "祝日", "非常勤"}
        self.assertEqual(set(missing_columns(self.row, self.fields)) - allowed_empty, set())


class TestTransforms(unittest.TestCase):
    def test_date_wareki(self):
        from src.extract import _to_date

        self.assertEqual(_to_date("令和5年11月1日"), "2023/11/01")
        self.assertEqual(_to_date("2023/11/1"), "2023/11/01")

    def test_int_with_unit(self):
        from src.extract import _to_int

        self.assertEqual(_to_int("４人"), 4)
        self.assertEqual(_to_int("－"), "")

    def test_yesno(self):
        from src.extract import _yesno

        self.assertEqual(_yesno("あり "), "あり")
        self.assertEqual(_yesno("○"), "あり")



class TestClosedHours(unittest.TestCase):
    """実データにあった「休み」の表し方をすべて空欄にできること。"""

    def test_closed_patterns(self):
        from src.extract import apply_transform

        for v in ("－", "-", "時分～時分", "0：00～0：00", "0：～0：", "0:00～0:00", ""):
            self.assertEqual(apply_transform(v, "time", {}, True), "", f"{v!r} が空欄にならない")

    def test_open_hours_kept(self):
        from src.extract import apply_transform

        for v in ("9：00～17：00", "8時30分～17時30分", "0:00～24:00"):
            self.assertEqual(apply_transform(v, "time", {}, True), v)


class TestRegexLookup(unittest.TestCase):
    """特定事業所加算の見出しゆれを正規表現で拾えること（取り違えないこと）。"""

    def _harvest(self, labels):
        from src.extract import Harvest, norm_label

        h = Harvest()
        for k, v in labels.items():
            h.kv[norm_label(k)] = v
        return h

    def test_roman_numerals_are_not_confused(self):
        from src.extract import lookup_value

        h = self._harvest({
            "特定事業所加算（Ⅰ）": "なし",
            "特定事業所加算（Ⅱ）": "あり",
            "特定事業所加算（Ⅲ）": "なし",
            "特定事業所加算（Ａ）": "なし",
        })
        self.assertEqual(lookup_value(r"re:特定事業所加算\(?I\)?$", h, {}), "なし")
        self.assertEqual(lookup_value(r"re:特定事業所加算\(?II\)?$", h, {}), "あり")
        self.assertEqual(lookup_value(r"re:特定事業所加算\(?III\)?$", h, {}), "なし")
        self.assertEqual(lookup_value(r"re:特定事業所加算\(?A\)?$", h, {}), "なし")

    def test_variants(self):
        from src.extract import lookup_value

        for label in ("特定事業所加算Ⅱ", "特定事業所加算(Ⅱ)", "介護予防特定事業所加算（Ⅱ）"):
            h = self._harvest({label: "あり"})
            self.assertEqual(
                lookup_value(r"re:特定事業所加算\(?II\)?$", h, {}), "あり", label
            )
            self.assertIsNone(lookup_value(r"re:特定事業所加算\(?I\)?$", h, {}), label)


class TestNamePriority(unittest.TestCase):
    """検索結果の事業所名を、詳細ページのフリガナより優先すること。"""

    def test_heading_wins_over_furigana(self):
        from src.config import load_fields
        from src.extract import Harvest, build_row, norm_label

        fields = load_fields(BASE, "fields_kyotaku.csv")
        h = Harvest()
        h.kv[norm_label("事業所の名称")] = "けあらぼ"
        row = build_row(fields, h, {"heading": "ケアラボ", "name": ""}, normalize=True)
        self.assertEqual(row["事業所名"], "ケアラボ")

class TestYesNoRejectsProse(unittest.TestCase):
    """あり／なしの列に、事業所のPR文のような長文を入れないこと。

    見出しの探索を緩くしている都合で無関係な文章を拾うことがある。
    それを「あり／なし」の列にそのまま出すと、空欄よりも悪い誤りになる
    （実際に特定事業所加算の4列にPR文が入る不具合が起きた）。
    """

    def test_prose_becomes_blank(self):
        from src.extract import apply_transform

        prose = ("利用者様の在宅生活継続のため、個別性を大切にし地域に根差した"
                 "事業所として２４時間連絡体制を整えています。")
        self.assertEqual(apply_transform(prose, "yesno", {}, True), "")

    def test_known_wordings(self):
        from src.extract import apply_transform

        for v, want in [("あり", "あり"), ("なし", "なし"), ("○", "あり"), ("×", "なし"),
                        ("算定している", "あり"), ("算定していない", "なし"),
                        ("有", "あり"), ("無", "なし"), ("", "")]:
            self.assertEqual(apply_transform(v, "yesno", {}, True), want, v)

    def test_numbers_are_not_treated_as_yes_no(self):
        """数値をあり／なしに読み替えないこと。

        実サイトの「前年同月の提供実績」欄に入っていたのは「10人」という
        利用者数だった。これを「1件以上＝あり」と読み替えると、
        4区分すべてが「あり」になる誤りが出る。
        """
        from src.extract import apply_transform

        for v in ("10人", "10件", "3", "0", "1", "1,204"):
            self.assertEqual(apply_transform(v, "yesno", {}, True), "", v)

    def test_regex_lookup_does_not_grab_long_value(self):
        from src.extract import Harvest, lookup_value, norm_label

        h = Harvest()
        h.matrix[(norm_label("特定事業所加算（Ⅱ）"), norm_label("取組内容"))] = (
            "当事業所は利用者様の在宅生活を支えるため、24時間の連絡体制を確保しています。")
        self.assertIsNone(lookup_value(r"re:特定事業所加算\(?II\)?$", h, {}),
                          "長文を加算の値として拾っている")
        h.matrix[(norm_label("特定事業所加算（Ⅱ）"), norm_label("算定状況"))] = "あり"
        self.assertEqual(lookup_value(r"re:特定事業所加算\(?II\)?$", h, {}), "あり")


class TestFoundButUnusable(unittest.TestCase):
    """「見出しは見つかったが値として使えない」列を検知できること。

    特定事業所加算の列に事業所のPR文が入っていたとき、found だけを見て
    いたため「取得できている」と扱われ、要確認列として報告されなかった。
    結果、原因を突き止める手掛かり（見つかった見出しの一覧）も
    出力されなかった。
    """

    def _row(self, value):
        from src.config import load_fields
        from src.extract import Harvest, build_row, norm_label

        fields = load_fields(BASE, "fields_kyotaku.csv")
        h = Harvest()
        h.kv[norm_label("特定事業所加算（Ⅰ）")] = value
        found, rejected = set(), set()
        row = build_row(fields, h, {"city": "西宮市", "pref": "兵庫県", "heading": "A"},
                        True, found, rejected)
        return row, found, rejected

    def test_prose_is_reported_as_unusable(self):
        row, found, rejected = self._row(
            "当事業所は24時間連絡体制を確保し、利用者様に寄り添います。")
        self.assertEqual(row["（Ⅰ）"], "")
        self.assertIn("（Ⅰ）", found, "見出し自体は見つかっている")
        self.assertIn("（Ⅰ）", rejected, "値として使えなかったことが記録されていない")

    def test_valid_value_is_not_reported(self):
        row, found, rejected = self._row("あり")
        self.assertEqual(row["（Ⅰ）"], "あり")
        self.assertNotIn("（Ⅰ）", rejected)


class TestConfigEncoding(unittest.TestCase):
    """設定ファイルをExcelで保存(CP932)されても読めること。

    項目定義CSVは「利用者が現地で直せる」ことを狙って外出ししている。
    ところが Excel で開いて保存すると CP932 になる。utf-8 固定で読んで
    いると、そこでツールが起動できなくなり、外出しした意味が消える。
    """

    def test_reads_cp932_definition_file(self):
        import shutil
        import tempfile

        from src.config import load_fields

        work = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, work, True)
        os.makedirs(os.path.join(work, "config"))
        src = os.path.join(BASE, "config", "fields_kyotaku.csv")
        with open(src, encoding="utf-8-sig") as f:
            text = f.read()
        # Excel で保存した状態を再現する
        dst = os.path.join(work, "config", "fields_kyotaku.csv")
        with open(dst, "w", encoding="cp932", errors="replace") as f:
            f.write(text)

        fields = load_fields(work, "fields_kyotaku.csv")
        self.assertEqual([f.column for f in fields][:3],
                         ["市区町村", "サービス種別", "事業所名"])

    def test_reads_utf8_definition_file(self):
        from src.config import load_fields

        fields = load_fields(BASE, "fields_kyotaku.csv")
        self.assertIn("（Ⅰ）", [f.column for f in fields])


if __name__ == "__main__":
    unittest.main(verbosity=2)

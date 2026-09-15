"""実サイト（兵庫県／西宮市／居宅介護支援）の検索結果HTMLに対する検証。

tests/fixtures/real_result_list.html は、実際の検索結果ページから
事業所2件ぶんを抜き出したもの。作り物ではないので、ここが通れば
検索結果ページからの読み取りは実物で動く。
"""
import os
import sys
import unittest

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

from src.config import load_services  # noqa: E402
from src.extract import build_row, harvest_pages, listing_rows  # noqa: E402


def load():
    p = os.path.join(BASE, "tests", "fixtures", "real_result_list.html")
    with open(p, encoding="utf-8") as f:
        return f.read()


class TestRealResultList(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = listing_rows(load())
        cls.fields = load_services(BASE)["居宅介護支援"].fields

    def row_for(self, cd):
        h, heading = harvest_pages([self.rows[cd]])
        ctx = {
            "city": "西宮市", "service": "居宅介護支援", "pref": "兵庫県",
            "name": "情報を選択して概要を見る", "heading": heading,
            "jigyosyo_cd": cd, "url": "https://example.invalid/",
        }
        return build_row(self.fields, h, ctx, normalize=True)

    def test_split_into_one_block_per_office(self):
        self.assertEqual(len(self.rows), 2)
        self.assertIn("2870903032-00", self.rows)
        self.assertIn("2870900897-00", self.rows)

    def test_first_office(self):
        r = self.row_for("2870903032-00")
        self.assertEqual(r["事業所名"], "ケアラボ")
        self.assertEqual(r["所在地"], "兵庫県西宮市生瀬町2丁目２番７号")
        self.assertEqual(r["連絡先"], "0797-20-5637")
        self.assertEqual(r["サービス提供地域"], "西宮市北部・宝塚市・神戸市北区")
        self.assertEqual(r["平日"], "9：00～17：00")
        self.assertEqual(r["祝日"], "9：00～17：00")
        self.assertEqual(r["土曜"], "")      # 「－」は空欄にする
        self.assertEqual(r["日曜"], "")
        self.assertEqual(r["定休日"], "土日、年末年始")
        self.assertEqual(r["市区町村"], "西宮市")

    def test_second_office_address_without_city(self):
        r = self.row_for("2870900897-00")
        self.assertEqual(r["事業所名"], "ミドリライフサービス株式会社")
        # サイト側の住所に市名が無い（〒663-8247 津門稲荷町5-13…）
        self.assertEqual(r["所在地"], "兵庫県西宮市津門稲荷町5-13サンシャイン西宮201")
        self.assertEqual(r["土曜"], "9：00～17：00")
        self.assertEqual(r["サービス提供地域"], "西宮市")

    def test_columns_available_from_result_list(self):
        """検索結果ページだけで埋まる列（詳細ページを開かなくても取れる分）。"""
        r = self.row_for("2870903032-00")
        filled = [k for k, v in r.items() if v not in (None, "")]
        for col in ["市区町村", "サービス種別", "事業所名", "所在地", "連絡先",
                    "サービス提供地域", "平日", "祝日", "定休日", "事業所番号"]:
            self.assertIn(col, filled, f"{col} が検索結果ページから取れていない")


class TestRealKasanTable(unittest.TestCase):
    """実サイトの「介護報酬の加算状況」から、あり／なしを読めること。

    あり／なしは文字ではなく画像で表示されている。
      <td><img alt="あり" src="ico_jigyosho_ari.gif"></td>
    文字だけを拾うと空になり、見出しのゆれを吸収する探索が隣の
    「(その内容)」欄のPR文を拾ってしまう（実際にこの不具合を出した）。
    """

    def setUp(self):
        from src.extract import harvest_html

        p = os.path.join(BASE, "tests", "fixtures", "real_kasan_table.html")
        with open(p, encoding="utf-8") as f:
            self.h = harvest_html(f.read())

    def test_reads_yes_no_from_image_alt(self):
        from src.extract import norm_label

        got = {n: self.h.kv.get(norm_label(f"特定事業所加算（{n}）"))
               for n in ("Ⅰ", "Ⅱ", "Ⅲ", "Ａ")}
        self.assertEqual(got, {"Ⅰ": "あり", "Ⅱ": "なし", "Ⅲ": "なし", "Ａ": "なし"})

    def test_row_uses_the_right_values(self):
        from src.config import load_services
        from src.extract import build_row

        fields = load_services(BASE)["居宅介護支援"].fields
        row = build_row(fields, self.h,
                        {"city": "西宮市", "pref": "兵庫県", "heading": "ケアラボ"},
                        normalize=True)
        self.assertEqual(row["（Ⅰ）"], "あり")
        self.assertEqual(row["（Ⅱ）"], "なし")
        self.assertEqual(row["（Ⅲ）"], "なし")
        self.assertEqual(row["（Ａ）"], "なし")


if __name__ == "__main__":
    unittest.main(verbosity=2)

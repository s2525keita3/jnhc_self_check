"""模擬サイトに対して、実際のブラウザで検索→一覧→詳細→抽出まで通す結合テスト。

Chrome(Chromium) と chromedriver が無い環境では自動でスキップする。
"""
import os
import sys
import unittest

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
sys.path.insert(0, os.path.join(BASE, "tests"))

from mocksite import MockSite, cd_of, name_of  # noqa: E402

from src.config import load_services  # noqa: E402
from src.extract import Harvest, build_row, harvest_html  # noqa: E402


def browser_available() -> bool:
    drv = os.environ.get("KAIGO_CHROMEDRIVER")
    if drv and not os.path.exists(drv):
        return False
    try:
        from selenium import webdriver  # noqa: F401
    except ImportError:
        return False
    return True


@unittest.skipUnless(browser_available(), "Chrome/chromedriver が無いためスキップ")
class MockFlowMixin:
    variant = "checkbox"

    site = None

    def run_flow(self, city, service_name, expect):
        from src.navigator import Navigator

        services = load_services(BASE)
        sd = services[service_name]
        with MockSite(self.variant) as site:
            self.site = site
            nav = Navigator(
                pref="兵庫県", pref_code="28", display=False, wait=0,
                retry=2, base_url=site.base_url,
            )
            try:
                nav.search(city, sd.site_label, exact=False)
                listings = nav.collect_listings()
                self.assertEqual(len(listings), expect, f"一覧の件数({self.variant})")
                rows = []
                for lst in listings:
                    h = Harvest()
                    for html in nav.detail_pages(lst):
                        h.merge(harvest_html(html))
                    ctx = {
                        "city": city, "service": service_name, "pref": "兵庫県",
                        "name": lst.name, "jigyosyo_cd": lst.jigyosyo_cd, "url": lst.url,
                    }
                    rows.append(build_row(sd.fields, h, ctx, normalize=True))
                return rows
            finally:
                nav.close()


class TestCheckboxVariant(MockFlowMixin, unittest.TestCase):
    variant = "checkbox"

    def test_kyotaku_with_pagination(self):
        rows = self.run_flow("西宮市", "居宅介護支援", 12)   # 10件+2件＝ページ送りを含む
        self.assertEqual(rows[0]["事業所名"], name_of("西宮市", "居宅介護支援", 1))
        self.assertEqual(rows[0]["市区町村"], "西宮市")
        self.assertEqual(rows[0]["所在地"], "兵庫県西宮市松風町1-1")
        self.assertEqual(rows[0]["連絡先"], "Tel：0798-31-1001／Fax：0798-31-2001")
        self.assertEqual(rows[0]["事業開始年月日"], "2011/10/01")
        self.assertEqual(rows[0]["平日"], "8時30分～17時30分")
        self.assertEqual(rows[0]["土曜"], "9時00分～12時00分")
        self.assertEqual(rows[0]["日曜"], "")
        self.assertEqual(rows[0]["定休日"], "土・日、年始年末")
        self.assertEqual(rows[0]["常勤"], 2)
        self.assertEqual(rows[0]["非常勤"], 1)
        self.assertEqual(rows[0]["要介護２"], 19)
        self.assertEqual(rows[0]["氏名"], "森田　愛1")
        self.assertEqual(rows[0]["（Ⅱ）"], "あり")
        self.assertEqual(rows[0]["（Ⅰ）"], "なし")
        self.assertEqual(rows[0]["事業所番号"], cd_of("西宮市", "居宅介護支援", 1))
        self.assertTrue(rows[0]["詳細URL"].startswith("http"))

    def test_houkan(self):
        rows = self.run_flow("芦屋市", "訪問看護", 3)
        self.assertEqual(rows[0]["サービス種別"], "訪問看護")
        self.assertEqual(rows[0]["看護師_常勤"], 3)
        self.assertEqual(rows[0]["看護師_非常勤"], 3)
        self.assertEqual(rows[0]["保健師_常勤"], 1)
        self.assertEqual(rows[0]["緊急時訪問看護加算"], "あり")
        self.assertEqual(rows[0]["サービス提供体制強化加算"], "なし")

    def test_ward_name(self):
        rows = self.run_flow("神戸市中央区", "居宅介護支援", 3)
        self.assertEqual(rows[0]["市区町村"], "神戸市中央区")


class TestLinkVariant(MockFlowMixin, unittest.TestCase):
    variant = "link"

    def test_kyotaku(self):
        rows = self.run_flow("西宮市", "居宅介護支援", 12)
        self.assertEqual(rows[0]["市区町村"], "西宮市")
        self.assertEqual(rows[-1]["事業所名"], name_of("西宮市", "居宅介護支援", 12))


class TestSelectVariant(MockFlowMixin, unittest.TestCase):
    variant = "select"

    def test_kyotaku(self):
        rows = self.run_flow("西宮市", "居宅介護支援", 12)
        self.assertEqual(rows[0]["市区町村"], "西宮市")
        self.assertEqual(rows[0]["常勤"], 2)


class TestDeepVariant(MockFlowMixin, unittest.TestCase):
    """トップから2階層たどらないと市区町村に届かない構成でも動くこと。"""

    variant = "deep"

    def test_kyotaku(self):
        rows = self.run_flow("西宮市", "居宅介護支援", 12)
        self.assertEqual(rows[0]["市区町村"], "西宮市")


class TestDeadNextVariant(MockFlowMixin, unittest.TestCase):
    """「次へ」を押しても同じページに戻る構成で、無限ループにならないこと。"""

    variant = "deadnext"

    def test_stops_without_hanging(self):
        rows = self.run_flow("西宮市", "居宅介護支援", 10)   # 1ページ分で打ち切る
        self.assertEqual(rows[0]["市区町村"], "西宮市")


class TestTextboxVariant(MockFlowMixin, unittest.TestCase):
    """市区町村を文字で入力させる構成でも動くこと。"""

    variant = "textbox"

    def test_kyotaku(self):
        rows = self.run_flow("西宮市", "居宅介護支援", 12)
        self.assertEqual(rows[0]["市区町村"], "西宮市")


class TestTextOnlyVariant(MockFlowMixin, unittest.TestCase):
    """サービス種別を選ぶ部品が無くても、市区町村の入力を壊さないこと。"""

    variant = "textonly"

    def test_city_not_overwritten_by_service(self):
        rows = self.run_flow("西宮市", "居宅介護支援", 12)
        self.assertEqual({r["市区町村"] for r in rows}, {"西宮市"})
        self.assertTrue(all("西宮市" in r["事業所名"] for r in rows))


class TestRealFlowVariant(MockFlowMixin, unittest.TestCase):
    """実サイトの導線（サービス選択 → 所在地選択）を再現した構成。"""

    variant = "real"

    def test_kyotaku(self):
        rows = self.run_flow("西宮市", "居宅介護支援", 12)
        self.assertEqual(rows[0]["市区町村"], "西宮市")
        self.assertEqual(rows[0]["常勤"], 2)
        self.assertEqual(rows[0]["（Ⅱ）"], "あり")
        self.assertEqual(self.site.pdf_hits, 0, "PDFを開いてしまっている")

    def test_houkan(self):
        rows = self.run_flow("芦屋市", "訪問看護", 3)
        self.assertEqual(rows[0]["サービス種別"], "訪問看護")
        self.assertEqual(rows[0]["緊急時訪問看護加算"], "あり")

    def test_ward(self):
        rows = self.run_flow("神戸市中央区", "居宅介護支援", 3)
        self.assertEqual(rows[0]["市区町村"], "神戸市中央区")


class TestIframeVariant(MockFlowMixin, unittest.TestCase):
    """検索フォームが iframe の中にあっても動くこと。"""

    variant = "iframe"

    def test_kyotaku(self):
        rows = self.run_flow("西宮市", "居宅介護支援", 12)
        self.assertEqual(rows[0]["市区町村"], "西宮市")
        self.assertEqual(rows[0]["常勤"], 2)


class TestPdfTrapVariant(MockFlowMixin, unittest.TestCase):
    """PDFや案内ページのリンクをたどらないこと（実サイトで起きた誤追尾）。"""

    variant = "pdftrap"

    def test_does_not_follow_pdf(self):
        rows = self.run_flow("西宮市", "居宅介護支援", 12)
        self.assertEqual(rows[0]["市区町村"], "西宮市")
        self.assertEqual(self.site.pdf_hits, 0, "PDFを開いてしまっている")


@unittest.skipUnless(browser_available(), "Chrome/chromedriver が無いためスキップ")
class TestUnknownCity(unittest.TestCase):
    def test_raises_clear_error(self):
        from src.navigator import Navigator, SiteError

        with MockSite("checkbox") as site:
            nav = Navigator("兵庫県", "28", False, 0, 1, base_url=site.base_url)
            try:
                with self.assertRaises(SiteError) as cm:
                    nav.search("存在しない市", "居宅介護支援")
            finally:
                nav.close()
        self.assertIn("存在しない市", str(cm.exception))
        self.assertIn("診断する.bat", str(cm.exception))


@unittest.skipUnless(browser_available(), "Chrome/chromedriver が無いためスキップ")
class TestCityListing(unittest.TestCase):
    def test_list_cities_all_variants(self):
        from src.navigator import Navigator

        for variant in ("checkbox", "link", "select", "real", "iframe", "deep"):
            with MockSite(variant) as site:
                nav = Navigator("兵庫県", "28", False, 0, 2, base_url=site.base_url)
                try:
                    cities = nav.list_cities("居宅介護支援")
                finally:
                    nav.close()
            self.assertIn("西宮市", cities, f"{variant} で市区町村一覧が取れない")
            self.assertIn("神戸市中央区", cities, f"{variant} で区名が取れない")


if __name__ == "__main__":
    unittest.main(verbosity=2)

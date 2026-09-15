"""画面版（gui.py）を実際に起動し、実行から出力までを通す検証。

tkinter が無い環境では自動でスキップする。
（Linuxでは python3-tk が必要。Windows の Python には最初から入っている）
"""
import os
import shutil
import sys
import tempfile
import time
import unittest

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
sys.path.insert(0, os.path.join(BASE, "tests"))


def gui_available():
    try:
        import tkinter  # noqa: F401
        import customtkinter  # noqa: F401
    except ImportError:
        return False
    return bool(os.environ.get("DISPLAY"))


@unittest.skipUnless(gui_available(), "tkinter/customtkinter/画面が無いためスキップ")
class TestGuiRun(unittest.TestCase):
    def setUp(self):
        from mocksite import MockSite

        self.work = tempfile.mkdtemp()
        shutil.copytree(os.path.join(BASE, "config"), os.path.join(self.work, "config"))
        shutil.copy2(os.path.join(BASE, "settings.ini"), self.work)
        cache = os.path.join(self.work, "config", "cities_cache")
        os.makedirs(cache, exist_ok=True)
        with open(os.path.join(cache, "28.json"), "w", encoding="utf-8") as f:
            f.write('["西宮市", "芦屋市", "神戸市中央区"]')

        self.site = MockSite("real")
        self.site.__enter__()
        os.environ["KAIGO_BASE_URL"] = self.site.base_url

        import gui
        self.gui = gui
        gui.BASE_DIR = self.work
        gui.CACHE_DIR = cache
        self.app = gui.App()

    def tearDown(self):
        try:
            self.app._on_close()
        except Exception:
            pass
        self.site.__exit__(None, None, None)
        os.environ.pop("KAIGO_BASE_URL", None)
        shutil.rmtree(self.work, ignore_errors=True)

    def pump(self, seconds):
        end = time.time() + seconds
        while time.time() < end:
            self.app.update()
            time.sleep(0.05)

    def wait_until(self, cond, timeout):
        end = time.time() + timeout
        while time.time() < end:
            self.app.update()
            if cond():
                return True
            time.sleep(0.1)
        return False

    def test_screen_is_built(self):
        self.assertEqual(len(self.app.city_vars), 3)
        self.assertEqual(set(self.app.svc_vars), {"居宅介護支援", "訪問看護"})
        self.assertEqual(self.app.run_btn.cget("state"), "normal")
        self.assertEqual(self.app.stop_btn.cget("state"), "disabled")

    def test_select_all_and_clear(self):
        self.app._set_all(True)
        self.assertEqual(len(self.app.selected_cities()), 3)
        self.app._set_all(False)
        self.assertEqual(self.app.selected_cities(), [])

    def test_select_wards_only(self):
        self.app._set_all(False)
        self.app._select_wards()
        self.assertEqual(self.app.selected_cities(), ["神戸市中央区"])

    def test_filter(self):
        self.app._set_all(False)          # 先に全解除してから絞り込む
        self.app.filter_entry.insert(0, "神戸市")
        self.app._render_cities()
        self.app._set_all(True)          # 絞り込み中は表示中のものだけ選ぶ
        self.assertEqual(self.app.selected_cities(), ["神戸市中央区"])

    def test_run_produces_excel(self):
        from openpyxl import load_workbook

        self.app._set_all(False)
        self.app.city_vars["芦屋市"].set(True)
        self.app.svc_vars["訪問看護"].set(False)
        self.app._start()
        self.assertEqual(self.app.run_btn.cget("state"), "disabled")
        self.assertTrue(
            self.wait_until(lambda: self.app.run_btn.cget("state") == "normal", 180),
            "実行が終わらない",
        )
        self.assertTrue(self.app.last_output, "出力ファイルが記録されていない")
        self.assertTrue(os.path.exists(self.app.last_output))
        wb = load_workbook(self.app.last_output)
        self.assertIn("居宅_全件", wb.sheetnames)
        self.assertEqual(wb["居宅_全件"].max_row, 3 + 3)
        self.assertEqual(wb["居宅_全件"].cell(4, 1).value, "芦屋市")
        self.assertGreater(self.app.bar.get(), 0.9)
        self.assertIn("完了しました", self.app.status.cget("text"))

    def test_stop_button(self):
        self.app._set_all(True)
        self.app._start()
        self.pump(6)                      # 走り出してから止める
        self.app._stop()
        self.assertTrue(
            self.wait_until(lambda: self.app.run_btn.cget("state") == "normal", 120),
            "停止できない",
        )
        self.assertIn("停止", self.app.status.cget("text"))


if __name__ == "__main__":
    unittest.main(verbosity=2)

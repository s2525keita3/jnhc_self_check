"""介護事業所情報取得ツール（画面版）。

設定ファイルを開かずに、都道府県とサービスを選び、市区町村を
チェックして実行できる。取得処理そのものは src/runner.py を使う
（コマンドライン版と同じ処理）。
"""
from __future__ import annotations

import json
import os
import queue
import subprocess
import sys
import threading
import time
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(sys.executable)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import customtkinter as ctk  # noqa: E402

from src import config as cfg  # noqa: E402
from src import runner  # noqa: E402
from src.state import AlreadyRunning, Lock, Progress  # noqa: E402

ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")

FONT = "Meiryo UI" if sys.platform.startswith("win") else None
CACHE_DIR = os.path.join(BASE_DIR, "config", "cities_cache")


def font(size=13, bold=False):
    return ctk.CTkFont(family=FONT, size=size, weight="bold" if bold else "normal")


def cached_cities(pref_code: str):
    try:
        with open(os.path.join(CACHE_DIR, f"{pref_code}.json"), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return []


def save_cities(pref_code: str, cities):
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        with open(os.path.join(CACHE_DIR, f"{pref_code}.json"), "w", encoding="utf-8") as f:
            json.dump(cities, f, ensure_ascii=False)
    except OSError:
        pass


def open_in_explorer(path: str):
    try:
        if sys.platform.startswith("win"):
            os.startfile(path)  # noqa: S606
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])
    except Exception:
        pass


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("介護事業所情報取得ツール")
        self.geometry("1020x720")
        self.minsize(900, 640)

        self.settings = cfg.load_settings(BASE_DIR)
        self.prefs = cfg.load_prefectures(BASE_DIR)
        self.services = cfg.load_services(BASE_DIR)

        self.events: queue.Queue = queue.Queue()
        self.worker: threading.Thread | None = None
        self.stop_flag = threading.Event()
        self.city_vars: dict = {}
        self._alive = True
        self.last_output = ""
        self.started_at = 0.0

        self._build()
        self.log("市区町村とサービスを選んで「実行」を押してください")
        self.log("途中で止めても、次回は続きから取得します")
        self._load_cities(initial=True)
        self.after(100, self._pump)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ------------------------------------------------------------ 画面作り
    def _build(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=3)   # 市区町村
        self.grid_rowconfigure(4, weight=2)   # ログ

        top = ctk.CTkFrame(self)
        top.grid(row=0, column=0, sticky="ew", padx=14, pady=(14, 8))
        top.grid_columnconfigure(3, weight=1)

        ctk.CTkLabel(top, text="都道府県", font=font(12)).grid(
            row=0, column=0, padx=(14, 6), pady=(12, 10), sticky="w")
        self.pref_box = ctk.CTkComboBox(
            top, values=list(self.prefs), width=140, font=font(14),
            command=lambda _v: self._load_cities(), state="readonly")
        self.pref_box.set(self.settings.pref if self.settings.pref in self.prefs else "兵庫県")
        self.pref_box.grid(row=0, column=1, pady=(12, 10), sticky="w")

        ctk.CTkLabel(top, text="サービス", font=font(12)).grid(
            row=0, column=2, padx=(24, 6), pady=(12, 10), sticky="w")
        svc_box = ctk.CTkFrame(top, fg_color="transparent")
        svc_box.grid(row=0, column=3, pady=(12, 10), sticky="w")
        wanted = [s.strip() for s in self.settings.services_raw.replace("、", ",").split(",")]
        if len(wanted) <= 1:
            wanted = list(self.services)      # 初回は全サービスを選んでおく
        self.svc_vars = {}
        for i, name in enumerate(self.services):
            v = ctk.BooleanVar(value=name in wanted)
            ctk.CTkCheckBox(svc_box, text=name, variable=v, font=font(13)).grid(
                row=0, column=i, padx=(0, 16))
            self.svc_vars[name] = v

        self.reload_btn = ctk.CTkButton(
            top, text="市区町村を取り直す", width=150, font=font(12),
            fg_color="transparent", text_color=("gray20", "gray90"),
            border_width=1, border_color="gray60", hover_color="gray90",
            command=lambda: self._load_cities(force=True))
        self.reload_btn.grid(row=0, column=4, padx=14, pady=(12, 10))

        # ---- 市区町村
        mid = ctk.CTkFrame(self)
        mid.grid(row=1, column=0, sticky="nsew", padx=14, pady=4)
        mid.grid_columnconfigure(0, weight=1)
        mid.grid_rowconfigure(1, weight=1)

        bar = ctk.CTkFrame(mid, fg_color="transparent")
        bar.grid(row=0, column=0, sticky="ew", padx=12, pady=(10, 4))
        bar.grid_columnconfigure(5, weight=1)
        ctk.CTkLabel(bar, text="市区町村", font=font(13, True)).grid(row=0, column=0, padx=(0, 12))
        ctk.CTkButton(bar, text="すべて選択", width=92, font=font(12),
                      command=lambda: self._set_all(True)).grid(row=0, column=1, padx=3)
        ctk.CTkButton(bar, text="すべて解除", width=92, font=font(12),
                      fg_color="transparent", text_color=("gray20", "gray90"),
                      border_width=1, border_color="gray60", hover_color="gray90",
                      command=lambda: self._set_all(False)).grid(row=0, column=2, padx=3)
        self.ward_btn = ctk.CTkButton(bar, text="政令市の全区", width=110, font=font(12),
                                      fg_color="transparent", text_color=("gray20", "gray90"),
                      border_width=1, border_color="gray60", hover_color="gray90",
                                      command=self._select_wards)
        self.ward_btn.grid(row=0, column=3, padx=3)
        self.filter_entry = ctk.CTkEntry(bar, placeholder_text="絞り込み", width=150, font=font(12))
        self.filter_entry.grid(row=0, column=4, padx=(12, 0))
        self.filter_entry.bind("<KeyRelease>", lambda _e: self._render_cities())
        self.count_label = ctk.CTkLabel(bar, text="0件選択中", font=font(12))
        self.count_label.grid(row=0, column=5, sticky="e")

        self.city_area = ctk.CTkScrollableFrame(mid, height=200)
        self.city_area.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))

        # ---- 実行
        run_bar = ctk.CTkFrame(self, fg_color="transparent")
        run_bar.grid(row=2, column=0, sticky="ew", padx=14, pady=(2, 6))
        run_bar.grid_columnconfigure(2, weight=1)
        self.run_btn = ctk.CTkButton(run_bar, text="実行", width=150, height=40,
                                     font=font(15, True), command=self._start)
        self.run_btn.grid(row=0, column=0, padx=(0, 10))
        self.stop_btn = ctk.CTkButton(run_bar, text="停止", width=110, height=40,
                                      font=font(15), state="disabled",
                                      fg_color="transparent", text_color=("gray20", "gray90"),
                      border_width=1, border_color="gray60", hover_color="gray90",
                                      command=self._stop)
        self.stop_btn.grid(row=0, column=1)
        self.status = ctk.CTkLabel(run_bar, text="待機中", font=font(13), anchor="w")
        self.status.grid(row=0, column=2, sticky="ew", padx=16)

        self.bar = ctk.CTkProgressBar(self, height=14)
        self.bar.grid(row=3, column=0, sticky="ew", padx=14, pady=(2, 8))
        self.bar.set(0)

        # ---- ログ
        self.logbox = ctk.CTkTextbox(self, font=font(12), activate_scrollbars=True)
        self.logbox.grid(row=4, column=0, sticky="nsew", padx=14, pady=(0, 6))
        self.logbox.configure(state="disabled")

        bottom = ctk.CTkFrame(self, fg_color="transparent")
        bottom.grid(row=5, column=0, sticky="ew", padx=14, pady=(0, 14))
        self.open_xlsx = ctk.CTkButton(bottom, text="Excelを開く", width=140, font=font(13),
                                       state="disabled", command=self._open_xlsx)
        self.open_xlsx.grid(row=0, column=0, padx=(0, 8))
        ctk.CTkButton(bottom, text="フォルダを開く", width=140, font=font(13),
                      fg_color="transparent", text_color=("gray20", "gray90"),
                      border_width=1, border_color="gray60", hover_color="gray90",
                      command=lambda: open_in_explorer(BASE_DIR)).grid(row=0, column=1)
        self.hint = ctk.CTkLabel(bottom, text="", font=font(12), text_color="gray40")
        self.hint.grid(row=0, column=2, sticky="w", padx=16)

    # ------------------------------------------------------------ 市区町村
    def _load_cities(self, initial: bool = False, force: bool = False):
        pref = self.pref_box.get()
        code = self.prefs.get(pref, "")
        cities = [] if force else cached_cities(code)
        if cities:
            self._set_cities(cities)
            return
        self._set_cities([])
        self.log(f"{pref} の市区町村一覧を取得しています…（初回のみ・1分ほど）")
        threading.Thread(target=self._fetch_cities, args=(pref, code), daemon=True).start()

    def _fetch_cities(self, pref: str, code: str):
        try:
            s = cfg.load_settings(BASE_DIR)
            s.pref = pref
            nav = runner.make_navigator(s, code)
            try:
                label = next(iter(self.services.values())).site_label
                cities = nav.list_cities(label)
            finally:
                nav.close()
            if cities:
                save_cities(code, cities)
            self.events.put(("cities", cities))
        except Exception as e:  # 画面を落とさない
            self.events.put(("log", f"市区町村の取得に失敗しました: {e}"))
            self.events.put(("cities", []))

    def _set_cities(self, cities):
        self.all_cities = list(cities)
        prev = {c: v.get() for c, v in self.city_vars.items()}
        self.city_vars = {c: ctk.BooleanVar(value=prev.get(c, False)) for c in self.all_cities}
        if cities and not any(v.get() for v in self.city_vars.values()):
            wanted = cfg.resolve_cities(BASE_DIR, self.settings.cities_raw, self.all_cities)
            for c in wanted:
                if c in self.city_vars:
                    self.city_vars[c].set(True)
        self._render_cities()

    def _render_cities(self):
        for w in self.city_area.winfo_children():
            w.destroy()
        word = self.filter_entry.get().strip() if hasattr(self, "filter_entry") else ""
        shown = [c for c in self.all_cities if not word or word in c]
        if not shown:
            ctk.CTkLabel(self.city_area,
                         text="（市区町村を取得中です…）" if not self.all_cities else "（該当なし）",
                         font=font(12), text_color="gray40").grid(row=0, column=0, sticky="w")
        for i, c in enumerate(shown):
            ctk.CTkCheckBox(self.city_area, text=c, variable=self.city_vars[c],
                            font=font(13), command=self._update_count).grid(
                row=i // 4, column=i % 4, sticky="w", padx=6, pady=3)
        self._update_count()

    def _update_count(self):
        n = sum(1 for v in self.city_vars.values() if v.get())
        self.count_label.configure(text=f"{n}件選択中")

    def _set_all(self, value: bool):
        word = self.filter_entry.get().strip()
        for c, v in self.city_vars.items():
            if not word or word in c:
                v.set(value)
        self._update_count()

    def _select_wards(self):
        for c, v in self.city_vars.items():
            if c.endswith("区"):
                v.set(True)
        self._update_count()

    # ------------------------------------------------------------ 実行
    def selected_cities(self):
        return [c for c, v in self.city_vars.items() if v.get()]

    def selected_services(self):
        return {n: sd for n, sd in self.services.items() if self.svc_vars[n].get()}

    def _start(self):
        cities = self.selected_cities()
        services = self.selected_services()
        if not cities:
            self.log("市区町村が選ばれていません")
            return
        if not services:
            self.log("サービスが選ばれていません")
            return
        self.stop_flag.clear()
        self.run_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.open_xlsx.configure(state="disabled")
        self.bar.set(0)
        self.started_at = time.time()
        self.log(f"開始：{len(cities)}自治体 × {len(services)}サービス")
        self.worker = threading.Thread(
            target=self._work, args=(self.pref_box.get(), cities, services), daemon=True)
        self.worker.start()

    def _work(self, pref, cities, services):
        # 別スレッドから画面部品を触ってはいけないため、必要な値は引数で受け取る
        nav = None
        try:
            with Lock(BASE_DIR):
                s = cfg.load_settings(BASE_DIR)
                s.pref = pref
                nav = runner.make_navigator(s, self.prefs[s.pref])
                progress = Progress(os.path.join(s.log_dir, "progress.json"))
                if s.resume:
                    progress.load()
                    if progress.stale:
                        self.events.put(
                            ("log", "※ ツールが更新されているため最初から取得します"))
                rep = runner.collect(
                    nav, s, services, cities, progress,
                    on_log=lambda m: self.events.put(("log", m)),
                    on_progress=lambda *a: self.events.put(("tick", a)),
                    should_stop=self.stop_flag.is_set,
                )
                self.events.put(("done", rep))
                cfg.save_last_input(BASE_DIR, s.pref, ", ".join(cities), s.search_type)
        except AlreadyRunning as e:
            self.events.put(("log", str(e)))
            self.events.put(("done", None))
        except Exception as e:
            self.events.put(("log", f"エラー: {e}"))
            self.events.put(("done", None))
        finally:
            if nav is not None:
                nav.close()

    def _stop(self):
        self.stop_flag.set()
        self.stop_btn.configure(state="disabled")
        self.status.configure(text="停止しています…（今の事業所の取得が終わるまでお待ちください）")

    # ------------------------------------------------------------ 画面更新
    def log(self, msg: str):
        self.logbox.configure(state="normal")
        self.logbox.insert("end", f"{datetime.now():%H:%M:%S}  {msg}\n")
        self.logbox.see("end")
        self.logbox.configure(state="disabled")

    def _pump(self):
        try:
            while True:
                kind, payload = self.events.get_nowait()
                if kind == "log":
                    self.log(payload)
                elif kind == "cities":
                    self._set_cities(payload)
                    if payload:
                        self.log(f"{len(payload)}件の市区町村を読み込みました")
                elif kind == "tick":
                    self._tick(*payload)
                elif kind == "done":
                    self._finish(payload)
        except queue.Empty:
            pass
        if self._alive:
            self.after(120, self._pump)

    def _tick(self, done, total, head, i, n):
        frac = (done + (i / n if n else 0)) / total if total else 0
        self.bar.set(min(max(frac, 0.0), 1.0))
        text = f"{min(done + 1, total)}/{total}  {head}"
        if n:
            text += f"  {i}/{n}件"
        elapsed = time.time() - self.started_at
        # 目安が落ち着くまでは残り時間を出さない
        if 0.01 < frac < 1.0 and elapsed > 8:
            remain = elapsed / frac - elapsed
            if remain > 90:
                text += f"　残り約{round(remain / 60)}分"
            elif remain > 15:
                text += "　まもなく完了"
        self.status.configure(text=text)

    def _finish(self, rep):
        self.run_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")
        if rep is None:
            self.status.configure(text="中断しました")
            return
        self.bar.set(1.0)
        self.last_output = rep.output_path
        self.open_xlsx.configure(state="normal")
        word = "停止しました" if rep.cancelled else "完了しました"
        self.status.configure(text=f"{word}：{rep.total_rows}件")
        self.log(f"{word}：{rep.total_rows}件を出力  {rep.output_path}")
        if rep.errors:
            self.log(f"失敗した検索が {len(rep.errors)} 件あります。再実行すると続きから取得します")
        self.hint.configure(text=os.path.basename(rep.output_path))

    def _open_xlsx(self):
        if self.last_output:
            open_in_explorer(self.last_output)

    def _on_close(self):
        self._alive = False
        self.stop_flag.set()
        self.destroy()


def main():
    App().mainloop()


if __name__ == "__main__":
    main()

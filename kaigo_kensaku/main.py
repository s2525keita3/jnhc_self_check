"""介護事業所情報取得ツール（居宅介護支援 / 訪問看護）。

使い方:
    ダブルクリック、または
    python main.py [--pref 兵庫県] [--cities "神戸市*,西宮市"] [--services "居宅介護支援,訪問看護"]
                   [--no-resume] [--restart] [--list-cities]
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
import traceback

BASE_DIR = os.path.dirname(os.path.abspath(getattr(sys, "_MEIPASS", __file__)))
if getattr(sys, "frozen", False):  # PyInstaller で .exe 化した場合
    BASE_DIR = os.path.dirname(sys.executable)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src import config as cfg  # noqa: E402
from src import runner  # noqa: E402
from src.logging_setup import setup_logging  # noqa: E402
from src.state import AlreadyRunning, Lock, Progress  # noqa: E402

log = logging.getLogger("itakukaigokensaku")


def ask(prompt: str, default: str = "") -> str:
    try:
        v = input(f"{prompt}{f' [{default}]' if default else ''}: ").strip()
    except EOFError:
        return default
    return v or default


def interactive(settings: cfg.Settings, prefs) -> cfg.Settings:
    last = cfg.load_last_input(settings.base_dir)
    if not settings.pref:
        while True:
            p = ask("都道府県", last.get("select_pref", "兵庫県"))
            if p in prefs:
                settings.pref = p
                break
            print(f"  『{p}』は都道府県名として認識できません。例: 兵庫県")
    if not settings.cities_raw:
        print("市区町村（カンマ区切りで複数可 / 神戸市* で全区 / ALL で県内全域）")
        settings.cities_raw = ask("市区町村", last.get("input_cities", "ALL"))
    if not settings.services_raw:
        settings.services_raw = ask("サービス種別", "居宅介護支援, 訪問看護")
    return settings


def diagnose(nav, settings: cfg.Settings, services) -> int:
    """検索画面の作りを調べて logs/診断結果.txt に書き出す。"""
    parts = []
    print("\n検索画面の作りを調べています…\n")

    nav.get(nav.base_url.format(code=nav.pref_code))
    parts.append("=" * 70)
    parts.append("【1】都道府県トップページ")
    parts.append("=" * 70)
    parts.append(nav.describe_page())

    nav.open_search_screen()
    parts.append("\n" + "=" * 70)
    parts.append("【2】検索画面（事業所検索リンクをたどった後）")
    parts.append("=" * 70)
    parts.append(nav.describe_page())

    city = (settings.cities_raw or "").split(",")[0].strip().rstrip("*")
    if city and city.upper() != "ALL":
        kind = nav._pick(city, False)
        parts.append("\n" + "=" * 70)
        parts.append(f"【3】『{city}』を選択した結果: {kind or '見つかりませんでした'}")
        parts.append("=" * 70)
        if kind:
            parts.append(nav.describe_page())

    text = "\n".join(parts)
    out = os.path.join(settings.log_dir, "診断結果.txt")
    os.makedirs(settings.log_dir, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(text)
    print(text[:3000])
    print("\n" + "-" * 62)
    print(f"診断結果を書き出しました:\n  {out}")
    print("このファイルと logs\\html\\ の中身を送ってください。")
    print("-" * 62)
    return 0


def diagnose_detail(nav, settings: cfg.Settings, sd) -> int:
    """詳細ページを1件だけ取得し、HTMLと読み取れた項目を書き出す。"""
    from src.extract import harvest_html, main_heading

    city = (settings.cities_raw or "").split(",")[0].strip().rstrip("*")
    print(f"\n{city} / {sd.service_name} を1件だけ調べます…\n")
    nav.search(city, sd.site_label, exact=(settings.search_type == "exact"))
    listings = nav.collect_listings(max_pages=1)
    if not listings:
        print("検索結果が0件でした。『診断する.bat』を先に実行してください")
        return 2

    lst = listings[0]
    print(f"対象: {lst.name or '(名称不明)'}  {lst.url}\n")
    pages = nav.detail_pages(lst)

    out_html = os.path.join(settings.base_dir, "詳細ページ.html")
    with open(out_html, "w", encoding="utf-8") as f:
        for i, html in enumerate(pages):
            f.write(f"\n<!-- ===== ページ {i + 1} / {len(pages)} ===== -->\n")
            f.write(html)

    lines = [f"取得したページ数: {len(pages)}", f"事業所名(見出し): {main_heading(pages[0])}"]
    lines.append("\n■ 同じ事業所の別ページへのリンク")
    for u in nav._same_jigyosyo_links(lst):
        lines.append("  " + u)
    lines.append("\n■ ページ内のリンク・ボタン（表示文字）")
    lines.append(nav.describe_page())
    for i, html in enumerate(pages):
        h = harvest_html(html)
        lines.append(f"\n■ ページ{i + 1} で読み取れた見出し {len(h.kv)}件")
        lines.append("  " + " / ".join(sorted(h.kv)[:120]))
        lines.append(f"■ ページ{i + 1} の表（行×列）{len(h.matrix)}件")
        lines.append("  " + " / ".join(f"{a}×{b}" for a, b in sorted(h.matrix)[:80]))
    text = "\n".join(lines)

    out_txt = os.path.join(settings.log_dir, "詳細ページ診断.txt")
    os.makedirs(settings.log_dir, exist_ok=True)
    with open(out_txt, "w", encoding="utf-8") as f:
        f.write(text)
    print(text[:2500])
    print("\n" + "-" * 62)
    print(f"次の2つのファイルを送ってください:\n  {out_html}\n  {out_txt}")
    print("-" * 62)
    return 0


def run(settings: cfg.Settings, args) -> int:
    prefs = cfg.load_prefectures(settings.base_dir)
    all_services = cfg.load_services(settings.base_dir)

    settings = interactive(settings, prefs)
    if settings.pref not in prefs:
        print(f"都道府県『{settings.pref}』が config/prefectures.csv にありません")
        return 2

    wanted = [s.strip() for s in settings.services_raw.replace("、", ",").split(",") if s.strip()]
    services = {}
    for name in wanted:
        if name in all_services:
            services[name] = all_services[name]
        else:
            print(f"※ サービス種別『{name}』は config/services.csv に未定義のため無視します")
    if not services:
        print("取得するサービス種別が指定されていません")
        return 2

    if args.diagnose or args.diagnose_detail:
        settings.dump_html = True
    nav = runner.make_navigator(settings, prefs[settings.pref])

    progress = Progress(os.path.join(settings.log_dir, "progress.json"))
    if settings.resume and not args.restart:
        progress.load()
        if progress.stale:
            print("※ ツールが更新されているため、前回の取得データは使わず最初から取得します")
    elif args.restart:
        progress.clear()

    try:
        if args.diagnose:
            return diagnose(nav, settings, list(services.values()))
        if args.diagnose_detail:
            return diagnose_detail(nav, settings, list(services.values())[0])

        print(f"\n{settings.pref} の市区町村一覧を取得しています…")
        first_service = next(iter(services.values()))
        available = nav.list_cities(first_service.site_label)
        if args.list_cities:
            print("\n".join(available))
            return 0
        cities = cfg.resolve_cities(settings.base_dir, settings.cities_raw, available)
        if available:
            unknown = [c for c in cities if c not in available]
            if unknown:
                print(f"※ 検索画面に見つからない市区町村: {', '.join(unknown)}")
            cities = [c for c in cities if c in available] or cities
        if not cities:
            print("対象の市区町村がありません。settings.ini の cities を確認してください")
            return 2

        total = len(cities) * len(services)
        print(f"対象: {len(cities)}自治体 × {len(services)}サービス = {total}件の検索\n")

        def on_tick(done, all_, head, i, n):
            if n:
                print(f"      {i}/{n} 件取得", end="\r", flush=True)

        rep = runner.collect(
            nav, settings, services, cities, progress,
            on_log=print, on_progress=on_tick,
        )
        print(f"\n完了：{rep.total_rows}件を出力しました\n  {rep.output_path}")
        if rep.errors:
            print(f"\n失敗した検索が {len(rep.errors)} 件あります"
                  "（logs/itakukaigokensaku.log を確認してください）")
            print("  再実行すると、失敗した分だけ取得し直します")
        cfg.save_last_input(settings.base_dir, settings.pref, settings.cities_raw, settings.search_type)
        return 0
    finally:
        nav.close()


def main() -> int:
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("--pref")
    ap.add_argument("--cities")
    ap.add_argument("--services")
    ap.add_argument("--no-resume", action="store_true")
    ap.add_argument("--restart", action="store_true", help="前回の進捗を破棄して最初から取得する")
    ap.add_argument("--list-cities", action="store_true", help="対象都道府県の市区町村一覧を表示する")
    ap.add_argument("--diagnose", action="store_true", help="検索画面の作りを調べて logs に書き出す")
    ap.add_argument("--diagnose-detail", action="store_true",
                    help="詳細ページを1件だけ取得して、そのHTMLと中身を書き出す")
    args = ap.parse_args()

    settings = cfg.load_settings(BASE_DIR)
    if args.pref:
        settings.pref = args.pref
    if args.cities:
        settings.cities_raw = args.cities
    if args.services:
        settings.services_raw = args.services
    if args.no_resume:
        settings.resume = False

    setup_logging(BASE_DIR, settings.debug)
    print("=" * 62)
    print(" 介護事業所情報取得ツール（居宅介護支援 / 訪問看護）")
    print("=" * 62)

    try:
        with Lock(BASE_DIR):
            return run(settings, args)
    except AlreadyRunning as e:
        print(f"\n{e}")
        return 1
    except KeyboardInterrupt:
        print("\n中断しました。再実行すると続きから取得します")
        return 130
    except Exception:
        log.error("想定外のエラー\n%s", traceback.format_exc())
        print("\nエラーが発生しました。logs/itakukaigokensaku.log を確認してください")
        print(traceback.format_exc())
        return 1


if __name__ == "__main__":
    code = main()
    if sys.stdout.isatty():
        try:
            input("\nEnterキーで終了します…")
        except EOFError:
            pass
    sys.exit(code)

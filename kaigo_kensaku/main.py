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
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(getattr(sys, "_MEIPASS", __file__)))
if getattr(sys, "frozen", False):  # PyInstaller で .exe 化した場合
    BASE_DIR = os.path.dirname(sys.executable)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src import config as cfg  # noqa: E402
from src.excelout import write_workbook  # noqa: E402
from src.extract import build_row, harvest_html, Harvest  # noqa: E402
from src.state import AlreadyRunning, Lock, Progress  # noqa: E402

log = logging.getLogger("itakukaigokensaku")


def setup_logging(base_dir: str, debug: bool) -> None:
    log_dir = os.path.join(base_dir, "logs")
    os.makedirs(log_dir, exist_ok=True)
    level = logging.DEBUG if debug else logging.ERROR
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    for h in list(root.handlers):
        root.removeHandler(h)

    fh = logging.FileHandler(os.path.join(log_dir, "itakukaigokensaku.log"), encoding="utf-8")
    fh.setLevel(level)
    fh.setFormatter(fmt)
    root.addHandler(fh)

    sh = logging.StreamHandler(sys.stdout)
    sh.setLevel(logging.INFO if debug else logging.WARNING)
    sh.setFormatter(logging.Formatter("%(message)s"))
    root.addHandler(sh)

    logging.getLogger("selenium").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)


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


def run(settings: cfg.Settings, args) -> int:
    from src.navigator import Navigator, SiteError  # Selenium は実行時に読み込む

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

    if args.diagnose:
        settings.dump_html = True
    dump_dir = os.path.join(settings.log_dir, "html") if settings.dump_html else None
    nav = Navigator(
        pref=settings.pref,
        pref_code=prefs[settings.pref],
        display=settings.display,
        wait=settings.wait,
        retry=settings.retry,
        dump_dir=dump_dir,
    )

    progress = Progress(os.path.join(settings.log_dir, "progress.json"))
    if settings.resume and not args.restart:
        progress.load()
    elif args.restart:
        progress.clear()

    started = datetime.now()
    errors: list[str] = []
    try:
        if args.diagnose:
            return diagnose(nav, settings, list(services.values()))

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

        step = 0
        found_columns: dict = {}
        for svc_name, sd in services.items():
            for city in cities:
                step += 1
                head = f"[{step}/{total}] {city} / {svc_name}"
                if progress.is_done(svc_name, city):
                    print(f"{head} … 取得済みのためスキップ")
                    continue
                try:
                    nav.search(city, sd.site_label, exact=(settings.search_type == "exact"))
                    listings = nav.collect_listings()
                    print(f"{head} … {len(listings)}件")
                    rows = []
                    found = found_columns.setdefault(svc_name, set())
                    for i, lst in enumerate(listings, 1):
                        ctx = {
                            "city": city,
                            "service": svc_name,
                            "pref": settings.pref,
                            "name": lst.name,
                            "jigyosyo_cd": lst.jigyosyo_cd,
                            "url": lst.url,
                        }
                        h = Harvest()
                        for html in nav.detail_pages(lst):
                            h.merge(harvest_html(html))
                        rows.append(
                            build_row(sd.fields, h, ctx,
                                      normalize=settings.normalize, found=found)
                        )
                        if i % 10 == 0 or i == len(listings):
                            print(f"      {i}/{len(listings)} 件取得", end="\r", flush=True)
                    print(" " * 40, end="\r")
                    progress.put(svc_name, city, rows)
                    progress.save()
                except SiteError as e:
                    msg = f"{city} / {svc_name}: {e}"
                    errors.append(msg)
                    log.error(msg)
                    print(f"{head} … 失敗（{e}）")

        data = {name: progress.collected(name) for name in services}
        meta = {
            "実行日時": started.strftime("%Y/%m/%d %H:%M"),
            "都道府県": settings.pref,
            "対象市区町村": ", ".join(cities),
            "サービス種別": ", ".join(services),
            "失敗した検索": "\n".join(errors) or "なし",
        }
        # 一度も見出しが見つからなかった列（サイト構成変更の検知）。
        # 「時分～時分」のように整形後に空欄となる列は対象外。
        for name, sd in services.items():
            rows = data.get(name, [])
            if not rows:
                continue
            seen = found_columns.get(name, set())
            bad = [fd.column for fd in sd.fields if fd.column not in seen]
            if bad:
                meta[f"要確認列（{name}）"] = ", ".join(bad)
                print(f"\n※ {name}: ほぼ全件が空欄の列があります → {', '.join(bad)}")
                print("   サイトの見出し語が変わった可能性があります。"
                      "config/fields_*.csv の lookup 列で対応できます。")

        out = write_workbook(
            settings.output_path,
            services,
            data,
            summary_sheet=settings.summary_sheet,
            per_city_sheet=settings.per_city_sheet,
            decorate=settings.decorate,
            meta=meta,
        )
        total_rows = sum(len(v) for v in data.values())
        print(f"\n完了：{total_rows}件を出力しました\n  {out}")
        if errors:
            print(f"\n失敗した検索が {len(errors)} 件あります（logs/itakukaigokensaku.log を確認してください）")
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

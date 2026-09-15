"""取得処理の本体。コマンドライン版（main.py）と画面版（gui.py）で共用する。

進捗の伝え方だけを呼び出し側に任せ、取得のしかたは1か所にまとめている。
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Dict, List, Optional

from src.excelout import write_workbook
from src.extract import build_row, harvest_pages
from src.state import Progress

log = logging.getLogger(__name__)


class Cancelled(RuntimeError):
    """利用者が停止したとき。"""


@dataclass
class Report:
    """1回の取得の結果。"""

    data: Dict[str, List[dict]] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    meta: Dict[str, object] = field(default_factory=dict)
    output_path: str = ""
    cancelled: bool = False
    trial: bool = False          # お試し実行（件数を絞った）かどうか

    @property
    def total_rows(self) -> int:
        return sum(len(v) for v in self.data.values())


def make_navigator(settings, pref_code: str):
    from src.navigator import Navigator

    dump_dir = os.path.join(settings.log_dir, "html") if settings.dump_html else None
    return Navigator(
        pref=settings.pref,
        pref_code=pref_code,
        display=settings.display,
        wait=settings.wait,
        retry=settings.retry,
        dump_dir=dump_dir,
    )


def row_from_listing(nav, sd, lst, base_ctx: dict, normalize: bool = True,
                     found: Optional[set] = None, rejected: Optional[set] = None):
    """事業所1件ぶんの行を作る。

    「検索結果の1件ぶん → 詳細ページ群 → 見出し索引 → 行」という順序と
    ctx の組み立ては、本番とテストで必ず同じものを使うこと。
    以前ここが二重化していて、本番だけ直してテストが古い手順のまま
    通り続ける状態になっていた。

    戻り値は (行, 見出し索引)。
    """
    pages = nav.detail_pages(lst)
    if lst.row_html:
        pages.insert(0, lst.row_html)
    h, heading = harvest_pages(pages)
    ctx = dict(base_ctx)
    ctx.update({
        "name": lst.name,
        "heading": heading or lst.name,
        "jigyosyo_cd": lst.jigyosyo_cd,
        "url": lst.url,
    })
    return build_row(sd.fields, h, ctx, normalize=normalize,
                     found=found, rejected=rejected), h


def collect(
    nav,
    settings,
    services: Dict[str, object],
    cities: List[str],
    progress: Progress,
    on_log: Optional[Callable[[str], None]] = None,
    on_progress: Optional[Callable[[int, int, str, int, int], None]] = None,
    should_stop: Optional[Callable[[], bool]] = None,
) -> Report:
    """市区町村×サービスを順に取得し、Excelまで書き出す。

    on_log(メッセージ)                                     … 1行ぶんの経過
    on_progress(済, 全体, 現在の見出し, 件目, 件数)        … 進み具合
    should_stop()                                          … True で中断
    """
    from src.navigator import SiteError

    say = on_log or (lambda _m: None)
    tick = on_progress or (lambda *a: None)
    stop = should_stop or (lambda: False)

    limit = max(0, int(getattr(settings, "limit", 0) or 0))
    started = datetime.now()
    rep = Report()
    rep.trial = bool(limit)
    trial_rows: Dict[str, List[dict]] = {}
    found_columns: Dict[str, set] = {}
    rejected_columns: Dict[str, set] = {}
    label_samples: Dict[str, list] = {}
    fetched: Dict[str, int] = {}      # 今回実際に取得した自治体数（サービス別）
    tally: List[tuple] = []           # (サービス, 市区町村, 取得件数, サイト表示件数)
    total = len(cities) * len(services)
    step = 0

    try:
        for svc_name, sd in services.items():
            for city in cities:
                if stop():
                    raise Cancelled
                step += 1
                head = f"{city} / {svc_name}"
                tick(step - 1, total, head, 0, 0)
                if progress.is_done(svc_name, city):
                    say(f"[{step}/{total}] {head} … 取得済みのためスキップ")
                    continue
                try:
                    nav.search(city, sd.site_label,
                               exact=(settings.search_type == "exact"))
                    listings = nav.collect_listings()
                    shown = nav.last_total_on_site
                    if limit:
                        listings = listings[:limit]
                    # サイトが「◯件」と表示している数と突き合わせ、取りこぼしを検知する
                    # （お試し実行は最初から件数を絞っているので対象外）
                    if not limit and shown is not None and shown != len(listings):
                        msg = (f"{city} / {svc_name}: サイトの表示は{shown}件ですが"
                               f"{len(listings)}件しか取得できませんでした")
                        rep.errors.append(msg)
                        log.error(msg)
                        say(f"[{step}/{total}] {head} … 【要確認】{len(listings)}/{shown}件")
                    else:
                        say(f"[{step}/{total}] {head} … {len(listings)}件")
                    tally.append((svc_name, city, len(listings), shown))
                    rows = []
                    found = found_columns.setdefault(svc_name, set())
                    rejected = rejected_columns.setdefault(svc_name, set())
                    for i, lst in enumerate(listings, 1):
                        if stop():
                            raise Cancelled
                        row, h = row_from_listing(
                            nav, sd, lst,
                            {"city": city, "service": svc_name, "pref": settings.pref},
                            normalize=settings.normalize, found=found, rejected=rejected,
                        )
                        if svc_name not in label_samples:
                            label_samples[svc_name] = sorted(h.kv) + [
                                f"{a}×{b}" for a, b in sorted(h.matrix)
                            ]
                        rows.append(row)
                        tick(step - 1, total, head, i, len(listings))
                    if limit:
                        # お試しのぶんは進捗に残さない。残すと次回の本番実行で
                        # 「取得済み」と判断され、5件だけのデータが出てしまう
                        trial_rows.setdefault(svc_name, []).extend(rows)
                    else:
                        progress.put(svc_name, city, rows)
                        progress.save()
                    fetched[svc_name] = fetched.get(svc_name, 0) + 1
                    tick(step, total, head, len(listings), len(listings))
                except SiteError as e:
                    msg = f"{city} / {svc_name}: {e}"
                    rep.errors.append(msg)
                    log.error(msg)
                    say(f"[{step}/{total}] {head} … 失敗（{e}）")
    except Cancelled:
        rep.cancelled = True
        say("停止しました。取得済みのぶんを書き出します")

    # 今回選んだ市区町村のぶんだけを出力する（過去の取得ぶんを混ぜない）
    if limit:
        rep.data = {name: trial_rows.get(name, []) for name in services}
    else:
        rep.data = {name: progress.collected(name, cities) for name in services}
    rep.meta = {
        "実行日時": started.strftime("%Y/%m/%d %H:%M"),
        "都道府県": settings.pref,
        "対象市区町村": ", ".join(cities),
        "サービス種別": ", ".join(services),
        "失敗した検索": "\n".join(rep.errors) or "なし",
    }
    if limit:
        rep.meta["取得方法"] = (
            f"お試し実行：1つの市区町村につき先頭{limit}件だけ取得しました。"
            "すべて取得するには、お試しを外して実行してください")
    if rep.cancelled:
        rep.meta["備考"] = "途中で停止しました。再実行すると続きから取得します"

    # サイト上で見つかった見出しは、問題が無くても毎回残しておく。
    # 「値が取れているように見えて実は別の項目を拾っている」場合、
    # 要確認列には出ないため、後から突き合わせる材料が必要になる。
    for name, labels in label_samples.items():
        try:
            os.makedirs(settings.log_dir, exist_ok=True)
            with open(os.path.join(settings.log_dir, f"見つかった見出し_{name}.txt"),
                      "w", encoding="utf-8") as f:
                f.write("\n".join(labels))
        except OSError:
            pass

    if tally:
        rep.meta["市区町村別の件数"] = "\n".join(
            f"{svc} {city}: {got}件" + (f"（サイト表示 {shown}件）" if shown not in (None, got) else "")
            for svc, city, got, shown in tally
        )

    # 一度も見出しが見つからなかった列（サイト構成変更の検知）。
    # 今回1件も取得していない（全部スキップした）サービスは判定材料が無いので対象外。
    # ここを見落とすと「全列が要確認」という誤警報が毎回出て、本当の警告が埋もれる。
    for name, sd in services.items():
        rows = rep.data.get(name, [])
        if not rows or not fetched.get(name):
            continue
        seen = found_columns.get(name, set())
        bad_value = rejected_columns.get(name, set())
        # 見出しが見つからなかった列に加えて、「見つかったが値として使えず、
        # 結局どの行も空欄のままだった」列も要確認とする
        bad = [
            fd.column for fd in sd.fields
            if fd.column not in seen
            or (fd.column in bad_value
                and all(r.get(fd.column) in (None, "") for r in rows))
        ]
        if not bad:
            continue
        rep.meta[f"要確認列（{name}）"] = ", ".join(bad)
        labels = label_samples.get(name, [])
        if labels:
            rep.meta[f"見つかった見出し（{name}）"] = " / ".join(labels)[:30000]
            try:
                os.makedirs(settings.log_dir, exist_ok=True)
                with open(os.path.join(settings.log_dir, "見つかった見出し.txt"),
                          "w", encoding="utf-8") as f:
                    f.write(f"【{name}】取得できなかった列: {', '.join(bad)}\n\n")
                    f.write("\n".join(labels))
            except OSError:
                pass
        say(f"※ {name}: ほぼ全件が空欄の列があります → {', '.join(bad)}")
        say("   config/fields_*.csv の lookup 列で対応できます")

    if not rep.cancelled and not rep.errors and not limit:
        # 全部取り切ったので、再開用の進捗は役目を終えた。
        # 残したままだと次回の実行が「取得済み」と判断して古いデータを出す。
        progress.clear()

    out = settings.output_path
    if limit:
        # 本番データと取り違えないよう、ファイル名で区別する
        base, ext = os.path.splitext(out)
        out = f"{base}_お試し{ext}"
    rep.output_path = write_workbook(
        out, services, rep.data,
        summary_sheet=settings.summary_sheet,
        per_city_sheet=settings.per_city_sheet,
        decorate=settings.decorate,
        meta=rep.meta,
    )
    return rep

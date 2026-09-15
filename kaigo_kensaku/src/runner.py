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

    started = datetime.now()
    rep = Report()
    found_columns: Dict[str, set] = {}
    label_samples: Dict[str, list] = {}
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
                    say(f"[{step}/{total}] {head} … {len(listings)}件")
                    rows = []
                    found = found_columns.setdefault(svc_name, set())
                    for i, lst in enumerate(listings, 1):
                        if stop():
                            raise Cancelled
                        ctx = {
                            "city": city, "service": svc_name, "pref": settings.pref,
                            "name": lst.name, "jigyosyo_cd": lst.jigyosyo_cd,
                            "url": lst.url,
                        }
                        pages = nav.detail_pages(lst)
                        if lst.row_html:
                            pages.insert(0, lst.row_html)
                        h, heading = harvest_pages(pages)
                        if svc_name not in label_samples:
                            label_samples[svc_name] = sorted(h.kv) + [
                                f"{a}×{b}" for a, b in sorted(h.matrix)
                            ]
                        ctx["heading"] = heading or lst.name
                        rows.append(build_row(sd.fields, h, ctx,
                                              normalize=settings.normalize, found=found))
                        tick(step - 1, total, head, i, len(listings))
                    progress.put(svc_name, city, rows)
                    progress.save()
                    tick(step, total, head, len(listings), len(listings))
                except SiteError as e:
                    msg = f"{city} / {svc_name}: {e}"
                    rep.errors.append(msg)
                    log.error(msg)
                    say(f"[{step}/{total}] {head} … 失敗（{e}）")
    except Cancelled:
        rep.cancelled = True
        say("停止しました。取得済みのぶんを書き出します")

    rep.data = {name: progress.collected(name) for name in services}
    rep.meta = {
        "実行日時": started.strftime("%Y/%m/%d %H:%M"),
        "都道府県": settings.pref,
        "対象市区町村": ", ".join(cities),
        "サービス種別": ", ".join(services),
        "失敗した検索": "\n".join(rep.errors) or "なし",
    }
    if rep.cancelled:
        rep.meta["備考"] = "途中で停止しました。再実行すると続きから取得します"

    # 一度も見出しが見つからなかった列（サイト構成変更の検知）
    for name, sd in services.items():
        rows = rep.data.get(name, [])
        if not rows:
            continue
        seen = found_columns.get(name, set())
        bad = [fd.column for fd in sd.fields if fd.column not in seen]
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

    rep.output_path = write_workbook(
        settings.output_path, services, rep.data,
        summary_sheet=settings.summary_sheet,
        per_city_sheet=settings.per_city_sheet,
        decorate=settings.decorate,
        meta=rep.meta,
    )
    return rep

"""settings.ini / config配下のマスタ読み込み。"""
from __future__ import annotations

import configparser
import csv
import json
import os
from dataclasses import dataclass, field
from datetime import date
from typing import Dict, List


@dataclass
class FieldDef:
    column: str
    lookups: List[str]
    transform: str
    group1: str = ""
    group2: str = ""


@dataclass
class ServiceDef:
    service_name: str
    short_name: str
    service_cd: str
    fields_file: str
    site_label: str
    fields: List[FieldDef] = field(default_factory=list)


@dataclass
class Settings:
    base_dir: str
    debug: bool
    display: bool
    dump_html: bool
    pref: str
    cities_raw: str
    search_type: str
    services_raw: str
    out_file: str
    summary_sheet: bool
    per_city_sheet: bool
    decorate: bool
    normalize: bool
    wait: float
    retry: int
    resume: bool

    @property
    def log_dir(self) -> str:
        return os.path.join(self.base_dir, "logs")

    @property
    def output_path(self) -> str:
        name = (self.out_file
                .replace("{date}", date.today().strftime("%Y%m%d"))
                .replace("{pref}", self.pref or ""))
        return name if os.path.isabs(name) else os.path.join(self.base_dir, name)


def _b(v: str) -> bool:
    return str(v).strip().lower() in ("true", "1", "yes", "on")


def load_settings(base_dir: str) -> Settings:
    path = os.path.join(base_dir, "settings.ini")
    cp = configparser.ConfigParser()
    # 値に ; や # を含むコメント扱いを防ぐため inline_comment_prefixes は使わない
    with open(path, encoding="utf-8-sig") as f:
        cp.read_file(f)

    def g(sec: str, key: str, default: str = "") -> str:
        try:
            return cp.get(sec, key).strip()
        except Exception:
            return default

    return Settings(
        base_dir=base_dir,
        debug=_b(g("dev", "debug", "True")),
        display=_b(g("dev", "display", "False")),
        dump_html=_b(g("dev", "dump_html", "False")),
        pref=g("search", "pref"),
        cities_raw=g("search", "cities"),
        search_type=g("search", "search_type", "partial") or "partial",
        services_raw=g("search", "services", "居宅介護支援"),
        out_file=g("output", "file", "介護事業所一覧_{date}.xlsx"),
        summary_sheet=_b(g("output", "summary_sheet", "True")),
        per_city_sheet=_b(g("output", "per_city_sheet", "True")),
        decorate=_b(g("output", "decorate", "True")),
        normalize=_b(g("output", "normalize", "True")),
        wait=float(g("run", "wait", "1.0") or 1.0),
        retry=int(g("run", "retry", "3") or 3),
        resume=_b(g("run", "resume", "True")),
    )


def parse_names(raw: str) -> List[str]:
    """「居宅介護支援, 訪問看護」のような指定を名前のリストにする。

    空白だけ／未設定なら空リスト。1件だけの指定と未設定を区別できるようにする。
    """
    return [t.strip() for t in (raw or "").replace("、", ",").split(",") if t.strip()]


def load_prefectures(base_dir: str) -> Dict[str, str]:
    path = os.path.join(base_dir, "config", "prefectures.csv")
    with open(path, encoding="utf-8-sig", newline="") as f:
        return {r["pref_name"]: r["pref_code"] for r in csv.DictReader(f)}


def load_fields(base_dir: str, fields_file: str) -> List[FieldDef]:
    path = os.path.join(base_dir, "config", fields_file)
    out: List[FieldDef] = []
    with open(path, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            if not (r.get("column") or "").strip():
                continue
            out.append(
                FieldDef(
                    column=r["column"].strip(),
                    lookups=[x.strip() for x in (r.get("lookup") or "").split("|") if x.strip()],
                    transform=(r.get("transform") or "text").strip() or "text",
                    group1=(r.get("group1") or "").strip(),
                    group2=(r.get("group2") or "").strip(),
                )
            )
    return out


def load_services(base_dir: str) -> Dict[str, ServiceDef]:
    path = os.path.join(base_dir, "config", "services.csv")
    out: Dict[str, ServiceDef] = {}
    with open(path, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            sd = ServiceDef(
                service_name=r["service_name"].strip(),
                short_name=r["short_name"].strip(),
                service_cd=r["service_cd"].strip(),
                fields_file=r["fields_file"].strip(),
                site_label=(r.get("site_label") or r["service_name"]).strip(),
            )
            sd.fields = load_fields(base_dir, sd.fields_file)
            out[sd.service_name] = sd
    return out


def resolve_cities(base_dir: str, cities_raw: str, available: List[str]) -> List[str]:
    """設定値の市区町村指定を、実際の市区町村名リストへ展開する。

    ALL / 前方一致ワイルドカード(神戸市*) / @ファイル / カンマ区切り に対応。
    available が空（サイト未取得）の場合は指定をそのまま返す。
    """
    raw = (cities_raw or "").strip()
    if raw.startswith("@"):
        p = os.path.join(base_dir, raw[1:].strip())
        with open(p, encoding="utf-8-sig") as f:
            tokens = [ln.strip() for ln in f if ln.strip() and not ln.startswith("#")]
    else:
        tokens = [t.strip() for t in raw.replace("、", ",").split(",") if t.strip()]

    if any(t.upper() == "ALL" for t in tokens):
        return list(available)

    resolved: List[str] = []
    for t in tokens:
        if t.endswith("*"):
            prefix = t[:-1]
            hits = [c for c in available if c.startswith(prefix)]
            resolved.extend(hits if hits else [])
            if not hits and not available:
                resolved.append(prefix)
        else:
            resolved.append(t)
    # 重複除去（順序維持）
    seen, out = set(), []
    for c in resolved:
        if c not in seen:
            seen.add(c)
            out.append(c)
    return out


def load_last_input(base_dir: str) -> dict:
    """旧ツール互換の input_settings.json があれば既定値として読む。"""
    path = os.path.join(base_dir, "input_settings.json")
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_last_input(base_dir: str, pref: str, cities: str, search_type: str,
                    services: str = "") -> None:
    path = os.path.join(base_dir, "input_settings.json")
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(
                {"select_pref": pref, "input_cities": cities,
                 "search_type": search_type, "services": services},
                f,
                ensure_ascii=False,
            )
    except Exception:
        pass

"""データを統合して、生存分析・人員構成・営業先マップのダッシュボードを出力する。

    python build.py                       # data/raw の実データで作成
    python build.py --data-dir data/demo  # デモデータで作成（make_demo_data.py で生成）

出力: output/dashboard.html と CSV 一式
"""

from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path

import pandas as pd

from config import AREA, CATEGORIES, OUT_DIR, OWN_STATION, RAW_DIR, SOURCES
from loaders import STD_COLS, filter_area, norm_name, read_table, standardize
from survival import build_history, load_snapshots, survival_at, survival_summary

TEMPLATE = Path(__file__).resolve().parent / "templates" / "dashboard.html"
SALES_CATS = ["kyotaku", "houkatsu", "hospital", "clinic", "soudan"]


# ---------------------------------------------------------------------------
# 施設（最新時点）
# ---------------------------------------------------------------------------

def latest_files(directory: Path) -> list[Path]:
    files = [p for p in directory.glob("*") if p.suffix.lower() in (".csv", ".xlsx", ".xls")]
    stamped = [p for p in files if re.match(r"\d{6}", p.name)]
    if not stamped:
        return files
    latest = max(p.name[:6] for p in stamped)
    return [p for p in files if p.name.startswith(latest) or p not in stamped]


def load_facilities(data_dir: Path) -> pd.DataFrame:
    frames = []
    for key, src in SOURCES.items():
        d = data_dir / src["dir"]
        if not d.exists():
            continue
        default = "houkan" if key == "kouseikyoku_houkan" else None
        for p in latest_files(d):
            df = filter_area(standardize(read_table(p), key, p.name, default))
            frames.append(df)
    # 手入力の追加分（包括の一覧など）: data_dir/manual/*.csv に category 列付きで置く
    manual = data_dir / "manual"
    if manual.exists():
        for p in manual.glob("*.csv"):
            raw = read_table(p)
            df = standardize(raw, "manual", p.name, None)
            if "category" in raw.columns:
                df["category"] = raw["category"].values
            frames.append(filter_area(df))
    if not frames:
        return pd.DataFrame(columns=STD_COLS)
    fac = pd.concat(frames, ignore_index=True)
    fac = fac[fac["category"].notna()]
    # 同じ施設が複数ソースにあれば、座標を持つ行を優先して1行に
    fac["_has_geo"] = fac["lat"].notna()
    fac = fac.sort_values("_has_geo", ascending=False)
    fac = fac.drop_duplicates(subset=["category", "name_key", "ward"]).drop(columns="_has_geo")
    return fac.reset_index(drop=True)


# ---------------------------------------------------------------------------
# 人員
# ---------------------------------------------------------------------------

def load_staff(data_dir: Path) -> pd.DataFrame:
    p = data_dir / "staff.csv"
    if not p.exists():
        return pd.DataFrame()
    df = read_table(p)
    num = [c for c in df.columns if c not in ("事業所番号", "事業所名", "調査日", "出典")]
    for c in num:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["name_key"] = df["事業所名"].map(norm_name)
    exp = ["経験_1年未満", "経験_1-3年", "経験_3-5年", "経験_5-10年", "経験_10年以上"]
    ages = ["年代_20代", "年代_30代", "年代_40代", "年代_50代", "年代_60代以上"]
    total_exp = df[exp].sum(axis=1, min_count=1)
    df["看護職員_計"] = df[["看護職員_常勤", "看護職員_非常勤"]].sum(axis=1, min_count=1)
    df["経験5年未満割合"] = (df[exp[:3]].sum(axis=1) / total_exp).round(3)
    df["離職率"] = (df["前年度_退職者数"] / df["看護職員_計"]).round(3)
    df["常勤比率"] = (df["看護職員_常勤"] / df["看護職員_計"]).round(3)
    df["年代_回答数"] = df[ages].sum(axis=1, min_count=1)
    df["規模"] = pd.cut(df["看護職員_常勤換算"], [-1, 2.99, 4.99, 9.99, 999],
                      labels=["3未満", "3-5未満", "5-10未満", "10以上"]).astype(str)
    return df


def attach_staff(stations: pd.DataFrame, staff: pd.DataFrame) -> pd.DataFrame:
    if staff.empty:
        return stations
    # 事業所番号で突合し、取れなければ名称キーで突合
    ids = staff["事業所番号"].astype(str).str.strip()
    by_id = dict(zip(ids, staff.index))
    by_name = dict(zip(staff["name_key"], staff.index))
    idx = [by_id.get(str(k), by_name.get(n)) for k, n in zip(stations["key"], stations["name_key"])]
    cols = [c for c in staff.columns if c not in ("事業所番号", "事業所名", "name_key")]
    matched = staff.reindex(pd.Index(idx, dtype="float").fillna(-1).astype(int))[cols]
    return pd.concat([stations.reset_index(drop=True), matched.reset_index(drop=True)], axis=1)


# ---------------------------------------------------------------------------
# 集計
# ---------------------------------------------------------------------------

def haversine_km(lat1, lon1, lat2, lon2) -> float | None:
    if any(pd.isna(v) for v in (lat1, lon1, lat2, lon2)):
        return None
    p = math.pi / 180
    a = (math.sin((lat2 - lat1) * p / 2) ** 2
         + math.cos(lat1 * p) * math.cos(lat2 * p) * math.sin((lon2 - lon1) * p / 2) ** 2)
    return round(12742 * math.asin(math.sqrt(a)), 2)


def ward_summary(fac: pd.DataFrame, hist: pd.DataFrame) -> list[dict]:
    rows = []
    for w in AREA["wards"] + [""]:
        f = fac[fac["ward"] == w]
        r = {"ward": w or "区不明", **{c: int((f["category"] == c).sum()) for c in CATEGORIES}}
        if not hist.empty:
            h = hist[hist["ward"] == w]
            r["houkan_open"] = int((~h["closed"]).sum())
            r["houkan_closed"] = int(h["closed"].sum())
        if r["houkan"]:
            r["kyotaku_per_houkan"] = round(r["kyotaku"] / r["houkan"], 2)
        if any(v for k, v in r.items() if k != "ward"):
            rows.append(r)
    return rows


def records(df: pd.DataFrame, cols: list[str]) -> list[dict]:
    cols = [c for c in cols if c in df.columns]
    out = df[cols].copy()
    for c in cols:
        if pd.api.types.is_datetime64_any_dtype(out[c]):
            out[c] = out[c].dt.strftime("%Y-%m-%d")
    return json.loads(out.to_json(orient="records", force_ascii=False))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", type=Path, default=RAW_DIR)
    ap.add_argument("--out", type=Path, default=OUT_DIR)
    args = ap.parse_args()
    data_dir, out = args.data_dir.resolve(), args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    is_demo = (data_dir / "DEMO").exists()

    fac = load_facilities(data_dir)
    print(f"施設: {len(fac)}件 " + ", ".join(f"{CATEGORIES[c]}={n}" for c, n in fac["category"].value_counts().items()))

    # 生存曲線: 厚生局の月次名簿を優先、無ければ介護公表オープンデータの月次版
    snaps = load_snapshots(data_dir / SOURCES["kouseikyoku_houkan"]["dir"], "kouseikyoku_houkan", "houkan")
    hist_source = "関東信越厚生局 訪問看護ステーション名簿"
    if snaps.empty or snaps["snapshot"].nunique() < 2:
        snaps = load_snapshots(data_dir / SOURCES["kaigo_opendata"]["dir"], "kaigo_opendata")
        hist_source = "介護サービス情報公表 オープンデータ"
    hist = build_history(snaps) if not snaps.empty else pd.DataFrame()

    staff = load_staff(data_dir)
    surv, meta = {}, {}
    if not hist.empty:
        # 座標が名簿に無ければ施設テーブルから補完
        geo = fac[fac["category"] == "houkan"].dropna(subset=["lat"]).drop_duplicates("name_key")
        geo = geo.set_index("name_key")[["lat", "lon"]]
        for c in ("lat", "lon"):
            hist[c] = hist[c].fillna(hist["name_key"].map(geo[c]))
        attrs = dict(hist.attrs)
        hist = attach_staff(hist, staff)
        hist.attrs = attrs
        # 規模・人員は現存事業所にしか無い（廃止事業所の人員は取れない）ので層別に使わない
        strata = ["cohort", "corp_type", "ward"]
        surv = survival_summary(hist, strata)
        meta = {
            "source": hist_source,
            "first_month": hist.attrs["first_month"].strftime("%Y-%m"),
            "last_month": hist.attrs["last_month"].strftime("%Y-%m"),
            "n_snapshots": hist.attrs["n_snapshots"],
            "n": int(len(hist)), "closed": int(hist["closed"].sum()),
            "s3": survival_at(surv["overall"], 3), "s5": survival_at(surv["overall"], 5),
            "s10": survival_at(surv["overall"], 10),
        }
        hist.sort_values("start").to_csv(out / "station_history.csv", index=False, encoding="utf-8-sig")
        print(f"ステーション履歴: {meta['n']}件（うち廃止 {meta['closed']}） 5年生存率={meta['s5']}")
        if meta["n_snapshots"] < 12:
            print("  ⚠ スナップショットが12か月分未満です。廃止の把握が不十分なので fetch.py --wayback で過去版を足してください")

    sales = fac[fac["category"].isin(SALES_CATS)].copy()
    if OWN_STATION:
        sales["distance_km"] = [haversine_km(OWN_STATION["lat"], OWN_STATION["lon"], a, b)
                                for a, b in zip(sales["lat"], sales["lon"])]
        sales = sales.sort_values("distance_km")
    sales["category_label"] = sales["category"].map(CATEGORIES)
    sales.to_csv(out / "sales_targets.csv", index=False, encoding="utf-8-sig")
    fac.to_csv(out / "facilities.csv", index=False, encoding="utf-8-sig")

    station_cols = ["key", "name", "address", "ward", "corp", "corp_type", "start", "end", "closed",
                    "duration_y", "cohort", "lat", "lon", "看護職員_常勤", "看護職員_非常勤", "看護職員_常勤換算",
                    "経験_1年未満", "経験_1-3年", "経験_3-5年", "経験_5-10年", "経験_10年以上",
                    "前年度_採用者数", "前年度_退職者数", "離職率", "常勤比率", "経験5年未満割合", "規模",
                    "年代_20代", "年代_30代", "年代_40代", "年代_50代", "年代_60代以上", "年代_回答数"]
    payload = {
        "area": AREA, "categories": CATEGORIES, "is_demo": is_demo, "own": OWN_STATION,
        "survival": surv, "survival_meta": meta,
        "stations": records(hist, station_cols) if not hist.empty else [],
        "facilities": records(sales, ["category", "name", "address", "ward", "lat", "lon", "corp",
                                      "beds", "phone", "distance_km"]),
        "wards": ward_summary(fac, hist),
        "generated": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"),
    }
    (out / "data.json").write_text(json.dumps(payload, ensure_ascii=False, default=str), encoding="utf-8")
    html = TEMPLATE.read_text(encoding="utf-8").replace(
        "/*__DATA__*/null", json.dumps(payload, ensure_ascii=False, default=str).replace("</", "<\\/"))
    (out / "dashboard.html").write_text(html, encoding="utf-8")
    print(f"出力: {out / 'dashboard.html'}")


if __name__ == "__main__":
    main()

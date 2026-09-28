"""月次スナップショットからステーションの開設〜廃止の履歴を作り、生存曲線を推定する。

ポイント
- 開設日: 指定年月日（無ければ初めて名簿に載った月）
- 廃止日: 名簿から消えた月（最後に載った月の翌月）。最新月にも載っていれば打ち切り(censored)
- 左側切断: 最初のスナップショットより前に廃止された事業所は観測できない。
  そのため最初のスナップショット時点で既に存在した事業所は「その時点の事業所年齢から観察開始」
  （delayed entry）として扱い、生存率が楽観側に偏るのを防ぐ。
- 移転・開設者交代: コードが変わっても名称が同じで3か月以内に再登場したら同一事業所として継続扱い。
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd

from loaders import filter_area, read_table, snapshot_month, standardize

RELINK_MONTHS = 3


def load_snapshots(directory: Path, source: str, category: str | None = None) -> pd.DataFrame:
    rows = []
    for p in sorted(directory.glob("*")):
        if p.suffix.lower() not in (".csv", ".xlsx", ".xls"):
            continue
        month = snapshot_month(p)
        if month is None:
            continue
        df = filter_area(standardize(read_table(p), source, p.name, category))
        if category is None:
            df = df[df["category"] == "houkan"]
        df["snapshot"] = month
        rows.append(df)
    if not rows:
        return pd.DataFrame()
    return pd.concat(rows, ignore_index=True)


def build_history(snaps: pd.DataFrame) -> pd.DataFrame:
    """スナップショット群 → 1事業所1行の履歴テーブル。"""
    if snaps.empty:
        return pd.DataFrame()
    months = sorted(snaps["snapshot"].unique())
    first_month, last_month = months[0], months[-1]
    snaps = snaps.copy()
    snaps["key"] = snaps["id"].where(snaps["id"] != "", snaps["name_key"])

    g = snaps.sort_values("snapshot").groupby("key")
    hist = g.agg(
        name=("name", "last"), name_key=("name_key", "last"), address=("address", "last"),
        ward=("ward", "last"), corp=("corp", "last"), lat=("lat", "last"), lon=("lon", "last"),
        start_date=("start_date", "min"), first_seen=("snapshot", "min"), last_seen=("snapshot", "max"),
    ).reset_index()

    # 移転・交代の名寄せ: 消えた事業所と同名の新コードが近い時期に現れたら結合
    hist = _relink(hist)

    hist["start"] = hist["start_date"].fillna(hist["first_seen"])
    # 指定日が最初のスナップショット以前 → 名簿上最初から存在（左側切断）
    hist["closed"] = hist["last_seen"] < last_month
    hist["end"] = np.where(hist["closed"], hist["last_seen"] + pd.offsets.MonthBegin(1), last_month)
    hist["end"] = pd.to_datetime(hist["end"])
    hist["duration_y"] = (hist["end"] - hist["start"]).dt.days / 365.25
    entry = (pd.Timestamp(first_month) - hist["start"]).dt.days / 365.25
    hist["entry_y"] = entry.clip(lower=0)
    hist["open_year"] = hist["start"].dt.year
    hist["cohort"] = pd.cut(hist["open_year"], [0, 2011, 2017, 2021, 9999],
                            labels=["〜2011", "2012-2017", "2018-2021", "2022〜"]).astype(str)
    hist["corp_type"] = hist["corp"].map(corp_type_of)
    hist.attrs["first_month"] = pd.Timestamp(first_month)
    hist.attrs["last_month"] = pd.Timestamp(last_month)
    hist.attrs["n_snapshots"] = len(months)
    return hist


def _relink(hist: pd.DataFrame) -> pd.DataFrame:
    hist = hist.sort_values("first_seen").reset_index(drop=True)
    drop = set()
    for i, old in hist.iterrows():
        for j, new in hist.iterrows():
            if i == j or j in drop or new["name_key"] != old["name_key"] or not old["name_key"]:
                continue
            gap = (new["first_seen"].to_period("M") - old["last_seen"].to_period("M")).n
            if 0 < gap <= RELINK_MONTHS:
                hist.loc[j, "start_date"] = min(x for x in [old["start_date"], new["start_date"]] if pd.notna(x)) \
                    if pd.notna(old["start_date"]) or pd.notna(new["start_date"]) else pd.NaT
                hist.loc[j, "first_seen"] = old["first_seen"]
                drop.add(i)
                break
    return hist.drop(index=list(drop)).reset_index(drop=True)


def corp_type_of(corp) -> str:
    s = str(corp or "")
    if "株式会社" in s or "有限会社" in s or "合同会社" in s or "(株)" in s:
        return "営利法人"
    if "医療法人" in s:
        return "医療法人"
    if "社会福祉法人" in s:
        return "社会福祉法人"
    if "NPO" in s or "特定非営利" in s:
        return "NPO"
    if "社団" in s or "財団" in s or "協同組合" in s or "看護協会" in s or "医師会" in s:
        return "社団・財団・生協等"
    return "その他・不明"


# ---------------------------------------------------------------------------
# Kaplan-Meier（delayed entry 対応）と log-rank 検定
# ---------------------------------------------------------------------------

def kaplan_meier(df: pd.DataFrame, max_t: float = 15.0) -> list[dict]:
    d = df[df["duration_y"] > df["entry_y"]]
    times = np.sort(d.loc[d["closed"], "duration_y"].unique())
    s, var_sum = 1.0, 0.0
    curve = [{"t": 0.0, "s": 1.0, "lo": 1.0, "hi": 1.0, "n": int(((d["entry_y"] <= 0)).sum())}]
    for t in times:
        if t > max_t:
            break
        at_risk = int(((d["entry_y"] < t) & (d["duration_y"] >= t)).sum())
        events = int(((d["duration_y"] == t) & d["closed"]).sum())
        if at_risk == 0:
            continue
        s *= 1 - events / at_risk
        if at_risk > events:
            var_sum += events / (at_risk * (at_risk - events))
        lo, hi = _loglog_ci(s, var_sum)
        curve.append({"t": round(float(t), 3), "s": round(s, 4), "lo": lo, "hi": hi, "n": at_risk})
    return curve


def _loglog_ci(s: float, var_sum: float) -> tuple[float, float]:
    if s <= 0 or s >= 1 or var_sum == 0:
        return round(s, 4), round(s, 4)
    se = math.sqrt(var_sum) / abs(math.log(s))
    c = 1.96 * se
    return round(s ** math.exp(c), 4), round(s ** math.exp(-c), 4)


def survival_at(curve: list[dict], t: float) -> float | None:
    s = None
    for p in curve:
        if p["t"] <= t:
            s = p["s"]
    return s


def logrank(df: pd.DataFrame, group_col: str) -> float | None:
    """k群 log-rank 検定の p値。"""
    d = df[df["duration_y"] > df["entry_y"]]
    groups = [g for g in d[group_col].dropna().unique()]
    if len(groups) < 2:
        return None
    times = np.sort(d.loc[d["closed"], "duration_y"].unique())
    k = len(groups)
    O_E = np.zeros(k)
    V = np.zeros((k, k))
    for t in times:
        risk = (d["entry_y"] < t) & (d["duration_y"] >= t)
        ev = (d["duration_y"] == t) & d["closed"]
        n = risk.sum()
        e = ev.sum()
        if n < 2:
            continue
        n_g = np.array([(risk & (d[group_col] == g)).sum() for g in groups], dtype=float)
        e_g = np.array([(ev & (d[group_col] == g)).sum() for g in groups], dtype=float)
        O_E += e_g - e * n_g / n
        f = e * (n - e) / (n * n * (n - 1))
        V += f * (np.diag(n_g * n) - np.outer(n_g, n_g))
    try:
        stat = float(O_E[:-1] @ np.linalg.solve(V[:-1, :-1], O_E[:-1]))
    except np.linalg.LinAlgError:
        return None
    return round(_chi2_sf(stat, k - 1), 4)


def _chi2_sf(x: float, dof: int) -> float:
    """カイ二乗分布の上側確率（scipy無しで計算）。"""
    if x <= 0:
        return 1.0
    a = dof / 2.0
    return 1.0 - _gammainc_lower(a, x / 2.0)


def _gammainc_lower(a: float, x: float) -> float:
    if x < a + 1:
        term = total = 1.0 / a
        n = a
        for _ in range(500):
            n += 1
            term *= x / n
            total += term
            if abs(term) < 1e-12 * total:
                break
        return total * math.exp(-x + a * math.log(x) - math.lgamma(a))
    # 連分数
    b = x + 1 - a
    c = 1e300
    d = 1 / b
    h = d
    for i in range(1, 500):
        an = -i * (i - a)
        b += 2
        d = an * d + b
        d = 1 / d if abs(d) > 1e-300 else 1e300
        c = b + an / c
        if abs(c) < 1e-300:
            c = 1e-300
        delta = d * c
        h *= delta
        if abs(delta - 1) < 1e-12:
            break
    return 1.0 - math.exp(-x + a * math.log(x) - math.lgamma(a)) * h


def survival_summary(hist: pd.DataFrame, strata: list[str]) -> dict:
    res = {"overall": kaplan_meier(hist), "strata": {}}
    for col in strata:
        if col not in hist.columns:
            continue
        groups = {}
        for g, sub in hist.groupby(col):
            if len(sub) >= 3 and str(g) not in ("", "nan"):
                groups[str(g)] = {"n": int(len(sub)), "closed": int(sub["closed"].sum()),
                                  "curve": kaplan_meier(sub)}
        res["strata"][col] = {"groups": groups, "p": logrank(hist[hist[col].astype(str).isin(groups)], col)}
    return res

"""公的CSV/Excelを読み込んで、共通フォーマットの施設テーブルに揃える。"""

from __future__ import annotations

import re
import unicodedata
from datetime import date
from pathlib import Path

import pandas as pd

from config import AREA, COLS

# ---------------------------------------------------------------------------
# 読み込み
# ---------------------------------------------------------------------------

def _pick(df: pd.DataFrame, key: str) -> str | None:
    cols = {norm_text(c): c for c in df.columns}
    for cand in COLS[key]:
        if norm_text(cand) in cols:
            return cols[norm_text(cand)]
    # 部分一致（例: "事業所名称（漢字）"）
    for cand in COLS[key]:
        for nc, c in cols.items():
            if norm_text(cand) in nc:
                return c
    return None


def _find_header_row(raw: pd.DataFrame) -> int:
    """厚生局Excelのように表題行が上にあるファイルのヘッダー行を探す。"""
    keys = {norm_text(k) for k in COLS["name"] + COLS["address"]}
    for i in range(min(len(raw), 30)):
        cells = {norm_text(str(v)) for v in raw.iloc[i].tolist()}
        if cells & keys:
            return i
    return 0


def read_table(path: Path) -> pd.DataFrame:
    if path.suffix.lower() in (".xlsx", ".xls"):
        raw = pd.read_excel(path, header=None, dtype=str)
        h = _find_header_row(raw)
        df = raw.iloc[h + 1:].copy()
        df.columns = [str(c).replace("\n", "") for c in raw.iloc[h].tolist()]
        return df.dropna(how="all")
    for enc in ("utf-8-sig", "cp932", "utf-8"):
        try:
            raw = pd.read_csv(path, dtype=str, encoding=enc, header=None)
            break
        except (UnicodeDecodeError, pd.errors.ParserError):
            continue
    else:
        raise ValueError(f"読み込めません: {path}")
    h = _find_header_row(raw)
    df = raw.iloc[h + 1:].copy()
    df.columns = [str(c) for c in raw.iloc[h].tolist()]
    return df.dropna(how="all")


# ---------------------------------------------------------------------------
# 正規化
# ---------------------------------------------------------------------------

def norm_text(s) -> str:
    if s is None or (isinstance(s, float) and pd.isna(s)):
        return ""
    s = unicodedata.normalize("NFKC", str(s))
    return re.sub(r"\s+", "", s)


def norm_name(s) -> str:
    """名寄せ用の名称キー。法人格や表記揺れを落とす。"""
    s = norm_text(s)
    s = re.sub(r"(株式会社|有限会社|合同会社|一般社団法人|社会福祉法人|医療法人社団|医療法人財団|医療法人|特定非営利活動法人|NPO法人|\(株\)|\(有\))", "", s)
    s = s.replace("ステーション", "ST").replace("ｽﾃｰｼｮﾝ", "ST")
    s = s.replace("ヶ", "ケ").replace("ヵ", "ケ")
    return s


_ERA = {"明治": 1867, "大正": 1911, "昭和": 1925, "平成": 1988, "令和": 2018,
        "M": 1867, "T": 1911, "S": 1925, "H": 1988, "R": 2018}


def parse_date(v) -> pd.Timestamp | None:
    """西暦・和暦（令和6年4月1日 / R6.4.1 / H 18. 4. 1）・Excelシリアル値に対応。"""
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    s = norm_text(v)
    if not s or s.lower() in ("nan", "none", "-"):
        return None
    if re.fullmatch(r"\d{5}(\.0)?", s):  # Excelシリアル
        return pd.Timestamp("1899-12-30") + pd.Timedelta(days=int(float(s)))
    m = re.match(r"(明治|大正|昭和|平成|令和|[MTSHR])\.?(元|\d{1,2})[年.\-/](\d{1,2})[月.\-/](\d{1,2})", s)
    if m:
        y = 1 if m.group(2) == "元" else int(m.group(2))
        try:
            return pd.Timestamp(date(_ERA[m.group(1)] + y, int(m.group(3)), int(m.group(4))))
        except ValueError:
            return None
    m = re.match(r"(\d{4})[年.\-/]?(\d{1,2})[月.\-/]?(\d{1,2})", s)
    if m:
        try:
            return pd.Timestamp(date(int(m.group(1)), int(m.group(2)), int(m.group(3))))
        except ValueError:
            return None
    return None


def ward_of(address: str) -> str:
    for w in AREA["wards"]:
        if w in address:
            return w
    return ""


# ---------------------------------------------------------------------------
# カテゴリ判定
# ---------------------------------------------------------------------------

def classify(service_text: str, filename: str, beds) -> str | None:
    t = norm_text(service_text) + " " + norm_text(filename)
    if "訪問看護" in t or "_130" in t or "houkan" in t:
        return "houkan"
    if "居宅介護支援" in t or "_430" in t or "kyotaku" in t:
        return "kyotaku"
    if "地域包括" in t or "高齢者支援センター" in t or "houkatsu" in t:
        return "houkatsu"
    if "相談支援" in t or "soudan" in t:
        return "soudan"
    if "病院" in t or "hospital" in t:
        return "hospital"
    if "診療所" in t or "clinic" in t:
        return "clinic"
    try:
        if beds is not None and float(beds) >= 20:
            return "hospital"
    except (TypeError, ValueError):
        pass
    return None


# ---------------------------------------------------------------------------
# 共通フォーマットへの変換
# ---------------------------------------------------------------------------

STD_COLS = ["category", "id", "name", "name_key", "address", "ward", "lat", "lon",
            "corp", "corp_type", "service", "start_date", "beds", "phone", "source"]


def standardize(df: pd.DataFrame, source: str, filename: str,
                default_category: str | None = None) -> pd.DataFrame:
    out = pd.DataFrame(index=df.index)
    for key in ["id", "name", "address", "lat", "lon", "corp", "corp_type",
                "service", "start_date", "beds", "phone"]:
        c = _pick(df, key)
        out[key] = df[c] if c else None
    out["address"] = out["address"].map(norm_text)
    out["name"] = out["name"].map(lambda s: norm_text(s) if s is not None else "")
    out["id"] = out["id"].map(lambda s: norm_text(s).replace(".0", "") if s is not None else "")
    out["start_date"] = out["start_date"].map(parse_date)
    for k in ("lat", "lon", "beds"):
        out[k] = pd.to_numeric(out[k], errors="coerce")
    out["category"] = [
        default_category or classify(s or "", filename, b)
        for s, b in zip(out["service"], out["beds"])
    ]
    out["name_key"] = out["name"].map(norm_name)
    out["ward"] = out["address"].map(ward_of)
    out["source"] = source
    return out[STD_COLS]


def filter_area(df: pd.DataFrame) -> pd.DataFrame:
    kw = AREA["address_keyword"]
    return df[df["address"].str.contains(kw, na=False)].copy()


def load_dir(source: str, directory: Path, default_category: str | None = None) -> pd.DataFrame:
    frames = []
    for p in sorted(directory.glob("*")):
        if p.suffix.lower() not in (".csv", ".xlsx", ".xls"):
            continue
        df = standardize(read_table(p), source, p.name, default_category)
        frames.append(filter_area(df))
    if not frames:
        return pd.DataFrame(columns=STD_COLS)
    return pd.concat(frames, ignore_index=True)


def snapshot_month(path: Path) -> pd.Timestamp | None:
    """ファイル名先頭の YYYYMM をスナップショット月とみなす。"""
    m = re.match(r"(\d{4})(\d{2})", path.name)
    if not m:
        return None
    return pd.Timestamp(int(m.group(1)), int(m.group(2)), 1)

"""詳細ページHTML → 項目辞書。

サイトのHTML構造（class名やDOM階層）に依存せず、表の「見出しテキスト」で
値を探す方式にしている。サイトの見た目が変わっても、見出し語さえ同じなら
動き続ける。見出し語が変わった場合は config/fields_*.csv の lookup 列を
直すだけで対応できる（コード修正は不要）。
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from bs4 import BeautifulSoup

# 表セル内に混ざるボタン・リンクの文言（値として取り込まない）
NOISE = (
    "地図を開く",
    "ホームページを開く",
    "この事業所と比較する",
    "お気に入りに追加する",
    "お気に入りから削除する",
    "画面を印刷する",
    "詳細を見る",
    "別ウィンドウで開く",
    "新しいウィンドウで開きます",
)

_ZEN2HAN_DIGIT = str.maketrans("０１２３４５６７８９", "0123456789")


def norm_label(s: str) -> str:
    """見出し語の照合用正規化。空白・記号ゆれを吸収する。"""
    if s is None:
        return ""
    s = unicodedata.normalize("NFKC", s)
    s = re.sub(r"[\s　]+", "", s)
    s = s.replace("（", "(").replace("）", ")")
    s = s.strip("：:・.。 ")
    # 「※」以降の注記は無視
    s = s.split("※")[0]
    return s


def cell_text(cell) -> str:
    """セルの表示文字列。ボタン等のノイズを除去する。"""
    txt = cell.get_text("\n", strip=True)
    lines = []
    for ln in txt.split("\n"):
        ln = ln.strip()
        if not ln or any(n in ln for n in NOISE):
            continue
        lines.append(ln)
    out = " ".join(lines)
    out = out.replace("\t", " ")
    return re.sub(r"[ ]{2,}", " ", out).strip()


@dataclass
class Harvest:
    """1事業所ぶんの全タブから集めた見出し→値の索引。"""

    kv: Dict[str, str] = field(default_factory=dict)
    matrix: Dict[Tuple[str, str], str] = field(default_factory=dict)

    def merge(self, other: "Harvest") -> None:
        for k, v in other.kv.items():
            if v and (k not in self.kv or not self.kv[k]):
                self.kv[k] = v
        for k, v in other.matrix.items():
            if v and (k not in self.matrix or not self.matrix[k]):
                self.matrix[k] = v


def _grid(table) -> Tuple[Dict[Tuple[int, int], object], int, int]:
    """rowspan/colspan を展開したセル格子を作る。"""
    rows = table.find_all("tr")
    # 入れ子テーブルの tr は除外（直近の親 table が自分自身のものだけ残す）
    rows = [tr for tr in rows if tr.find_parent("table") is table]
    grid: Dict[Tuple[int, int], object] = {}
    for r, tr in enumerate(rows):
        cells = [c for c in tr.find_all(["th", "td"]) if c.find_parent("tr") is tr]
        c = 0
        for cell in cells:
            while (r, c) in grid:
                c += 1
            try:
                rs = max(1, int(cell.get("rowspan", 1)))
                cs = max(1, int(cell.get("colspan", 1)))
            except (TypeError, ValueError):
                rs = cs = 1
            rs, cs = min(rs, 50), min(cs, 50)
            for dr in range(rs):
                for dc in range(cs):
                    grid.setdefault((r + dr, c + dc), cell)
            c += cs
    nrows = max((k[0] for k in grid), default=-1) + 1
    ncols = max((k[1] for k in grid), default=-1) + 1
    return grid, nrows, ncols


def harvest_html(html: str) -> Harvest:
    """ページ内の全テーブルを走査し、kv索引と行列索引を作る。"""
    soup = BeautifulSoup(html, "html.parser")
    h = Harvest()

    for table in soup.find_all("table"):
        grid, nrows, ncols = _grid(table)
        if not grid:
            continue
        for r in range(nrows):
            for c in range(ncols):
                cell = grid.get((r, c))
                if cell is None or cell.name != "td":
                    continue
                value = cell_text(cell)
                if not value:
                    continue
                # この td から見て左側にある th（＝行見出し）
                row_heads, seen = [], set()
                for cc in range(c):
                    hc = grid.get((r, cc))
                    if hc is not None and hc.name == "th" and id(hc) not in seen:
                        seen.add(id(hc))
                        lb = norm_label(cell_text(hc))
                        if lb:
                            row_heads.append(lb)
                # 上側にある th（＝列見出し）
                col_heads, seen = [], set()
                for rr in range(r):
                    hc = grid.get((rr, c))
                    if hc is not None and hc.name == "th" and id(hc) not in seen:
                        seen.add(id(hc))
                        lb = norm_label(cell_text(hc))
                        if lb:
                            col_heads.append(lb)

                for rl in row_heads:
                    for cl in col_heads:
                        h.matrix.setdefault((rl, cl), value)
                        h.matrix.setdefault((cl, rl), value)

                # 行に td が1つだけなら「見出し：値」とみなす
                tds = {
                    id(grid[(r, cc)]): grid[(r, cc)]
                    for cc in range(ncols)
                    if grid.get((r, cc)) is not None and grid[(r, cc)].name == "td"
                }
                if len(tds) == 1:
                    for rl in row_heads:
                        h.kv.setdefault(rl, value)
                if len(col_heads) == 1 and not row_heads:
                    h.kv.setdefault(col_heads[0], value)

        # th → 直後の td が同一行に並ぶ「th td th td」形式も拾う
        for r in range(nrows):
            prev_head: Optional[str] = None
            last = None
            for c in range(ncols):
                cell = grid.get((r, c))
                if cell is None or cell is last:
                    continue
                last = cell
                if cell.name == "th":
                    prev_head = norm_label(cell_text(cell))
                elif prev_head:
                    v = cell_text(cell)
                    if v:
                        h.kv.setdefault(prev_head, v)
                    prev_head = None

    # <dl><dt>見出し</dt><dd>値</dd></dl> 形式
    for dl in soup.find_all("dl"):
        dts = dl.find_all("dt")
        for dt in dts:
            dd = dt.find_next_sibling("dd")
            if dd is not None:
                lb, v = norm_label(cell_text(dt)), cell_text(dd)
                if lb and v:
                    h.kv.setdefault(lb, v)
    return h


# --------------------------------------------------------------------------
# 値の整形
# --------------------------------------------------------------------------

_EMPTY_TIME = re.compile(r"^[時分～~\-\s　]*$")


def _to_int(v: str):
    if v is None:
        return ""
    v = unicodedata.normalize("NFKC", str(v))
    m = re.search(r"-?\d+", v.replace(",", ""))
    return int(m.group()) if m else ""


def _to_date(v: str) -> str:
    if not v:
        return ""
    s = unicodedata.normalize("NFKC", v).strip()
    m = re.search(r"(\d{4})\s*[年/\-\.]\s*(\d{1,2})\s*[月/\-\.]\s*(\d{1,2})", s)
    if m:
        return "%04d/%02d/%02d" % tuple(int(x) for x in m.groups())
    m = re.search(r"(令和|平成|昭和)\s*(\d{1,2}|元)\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日", s)
    if m:
        era, yy, mm, dd = m.groups()
        yy = 1 if yy == "元" else int(yy)
        base = {"令和": 2018, "平成": 1988, "昭和": 1925}[era]
        return "%04d/%02d/%02d" % (base + yy, int(mm), int(dd))
    return s


def _clean_addr(v: str, pref: str = "") -> str:
    s = re.sub(r"〒\s*\d{3}-?\d{4}", "", v or "")
    s = s.replace("　", " ")
    s = re.sub(r"\s+", "", s).strip()
    if pref and s and not s.startswith(pref):
        s = pref + s
    return s


def _yesno(v: str) -> str:
    s = norm_label(v or "")
    if not s:
        return ""
    if s.startswith("あり") or s in ("有", "有り", "○", "◯"):
        return "あり"
    if s.startswith("なし") or s in ("無", "無し", "×", "－", "-"):
        return "なし"
    return v.strip()


def apply_transform(value: str, transform: str, ctx: dict, normalize: bool):
    v = (value or "").strip()
    if transform == "int":
        return _to_int(v)
    if transform == "date":
        return _to_date(v) if normalize else v
    if transform == "time":
        if normalize and _EMPTY_TIME.match(unicodedata.normalize("NFKC", v)):
            return ""
        return v
    if transform == "addr":
        return _clean_addr(v, ctx.get("pref", "") if normalize else "")
    if transform == "yesno":
        return _yesno(v) if normalize else v
    if transform == "space":
        return re.sub(r"[ \t]{2,}", " ", v).strip()
    if transform == "trim":
        return v
    return v


def lookup_value(lookup: str, h: Harvest, ctx: dict) -> Optional[str]:
    """1つの lookup 指定（ctx: / kv: / matrix:）を解決する。"""
    if lookup.startswith("ctx:"):
        return ctx.get(lookup[4:].strip())
    if lookup.startswith("kv:"):
        return h.kv.get(norm_label(lookup[3:]))
    if lookup.startswith("matrix:"):
        body = lookup[7:]
        if "/" not in body:
            return None
        a, b = body.split("/", 1)
        return h.matrix.get((norm_label(a), norm_label(b)))
    # 接頭辞なしは kv 扱い
    return h.kv.get(norm_label(lookup))


def build_row(fields, h: Harvest, ctx: dict, normalize: bool = True,
              found: Optional[set] = None) -> dict:
    """項目定義に従って1行ぶんの辞書を作る。

    found を渡すと、ページ上で見出しが見つかった列名を追加する。
    「整形した結果たまたま空欄」（営業時間の『時分～時分』など）と
    「そもそも見出しが無い」（サイト構成の変更）を区別するために使う。
    """
    row = {}
    for fd in fields:
        raw = ""
        for lk in fd.lookups:
            got = lookup_value(lk, h, ctx)
            if got not in (None, ""):
                raw = got
                break
        if raw != "" and found is not None:
            found.add(fd.column)
        row[fd.column] = apply_transform(raw, fd.transform, ctx, normalize)
    return row


def missing_columns(row: dict, fields) -> List[str]:
    """値が取れなかった列名（サイト構成変更の検知用）。"""
    return [fd.column for fd in fields if row.get(fd.column) in (None, "")]

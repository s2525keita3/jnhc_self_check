"""詳細ページHTML → 項目辞書。

サイトのHTML構造（class名やDOM階層）に依存せず、表の「見出しテキスト」で
値を探す方式にしている。サイトの見た目が変わっても、見出し語さえ同じなら
動き続ける。見出し語が変わった場合は config/fields_*.csv の lookup 列を
直すだけで対応できる（コード修正は不要）。
"""
from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from urllib.parse import unquote

from bs4 import BeautifulSoup

log = logging.getLogger(__name__)

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


# 番号だけのalt（アイコンの通し番号など）は文字として扱わない
_ALT_IGNORE = re.compile(r"^\d+$")


def cell_text(cell) -> str:
    """セルの表示文字列。ボタン等のノイズを除去する。

    実サイトは「あり／なし」を画像で表示している箇所がある。
      <td><img alt="あり" src="ico_jigyosho_ari.gif"></td>
    文字を拾うだけでは空になるため、画像の alt も文字として読む。
    """
    for img in cell.find_all("img"):
        alt = (img.get("alt") or "").strip()
        if alt and not _ALT_IGNORE.match(alt) and not any(n in alt for n in NOISE):
            img.replace_with(alt)
        else:
            img.replace_with("")
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


# サイト共通の見出し（事業所名ではない）
_CHROME = re.compile(
    r"(介護サービス情報公表システム|公表システム|生活関連情報|介護事業所検索|"
    r"検索結果|都道府県|全国版トップ)"
)
# サービス種別名そのものは事業所名ではない（完全一致のときだけ除外する。
# 「居宅介護支援事業所がじゅまる」のような正当な名称は残す）
_SERVICE_LABELS = {
    "居宅介護支援", "訪問看護", "訪問介護", "訪問入浴介護", "訪問リハビリテーション",
    "通所介護", "通所リハビリテーション", "短期入所生活介護", "福祉用具貸与",
    "介護老人福祉施設", "介護老人保健施設", "認知症対応型共同生活介護",
    "小規模多機能型居宅介護", "定期巡回・随時対応型訪問介護看護", "予防",
}


def _looks_like_name(t: str) -> bool:
    return bool(t) and 2 <= len(t) <= 60 and t not in _SERVICE_LABELS and not _CHROME.search(t)


def main_heading(html: str) -> str:
    """事業所名を取り出す。

    一覧のリンク文字が「情報を選択して概要を見る」のような操作案内で
    事業所名になっていないことがあるため、次の順で探す。
      1. 事業所名を表すことが明らかな要素（class に jigyosyoName 等）
      2. 見出し（h1〜h3）
      3. class に name / title を含む要素
    """
    soup = BeautifulSoup(html, "html.parser")
    for el in soup.find_all(attrs={"class": re.compile(r"jigyosyo.?name", re.I)}):
        t = cell_text(el)
        if _looks_like_name(t):
            return t
    for tag in ("h1", "h2", "h3"):
        for el in soup.find_all(tag):
            t = cell_text(el)
            if _looks_like_name(t):
                return t
    for el in soup.find_all(attrs={"class": re.compile(r"(name|title)", re.I)}):
        t = cell_text(el)
        if _looks_like_name(t):
            return t
    return ""


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

_EMPTY_TIME = re.compile(r"^[時分:：～~\-\s　]*$")


def _is_closed_time(v: str) -> bool:
    """営業時間が「休み」を意味するかどうか。

    実サイトでは「－」のほか「0：00～0：00」「0：～0：」のように
    すべて0で休みを表している事業所がある。
    """
    s = unicodedata.normalize("NFKC", v or "").strip()
    if _EMPTY_TIME.match(s):
        return True
    nums = re.findall(r"\d+", s)
    return bool(nums) and all(int(n) == 0 for n in nums)


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


def _clean_addr(v: str, pref: str = "", city: str = "") -> str:
    """〒を除き、都道府県名・市区町村名が欠けていれば補う。

    公表システムの住所は市区町村名が省かれていることがある
    （例: 「〒662-0916　津門稲荷町5-13」）。
    """
    s = re.sub(r"〒\s*\d{3}-?\d{4}", "", v or "")
    s = s.replace("　", " ")
    s = re.sub(r"\s+", "", s).strip()
    if not s:
        return s
    if city and city not in s:
        tail = re.search(r"([^市]+区)$", city)     # 神戸市中央区 → 中央区
        if tail and s.startswith(tail.group(1)):
            s = city[: -len(tail.group(1))] + s   # 「中央区…」→「神戸市中央区…」
        else:
            s = city + s
    if pref and not s.startswith(pref):
        s = pref + s
    return s


# あり／なしを表す言い回し。これ以外の値は「解釈できなかった」として扱う。
# 「1」「0」のような数値は含めない。意味が確かめられていない値を
# あり／なしに読み替えると、誤ったデータを正しい顔で出してしまう。
_YES = ("あり", "有", "有り", "○", "◯", "●", "算定している", "対応している", "実施している")
_NO = ("なし", "無", "無し", "×", "✕", "－", "-", "算定していない", "対応していない",
       "実施していない", "非該当", "該当なし")


def _yesno(v: str):
    """あり／なしの列の値を正規化する。

    解釈できない値（事業所のPR文など）は None を返し、列を空欄にする。
    見出しの探索を緩くしている都合上、無関係な文章を拾うことがあるが、
    それを「あり／なし」の列にそのまま出すと、空欄よりも悪い誤りになる。
    """
    s = norm_label(v or "")
    if not s:
        return ""
    if s in _YES or s.startswith("あり"):
        return "あり"
    if s in _NO or s.startswith("なし"):
        return "なし"
    # 数値を「あり／なし」に読み替えることはしない。
    # 実サイトの「前年同月の提供実績」欄に入っていたのは「10人」という
    # 利用者数であり、算定の有無ではなかった。数値を機械的に
    # あり／なしへ変換すると、全区分が「あり」になる誤りが出る。
    if len(s) > 12:
        log.debug("あり／なしとして解釈できない値のため空欄にしました: %s", s[:40])
        return None
    return None


def apply_transform(value: str, transform: str, ctx: dict, normalize: bool):
    v = (value or "").strip()
    if transform == "int":
        return _to_int(v)
    if transform == "date":
        return _to_date(v) if normalize else v
    if transform == "time":
        if normalize and _is_closed_time(v):
            return ""
        return v
    if transform == "addr":
        if not normalize:
            return v
        return _clean_addr(v, ctx.get("pref", ""), ctx.get("city", ""))
    if transform == "yesno":
        if not normalize:
            return v
        got = _yesno(v)
        return "" if got is None else got
    if transform == "space":
        return re.sub(r"[ \t]{2,}", " ", v).strip()
    if transform == "trim":
        return v
    return v


def lookup_value(lookup: str, h: Harvest, ctx: dict) -> Optional[str]:
    """1つの lookup 指定（ctx: / kv: / re: / matrix:）を解決する。"""
    if lookup.startswith("ctx:"):
        return ctx.get(lookup[4:].strip())
    if lookup.startswith("kv:"):
        return h.kv.get(norm_label(lookup[3:]))
    if lookup.startswith("re:"):
        # 見出し語のゆれを正規表現で吸収する（正規化後の見出しに対して照合）
        try:
            pat = re.compile(lookup[3:].strip())
        except re.error:
            return None
        for k in sorted(h.kv):
            if pat.search(k):
                return h.kv[k]
        # 行列からも拾うが、見出しが一致しただけで隣の長文を持ってこないよう、
        # 値が短いもの（あり／なし等）に限る
        for (a, b), v in sorted(h.matrix.items()):
            if (pat.search(a) or pat.search(b)) and len(v) <= 12:
                return v
        return None
    if lookup.startswith("inval:"):
        # 「特定事業所加算 → Ⅱ」のように、値の側に区分が書かれている形
        body = lookup[6:]
        if "/" not in body:
            return None
        keypat, token = body.rsplit("/", 1)
        try:
            pat = re.compile(keypat)
        except re.error:
            return None
        for k in sorted(h.kv):
            if pat.search(k):
                raw = unicodedata.normalize("NFKC", h.kv[k])
                parts = [p for p in re.split(r"[、,，・/／\s()（）:：]+", raw) if p]
                return "あり" if token in parts else "なし"
        return None
    if lookup.startswith("matrix:"):
        body = lookup[7:]
        if "/" not in body:
            return None
        a, b = body.split("/", 1)
        return h.matrix.get((norm_label(a), norm_label(b)))
    # 接頭辞なしは kv 扱い
    return h.kv.get(norm_label(lookup))


def build_row(fields, h: Harvest, ctx: dict, normalize: bool = True,
              found: Optional[set] = None, rejected: Optional[set] = None) -> dict:
    """項目定義に従って1行ぶんの辞書を作る。

    found を渡すと、ページ上で見出しが見つかった列名を追加する。
    「整形した結果たまたま空欄」（営業時間の『時分～時分』など）と
    「そもそも見出しが無い」（サイト構成の変更）を区別するために使う。

    rejected を渡すと、「見出しは見つかったが、値として使えなかった」列名を
    追加する。あり／なしの列に事業所のPR文が入っていた事例のように、
    見つかってはいるが別の項目を拾っている場合を検知するために必要。
    found だけだと、この状態が「取得できている」と誤って扱われる。
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
        value = apply_transform(raw, fd.transform, ctx, normalize)
        if (raw != "" and value in (None, "") and fd.transform == "yesno"
                and rejected is not None):
            rejected.add(fd.column)
        row[fd.column] = value
    return row


JIGYOSYO_CD_RE = re.compile(r"JigyosyoCd=([0-9A-Za-z\-]+)", re.I)
DETAIL_HREF_RE = re.compile(r"action_kouhyou_detail", re.I)


def listing_rows(html: str) -> Dict[str, str]:
    """検索結果ページを、事業所1件ごとのHTML断片に切り分ける。

    実サイトの検索結果には、事業所名・所在地・電話番号・サービス提供地域・
    営業時間・定休日が既に載っている。詳細ページを開かなくてもこれらが
    取れるので、1件ぶんのまとまりを切り出して抽出に回す。

    クラス名やDOM構造には依存せず、「事業所番号が1件だけ含まれる最大の
    かたまり」を1件ぶんとみなす。

    先に全リンクの祖先をたどって「その要素の下にある事業所番号」を数えておく。
    祖先ごとにHTMLを文字列化して数える実装だと、1ページ50件で件数の二乗に
    比例して遅くなる（実測 50件で1.3秒、100件で4.5秒）ため。
    """
    soup = BeautifulSoup(html, "html.parser")
    anchors = []
    for a in soup.find_all("a", href=True):
        href = unquote(a["href"])
        if not DETAIL_HREF_RE.search(href):
            continue
        m = JIGYOSYO_CD_RE.search(href)
        if m:
            anchors.append((a, m.group(1)))

    # 各要素の下に何種類の事業所番号があるか（2種類見つかった時点で打ち切り）
    codes_under: Dict[int, set] = {}
    for a, cd in anchors:
        node = a
        while node is not None:
            got = codes_under.setdefault(id(node), set())
            if len(got) < 2:
                got.add(cd)
            node = node.parent

    out: Dict[str, str] = {}
    for a, cd in anchors:
        if cd in out:
            continue
        best = a
        node = a.parent
        while node is not None:
            if codes_under.get(id(node), set()) != {cd}:
                break
            best = node
            node = node.parent
        out[cd] = str(best)
    return out


TOTAL_COUNT_CLASS = re.compile(r"(alldatanum|totalnum|resultnum|hitnum|kensucount)", re.I)
TOTAL_COUNT_TEXT = re.compile(r"(?:検索結果|該当|全)\s*([\d,]+)\s*件")


def total_on_page(html: str) -> Optional[int]:
    """検索結果ページが表示している総件数を読む。

    取得件数と突き合わせて、ページ送りの取りこぼしを検知するために使う。
    読めなければ None を返す（誤検知を出さないため、推測はしない）。
    """
    soup = BeautifulSoup(html, "html.parser")
    for el in soup.find_all(attrs={"class": TOTAL_COUNT_CLASS}):
        m = re.search(r"([\d,]+)", cell_text(el))
        if m:
            return int(m.group(1).replace(",", ""))
    for el in soup.find_all(["select", "option", "button"]):
        el.extract()          # 表示件数の選択肢や「0件」ボタンを数えないように
    m = TOTAL_COUNT_TEXT.search(soup.get_text(" ", strip=True))
    return int(m.group(1).replace(",", "")) if m else None


# 一覧のリンク文字が事業所名ではなく操作案内のことがある
GENERIC_LINK_TEXT = re.compile(
    r"(情報を選択|概要を見る|詳細を見る|詳細情報|詳細はこちら|この事業所|選択して|表示する|比較)"
)


def listing_name(row_html: str, jigyosyo_cd: str = "") -> str:
    """検索結果1件ぶんのHTMLから事業所名を取り出す。

    見出し（実サイトは class="jigyosyoName"）を優先し、無ければ
    詳細ページへのリンク文字を使う。リンク文字が「詳細情報を見る」の
    ような操作案内の場合は名前として採用しない。
    """
    name = main_heading(row_html)
    if name:
        return name
    soup = BeautifulSoup(row_html, "html.parser")
    for a in soup.find_all("a", href=True):
        if not DETAIL_HREF_RE.search(unquote(a["href"])):
            continue
        if jigyosyo_cd and jigyosyo_cd not in unquote(a["href"]):
            continue
        t = cell_text(a)
        if t and not GENERIC_LINK_TEXT.search(t):
            return t
    return ""


def detail_links(html: str, jigyosyo_cd: str = "") -> List[str]:
    """HTML断片に含まれる詳細ページへのリンクを、出現順に返す。

    実サイトの検索結果1件には「情報を選択して概要を見る」と
    「詳細情報を見る」の2つのリンクがあり、従業者数や加算の情報は
    後者の側にある。どちらも開く必要がある。
    """
    soup = BeautifulSoup(html, "html.parser")
    out: List[str] = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if not DETAIL_HREF_RE.search(href):
            continue
        if jigyosyo_cd and jigyosyo_cd not in unquote(href):
            continue
        if href not in out:
            out.append(href)
    return out


def harvest_pages(pages: List[str]):
    """詳細ページ（全タブ）から索引と事業所名の見出しをまとめて作る。

    main.py とテストで同じ処理を使うための入口。
    """
    h = Harvest()
    heading = ""
    for n, html in enumerate(pages):
        h.merge(harvest_html(html))
        if n == 0:
            heading = main_heading(html)
    return h, heading


def missing_columns(row: dict, fields) -> List[str]:
    """値が取れなかった列名（サイト構成変更の検知用）。"""
    return [fd.column for fd in fields if row.get(fd.column) in (None, "")]

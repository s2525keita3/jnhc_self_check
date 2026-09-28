"""公的データのダウンロード。

使い方:
    python fetch.py                 # 各配布ページから最新ファイルを取得
    python fetch.py --wayback       # 厚生局名簿の過去版を Internet Archive から取得（生存曲線用）

配布ページの構成が変わって自動取得できないときは、ブラウザでDLして
data/raw/<ソースのdir>/ に置けば build.py はそのまま動く。
厚生局名簿は「YYYYMM_任意名.xlsx」の名前で置くと月次スナップショットとして扱われる。
"""

from __future__ import annotations

import argparse
import re
import time
from datetime import date
from pathlib import Path
from urllib.parse import urljoin

import requests

from config import RAW_DIR, SOURCES

UA = {"User-Agent": "Mozilla/5.0 (area-analysis research; contact: owner)"}
WAIT = 2.0  # 配布元に負荷をかけないよう、1リクエストごとに待つ秒数

# ソースごとの「欲しいファイル」判定（リンク文字列 or URL にこれが含まれる）
LINK_FILTERS = {
    "kaigo_opendata": ["訪問看護", "居宅介護支援", "地域包括", "jigyosho_130", "jigyosho_430"],
    "kouseikyoku_houkan": ["訪問看護", "houmonkango", "kanagawa", "神奈川"],
    "iryou_opendata": ["病院", "診療所", "hospital", "clinic", "facility"],
    "shougai_opendata": ["相談支援", "keikaku", "soudan"],
}
FILE_RE = re.compile(r'href="([^"]+\.(?:csv|xlsx|xls|zip))"[^>]*>(.*?)</a>', re.I | re.S)


def get(url: str) -> requests.Response:
    r = requests.get(url, headers=UA, timeout=60)
    r.raise_for_status()
    time.sleep(WAIT)
    return r


def list_links(index_url: str) -> list[tuple[str, str]]:
    html = get(index_url).content.decode("utf-8", errors="ignore")
    return [(urljoin(index_url, href), re.sub(r"<[^>]+>", "", text).strip())
            for href, text in FILE_RE.findall(html)]


def fetch_latest(key: str) -> None:
    src = SOURCES[key]
    out = RAW_DIR / src["dir"]
    out.mkdir(parents=True, exist_ok=True)
    stamp = date.today().strftime("%Y%m")
    try:
        links = list_links(src["index_url"])
    except requests.RequestException as e:
        print(f"[{key}] 配布ページを取得できません: {e}\n  → 手動で {src['index_url']} からDLし {out}/ に置いてください")
        return
    wanted = [(u, t) for u, t in links if any(k.lower() in (u + t).lower() for k in LINK_FILTERS[key])]
    if not wanted:
        print(f"[{key}] 対象リンクが見つかりません（ページ構成が変わった可能性）。候補: {len(links)}件")
    for url, text in wanted:
        name = f"{stamp}_{Path(url).name}"
        dest = out / name
        if dest.exists():
            continue
        print(f"[{key}] {text or url} → {dest.name}")
        dest.write_bytes(get(url).content)
        if dest.suffix == ".zip":
            _unzip(dest, stamp)


def _unzip(path: Path, stamp: str) -> None:
    import zipfile
    with zipfile.ZipFile(path) as z:
        for info in z.infolist():
            if info.is_dir():
                continue
            try:  # 日本語ファイル名は cp437 で入っていることが多い
                fname = info.filename.encode("cp437").decode("cp932")
            except (UnicodeEncodeError, UnicodeDecodeError):
                fname = info.filename
            (path.parent / f"{stamp}_{Path(fname).name}").write_bytes(z.read(info))


def fetch_wayback(url: str, dest_dir: Path, since: str = "2015") -> None:
    """Internet Archive に保存された過去版を月1本ずつ取得する。"""
    dest_dir.mkdir(parents=True, exist_ok=True)
    cdx = ("https://web.archive.org/cdx/search/cdx?output=json&filter=statuscode:200"
           f"&collapse=timestamp:6&from={since}&url={url}")
    rows = get(cdx).json()[1:]
    print(f"過去版 {len(rows)} 件: {url}")
    for row in rows:
        ts, original = row[1], row[2]
        dest = dest_dir / f"{ts[:6]}_{Path(original).name}"
        if dest.exists():
            continue
        try:
            dest.write_bytes(get(f"https://web.archive.org/web/{ts}id_/{original}").content)
            print(f"  {dest.name}")
        except requests.RequestException as e:
            print(f"  失敗 {ts}: {e}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", choices=list(SOURCES), help="1ソースだけ取得")
    ap.add_argument("--wayback", metavar="FILE_URL",
                    help="厚生局名簿など、ファイルURLの過去版を Internet Archive から取得")
    args = ap.parse_args()
    if args.wayback:
        fetch_wayback(args.wayback, RAW_DIR / SOURCES["kouseikyoku_houkan"]["dir"])
        return
    for key in [args.only] if args.only else SOURCES:
        fetch_latest(key)


if __name__ == "__main__":
    main()

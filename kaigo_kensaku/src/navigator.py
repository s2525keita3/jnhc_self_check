"""介護サービス情報公表システムのブラウザ操作。

要素の特定は「画面に見えている文字」で行う。id/class に依存しないため、
サイトの改修に比較的強い。うまく動かない場合は settings.ini の
dump_html = True にすると logs/html/ に各ページのHTMLが残るので、
そこから NAV の候補文言を追加すれば対応できる。
"""
from __future__ import annotations

import logging
import os
import re
import time
import urllib.parse
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional

from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

log = logging.getLogger(__name__)

BASE_URL = "https://www.kaigokensaku.mhlw.go.jp/{code}/"

# 画面遷移に使うリンク・ボタンの候補文言（上から順に試す）
NAV = {
    "to_search": ["介護事業所検索", "事業所を検索する", "事業所検索", "サービスから探す", "地域から探す"],
    "search_button": ["検索する", "検索", "この条件で検索", "上記の条件で検索"],
    "next_page": ["次へ", "次の10件", "次のページ", "次へ >", ">"],
    "detail_tabs": ["事業所の概要", "事業所の特色", "事業所の詳細", "運営状況", "その他"],
}

DETAIL_HREF = re.compile(r"action_kouhyou_detail", re.I)
JIGYOSYO_CD = re.compile(r"JigyosyoCd=([0-9A-Za-z\-]+)", re.I)


@dataclass
class Listing:
    name: str
    url: str
    jigyosyo_cd: str


class SiteError(RuntimeError):
    pass


class Navigator:
    def __init__(self, pref: str, pref_code: str, display: bool, wait: float,
                 retry: int, dump_dir: Optional[str] = None):
        self.pref = pref
        self.pref_code = pref_code
        self.wait_sec = wait
        self.retry = retry
        self.dump_dir = dump_dir
        self.driver = self._start(display)
        self._dump_no = 0

    # ---------------------------------------------------------------- driver
    def _start(self, display: bool):
        opts = Options()
        if not display:
            opts.add_argument("--headless=new")
        opts.add_argument("--window-size=1400,1000")
        opts.add_argument("--disable-gpu")
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-dev-shm-usage")
        opts.add_argument("--lang=ja-JP")
        opts.add_experimental_option("excludeSwitches", ["enable-logging"])
        driver = webdriver.Chrome(options=opts)
        driver.set_page_load_timeout(60)
        return driver

    def close(self):
        try:
            self.driver.quit()
        except Exception:
            pass

    # ----------------------------------------------------------------- utils
    def _sleep(self):
        if self.wait_sec > 0:
            time.sleep(self.wait_sec)

    def _retry(self, fn: Callable, what: str):
        last = None
        for i in range(max(1, self.retry)):
            try:
                return fn()
            except WebDriverException as e:
                last = e
                log.warning("%s に失敗（%d回目）: %s", what, i + 1, type(e).__name__)
                time.sleep(2 ** i)
        raise SiteError(f"{what} に失敗しました: {last}")

    def get(self, url: str):
        self._retry(lambda: self.driver.get(url), f"ページ取得({url})")
        self._sleep()
        self.dump(url)

    def dump(self, tag: str = ""):
        if not self.dump_dir:
            return
        os.makedirs(self.dump_dir, exist_ok=True)
        self._dump_no += 1
        safe = re.sub(r"[^\w\-]+", "_", tag)[:60]
        path = os.path.join(self.dump_dir, f"{self._dump_no:04d}_{safe}.html")
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self.driver.page_source)
        except Exception:
            pass

    @property
    def html(self) -> str:
        return self.driver.page_source

    def _click_text(self, candidates: List[str], required: bool = True) -> bool:
        """候補文言のいずれかを含むリンク/ボタンをクリックする。"""
        for text in candidates:
            xps = [
                f"//a[contains(normalize-space(.), '{text}')]",
                f"//button[contains(normalize-space(.), '{text}')]",
                f"//input[@type='submit' and contains(@value, '{text}')]",
                f"//input[@type='button' and contains(@value, '{text}')]",
            ]
            for xp in xps:
                els = [e for e in self.driver.find_elements(By.XPATH, xp) if e.is_displayed()]
                if els:
                    self.driver.execute_script("arguments[0].click();", els[0])
                    self._sleep()
                    self.dump(f"click_{text}")
                    return True
        if required:
            raise SiteError(f"クリック対象が見つかりません: {candidates}")
        return False

    def _check_label(self, text: str, exact: bool) -> bool:
        """ラベル文言に対応するチェックボックス/ラジオをONにする。"""
        if exact:
            cond = f"normalize-space(.)='{text}'"
        else:
            cond = f"contains(normalize-space(.), '{text}')"
        for el in self.driver.find_elements(By.XPATH, f"//label[{cond}]"):
            target = None
            for_id = el.get_attribute("for")
            if for_id:
                found = self.driver.find_elements(By.ID, for_id)
                target = found[0] if found else None
            if target is None:
                inner = el.find_elements(By.XPATH, ".//input[@type='checkbox' or @type='radio']")
                target = inner[0] if inner else None
            if target is not None:
                if not target.is_selected():
                    self.driver.execute_script("arguments[0].click();", target)
                return True
        # label が無い作りの場合は value 属性で探す
        for el in self.driver.find_elements(
            By.XPATH, f"//input[(@type='checkbox' or @type='radio') and @value]"
        ):
            if text in (el.get_attribute("value") or ""):
                if not el.is_selected():
                    self.driver.execute_script("arguments[0].click();", el)
                return True
        return False

    # ------------------------------------------------------------ high level
    def open_search_screen(self):
        self.get(BASE_URL.format(code=self.pref_code))
        self._click_text(NAV["to_search"], required=False)

    def list_cities(self) -> List[str]:
        """検索画面に並んでいる市区町村名を取得する。"""
        self.open_search_screen()
        names = []
        for el in self.driver.find_elements(By.XPATH, "//label"):
            t = (el.text or "").strip()
            t = re.sub(r"\s*\(\d+\)\s*$", "", t)
            t = re.sub(r"\s*（\d+）\s*$", "", t)
            if re.search(r"(市|区|町|村)$", t) and 2 <= len(t) <= 12:
                names.append(t)
        seen, out = set(), []
        for n in names:
            if n not in seen:
                seen.add(n)
                out.append(n)
        log.debug("市区町村候補 %d件: %s", len(out), out[:10])
        return out

    def search(self, city: str, service_label: str, exact: bool = False) -> None:
        """市区町村とサービス種別を指定して検索を実行する。"""
        self.open_search_screen()
        if not self._check_label(city, exact):
            raise SiteError(f"市区町村『{city}』が検索画面で見つかりません")
        if not self._check_label(service_label, False):
            log.warning("サービス種別『%s』のチェックが見つかりません。全件検索のまま進みます", service_label)
        self._click_text(NAV["search_button"])
        try:
            WebDriverWait(self.driver, 30).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
        except Exception:
            pass
        self.dump(f"result_{city}_{service_label}")

    def collect_listings(self, max_pages: int = 200) -> List[Listing]:
        """検索結果一覧から、事業所名と詳細ページURLを集める（ページ送り対応）。"""
        found: Dict[str, Listing] = {}
        for page in range(max_pages):
            for a in self.driver.find_elements(By.XPATH, "//a[@href]"):
                href = a.get_attribute("href") or ""
                if not DETAIL_HREF.search(href):
                    continue
                name = (a.text or "").strip()
                if not name:
                    continue
                m = JIGYOSYO_CD.search(urllib.parse.unquote(href))
                cd = m.group(1) if m else href
                if cd not in found:
                    found[cd] = Listing(name=name, url=href, jigyosyo_cd=cd)
            if not self._click_text(NAV["next_page"], required=False):
                break
            log.debug("次ページへ (%d件取得済)", len(found))
        return list(found.values())

    def detail_pages(self, listing: Listing) -> List[str]:
        """詳細ページの各タブのHTMLを返す。"""
        pages = []
        self.get(listing.url)
        pages.append(self.html)
        tab_urls = []
        for a in self.driver.find_elements(By.XPATH, "//a[@href]"):
            t = (a.text or "").strip()
            href = a.get_attribute("href") or ""
            if t in NAV["detail_tabs"] and DETAIL_HREF.search(href) and href != listing.url:
                tab_urls.append(href)
        for url in dict.fromkeys(tab_urls):
            try:
                self.get(url)
                pages.append(self.html)
            except SiteError as e:
                log.warning("タブ取得失敗: %s", e)
        return pages

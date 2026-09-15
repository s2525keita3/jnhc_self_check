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
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select, WebDriverWait

from src.extract import detail_links, listing_rows

log = logging.getLogger(__name__)

BASE_URL = "https://www.kaigokensaku.mhlw.go.jp/{code}/"

# 画面遷移に使うリンク・ボタンの候補文言（上から順に試す）
# 実サイトの導線:
#   都道府県トップ →「介護事業所を検索する」→「詳しい条件で探す」
#   → サービスの選択 → 事業所の所在地選択 → 検索
NAV = {
    "to_search": [
        "介護事業所を検索する", "介護事業所検索", "事業所を検索する", "事業所検索",
        "サービスから探す", "地域から探す",
    ],
    "to_detail_search": [
        "詳しい条件で探す", "詳細条件で探す", "詳しい条件", "条件を指定して探す",
        "条件を選んで探す",
    ],
    "next_step": ["次へ進む", "次に進む", "この条件で次へ", "選択して次へ", "進む", "次へ"],
    "search_button": ["検索する", "検索", "この条件で検索", "上記の条件で検索"],
    "next_page": ["次へ", "次の10件", "次のページ", "次へ >", ">"],
    "detail_tabs": ["事業所の概要", "事業所の特色", "事業所の詳細", "運営状況", "その他"],
}

DETAIL_HREF = re.compile(r"action_kouhyou_detail", re.I)
# たどってはいけないリンク（PDF等のファイル、メール、JavaScript）
SKIP_HREF = re.compile(
    r"(\.pdf|\.xlsx?|\.docx?|\.zip|\.csv|\.jpe?g|\.png|\.gif)(\?|$)|^mailto:|^tel:|^javascript:",
    re.I,
)
# 検索画面ではないと分かる文言
SKIP_TEXT = re.compile(
    r"(パンフレット|読み解き方|使い方|ご利用にあたって|アンケート|リンク集|サイトマップ|"
    r"個人情報|著作権|お問い合わせ|よくある|PDF|概算|試算|料金)"
)
JIGYOSYO_CD = re.compile(r"JigyosyoCd=([0-9A-Za-z\-]+)", re.I)
# 一覧のリンク文字が事業所名ではなく操作案内のことがある
GENERIC_LINK = re.compile(
    r"(情報を選択|概要を見る|詳細を見る|詳細はこちら|この事業所|選択して|表示する|比較)"
)


@dataclass
class Listing:
    name: str
    url: str
    jigyosyo_cd: str
    row_html: str = ""      # 検索結果ページの、その事業所1件ぶんのHTML
    extra_urls: List[str] = field(default_factory=list)   # 「詳細情報を見る」等


class SiteError(RuntimeError):
    pass


class Navigator:
    def __init__(self, pref: str, pref_code: str, display: bool, wait: float,
                 retry: int, dump_dir: Optional[str] = None,
                 base_url: Optional[str] = None):
        self.pref = pref
        self.pref_code = pref_code
        self.base_url = base_url or os.environ.get("KAIGO_BASE_URL") or BASE_URL
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
        # テスト環境向けの差し替え（通常は未設定でよい）
        binary = os.environ.get("KAIGO_CHROME_BINARY")
        if binary:
            opts.binary_location = binary
        driver_path = os.environ.get("KAIGO_CHROMEDRIVER")
        if driver_path:
            driver = webdriver.Chrome(service=Service(driver_path), options=opts)
        else:
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

    # ------------------------------------------------------------ 選択部品
    @staticmethod
    def _clean(t: str) -> str:
        """『西宮市 (123)』→『西宮市』のように件数表記を落とす。"""
        t = (t or "").strip()
        t = re.sub(r"[\s　]*[（(]\s*\d+\s*[)）]\s*$", "", t)
        return t.strip()

    def _match(self, text: str, target: str, exact: bool) -> bool:
        t = self._clean(text)
        return t == target if exact else (target in t)

    def _in_frames(self, fn):
        """現在の文書で fn を試し、駄目ならフレームの中も順に試す。

        フレーム内で見つかった場合は、そのフレームに入ったままにする
        （続けて行うサービス選択や検索ボタン押下も同じフレームで行うため）。
        """
        r = fn()
        if r:
            return r
        n = len(self.driver.find_elements(By.XPATH, "//iframe|//frame"))
        for i in range(n):
            try:
                self.driver.switch_to.default_content()
                frames = self.driver.find_elements(By.XPATH, "//iframe|//frame")
                if i >= len(frames):
                    break
                self.driver.switch_to.frame(frames[i])
                r = fn()
                if r:
                    log.debug("フレーム %d 内で見つかりました", i)
                    return r
            except WebDriverException:
                continue
        try:
            self.driver.switch_to.default_content()
        except WebDriverException:
            pass
        return None

    def _pick(self, target: str, exact: bool = False,
              allow_text: bool = False) -> Optional[str]:
        """画面（フレーム内を含む）から『target』を選ぶ。"""
        return self._in_frames(lambda: self._pick_here(target, exact, allow_text))

    def _pick_here(self, target: str, exact: bool = False,
                   allow_text: bool = False) -> Optional[str]:
        """画面上の『target』を選ぶ。

        チェックボックス → プルダウン →（allow_text なら）文字入力欄 → リンク
        の順に試す。戻り値は選択できた部品の種類。見つからなければ None。

        allow_text は市区町村を選ぶときだけ True にする。サービス種別で許すと、
        市区町村の入力欄にサービス名を上書きしてしまうため。
        """
        if self._check_label(target, exact):
            return "checkbox"

        for sel in self.driver.find_elements(By.TAG_NAME, "select"):
            if not sel.is_displayed():
                continue
            for opt in sel.find_elements(By.TAG_NAME, "option"):
                if self._match(opt.text, target, exact):
                    try:
                        Select(sel).select_by_visible_text(opt.text)
                        self._sleep()
                        return "select"
                    except WebDriverException:
                        pass

        if allow_text:
            kind = self._fill_textbox(target)
            if kind:
                return kind

        for strict in (True, False):
            if strict is False and exact:
                break
            for a in self.driver.find_elements(By.XPATH, "//a[@href]"):
                try:
                    if not a.is_displayed():
                        continue
                    if self._match(a.text, target, exact or strict):
                        self.driver.execute_script("arguments[0].click();", a)
                        self._sleep()
                        self.dump(f"link_{target}")
                        return "link"
                except WebDriverException:
                    continue
        return None

    def _fill_textbox(self, target: str) -> Optional[str]:
        """『市区町村』などの文字入力欄があれば、そこに入力する。"""
        pat = re.compile(r"(市区町村|市町村|地域|所在地|住所|エリア)")
        for el in self.driver.find_elements(By.XPATH, "//input[@type='text' or not(@type)]"):
            try:
                if not el.is_displayed() or not el.is_enabled():
                    continue
                hint = " ".join(
                    filter(None, [
                        el.get_attribute("name"), el.get_attribute("id"),
                        el.get_attribute("placeholder"), el.get_attribute("title"),
                        el.get_attribute("aria-label"),
                    ])
                )
                label_id = el.get_attribute("id")
                if label_id:
                    for lb in self.driver.find_elements(
                        By.XPATH, f"//label[@for='{label_id}']"
                    ):
                        hint += " " + (lb.text or "")
                if not pat.search(hint):
                    continue
                el.clear()
                el.send_keys(target)
                self._sleep()
                log.debug("文字入力欄に『%s』を入力（%s）", target, hint.strip()[:40])
                return "textbox"
            except WebDriverException:
                continue
        return None

    def _candidate_links(self) -> List[str]:
        """市区町村の選択画面へ続きそうなリンクのURLを集める。

        PDF等のファイルや、都道府県ページの外に出るリンクはたどらない。
        """
        root = self.base_url.format(code=self.pref_code)
        out = []
        for a in self.driver.find_elements(By.XPATH, "//a[@href]"):
            try:
                t = self._clean(a.text)
                href = a.get_attribute("href") or ""
            except WebDriverException:
                continue
            if not t or not href.startswith(root):
                continue          # 都道府県ページ配下から出ない
            if SKIP_HREF.search(href) or SKIP_TEXT.search(t):
                continue          # PDF・案内ページ等は対象外
            if re.search(r"(検索|探す|事業所|サービス|地域|市区町村|エリア)", t):
                out.append(href)
        return list(dict.fromkeys(out))

    def _explore(self, fn, depth: int = 2, limit: int = 8):
        """今の画面で fn を試し、駄目なら関連リンクを depth 段までたどって探す。"""
        r = fn()
        if r:
            return r
        seen = set()
        frontier = self._candidate_links()
        for _ in range(depth):
            nxt = []
            for url in frontier[:limit]:
                if url in seen:
                    continue
                seen.add(url)
                try:
                    self.get(url)
                except SiteError:
                    continue
                r = fn()
                if r:
                    log.info("目的の画面: %s", url)
                    return r
                nxt.extend(self._candidate_links())
            frontier = [u for u in nxt if u not in seen]
            if not frontier:
                break
        return None

    def _find_city(self, city: str, exact: bool) -> Optional[str]:
        """市区町村を選べる画面を探してたどり着き、選択する。

        トップ→検索画面が1クリックとは限らないため、それらしいリンクを
        たどって探す。
        """
        self.get(self.base_url.format(code=self.pref_code))
        kind = self._pick(city, exact, allow_text=True)
        if kind:
            return kind

        self._click_text(NAV["to_search"], required=False)
        self._click_text(NAV["to_detail_search"], required=False)
        return self._explore(lambda: self._pick(city, exact, allow_text=True))

    # ------------------------------------------------------------ high level
    def open_search_screen(self):
        self.get(self.base_url.format(code=self.pref_code))
        self._click_text(NAV["to_search"], required=False)

    def describe_page(self) -> str:
        """今開いている画面の作りを文章で書き出す（診断用）。"""
        d = self.driver
        out = [f"URL   : {d.current_url}", f"title : {d.title}"]

        labels = [self._clean(e.text) for e in d.find_elements(By.XPATH, "//label")]
        labels = [t for t in labels if t]
        out.append(f"\n■ label要素 {len(labels)}個")
        out.append("  " + " / ".join(labels[:60]) if labels else "  （なし）")

        sels = d.find_elements(By.TAG_NAME, "select")
        out.append(f"\n■ プルダウン {len(sels)}個")
        for sel in sels[:6]:
            opts = [self._clean(o.text) for o in sel.find_elements(By.TAG_NAME, "option")]
            opts = [o for o in opts if o]
            out.append(f"  name={sel.get_attribute('name')} 選択肢{len(opts)}個: "
                       + " / ".join(opts[:30]))

        inputs = d.find_elements(By.XPATH, "//input[@type='checkbox' or @type='radio']")
        out.append(f"\n■ チェックボックス/ラジオ {len(inputs)}個")
        for el in inputs[:30]:
            out.append(f"  type={el.get_attribute('type')} name={el.get_attribute('name')} "
                       f"value={el.get_attribute('value')} id={el.get_attribute('id')}")

        links = []
        for a in d.find_elements(By.XPATH, "//a[@href]"):
            t = self._clean(a.text)
            if t:
                links.append(t)
        out.append(f"\n■ リンク {len(links)}個")
        out.append("  " + " / ".join(links[:80]))

        texts = d.find_elements(By.XPATH, "//input[@type='text' or not(@type)]")
        out.append(f"\n■ 文字入力欄 {len(texts)}個")
        for el in texts[:15]:
            out.append(f"  name={el.get_attribute('name')} id={el.get_attribute('id')} "
                       f"placeholder={el.get_attribute('placeholder')}")

        frames = d.find_elements(By.XPATH, "//iframe|//frame")
        out.append(f"\n■ フレーム {len(frames)}個")
        for fr in frames[:8]:
            out.append(f"  name={fr.get_attribute('name')} src={fr.get_attribute('src')}")

        btns = []
        for xp in ("//button", "//input[@type='submit']", "//input[@type='button']"):
            for e in d.find_elements(By.XPATH, xp):
                t = self._clean(e.text) or (e.get_attribute("value") or "").strip()
                if t:
                    btns.append(t)
        out.append(f"\n■ ボタン {len(btns)}個")
        out.append("  " + " / ".join(btns[:40]))

        # フレームの中身も1段だけ覗く
        for i in range(len(frames)):
            try:
                d.switch_to.default_content()
                fs = d.find_elements(By.XPATH, "//iframe|//frame")
                if i >= len(fs):
                    break
                d.switch_to.frame(fs[i])
                labels_f = [self._clean(e.text) for e in d.find_elements(By.XPATH, "//label")]
                links_f = [self._clean(e.text) for e in d.find_elements(By.XPATH, "//a[@href]")]
                out.append(f"\n■ フレーム{i} の中身: "
                           f"label {len([x for x in labels_f if x])}個 / "
                           f"リンク {len([x for x in links_f if x])}個")
                out.append("  " + " / ".join([x for x in (labels_f + links_f) if x][:40]))
            except WebDriverException:
                continue
        try:
            d.switch_to.default_content()
        except WebDriverException:
            pass
        return "\n".join(out)

    def _city_texts_here(self) -> List[str]:
        texts = []
        for xp in ("//label", "//option", "//a[@href]"):
            for el in self.driver.find_elements(By.XPATH, xp):
                try:
                    texts.append(self._clean(el.text))
                except WebDriverException:
                    continue
        return texts

    @staticmethod
    def _city_names(texts: List[str]) -> List[str]:
        names = [
            t for t in texts
            if t and re.search(r"(市|区|町|村)$", t) and 2 <= len(t) <= 12
        ]
        seen, out = set(), []
        for n in names:
            if n not in seen:
                seen.add(n)
                out.append(n)
        return out

    def _harvest_cities(self) -> List[str]:
        """今の画面（フレーム内を含む）から市区町村名を集める。"""
        names = self._city_names(self._city_texts_here())
        if names:
            return names
        collected: List[str] = []

        def grab():
            found = self._city_names(self._city_texts_here())
            if found:
                collected.extend(found)
                return True
            return False

        self._in_frames(grab)
        return self._city_names(collected)

    def list_cities(self, service_label: Optional[str] = None) -> List[str]:
        """市区町村名の一覧を取得する。

        実サイトではサービスを選ぶまで所在地の選択肢が現れないため、
        必要ならサービスを選んでから集める。
        """
        self.get(self.base_url.format(code=self.pref_code))
        self._click_text(NAV["to_search"], required=False)
        self._click_text(NAV["to_detail_search"], required=False)

        def try_here():
            found = self._harvest_cities()
            if found:
                return found
            if service_label and self._pick(service_label, False):
                if not self._click_text(NAV["next_step"], required=False):
                    self._click_text(NAV["search_button"], required=False)
                return self._harvest_cities()
            return None

        names = self._explore(try_here) or []
        log.debug("市区町村候補 %d件: %s", len(names), names[:20])
        return names

    def search(self, city: str, service_label: str, exact: bool = False) -> None:
        """サービス種別 → 市区町村 の順に選んで検索を実行する。

        実サイトは「詳しい条件で探す」→「サービスの選択」→「事業所の所在地選択」
        の順で、サービスを選ぶまで所在地の選択肢が現れない。この順序を既定とし、
        違う作りのサイトでも動くよう、駄目なら従来の探索に切り替える。
        """
        self.get(self.base_url.format(code=self.pref_code))
        self._click_text(NAV["to_search"], required=False)
        self._click_text(NAV["to_detail_search"], required=False)

        svc = self._pick(service_label, False)
        if svc:
            log.debug("サービス種別『%s』を %s で選択", service_label, svc)

        kind = self._pick(city, exact, allow_text=True)
        if kind is None and svc:
            # サービスを選ぶ画面と所在地を選ぶ画面が分かれている場合
            if not self._click_text(NAV["next_step"], required=False):
                self._click_text(NAV["search_button"], required=False)
            kind = self._pick(city, exact, allow_text=True)

        if kind is None:
            # 想定と異なる作りのとき: 市区町村を選べる画面を探し回る
            kind = self._find_city(city, exact)
            if kind is not None and svc is None:
                svc = self._pick(service_label, False)

        if kind is None:
            try:
                log.error("市区町村が見つからなかった画面の構造:\n%s", self.describe_page())
            except WebDriverException:
                pass
            raise SiteError(
                f"市区町村『{city}』を選べる画面が見つかりません"
                f"（最後に見た画面: {self.driver.current_url}）"
                "／『診断する.bat』で画面の作りを確認してください"
            )
        log.debug("市区町村『%s』を %s で選択", city, kind)
        if svc is None:
            # 市区町村を選んだ後の画面でサービスを選ばせる作りもある
            svc = self._pick(service_label, False)
            if svc:
                log.debug("サービス種別『%s』を %s で選択（所在地の後）", service_label, svc)
        if svc is None:
            log.warning("サービス種別『%s』が見つかりません。全件のまま進みます", service_label)

        if not (kind == "link" and svc is None):
            if not self._click_text(NAV["search_button"], required=False):
                self._in_frames(
                    lambda: self._click_text(NAV["search_button"], required=False)
                )
        try:
            WebDriverWait(self.driver, 30).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
        except Exception:
            pass
        self.dump(f"result_{city}_{service_label}")

    def set_page_size(self) -> None:
        """1ページの表示件数を最大にする（ページ送りの回数を減らす）。"""
        def pick_max():
            for sel in self.driver.find_elements(By.XPATH, "//select"):
                try:
                    if not sel.is_displayed():
                        continue
                    opts = sel.find_elements(By.TAG_NAME, "option")
                    nums = [
                        (int(re.sub(r"\D", "", o.text or "0") or 0), o)
                        for o in opts
                        if re.search(r"\d+\s*件", o.text or "")
                    ]
                    if not nums:
                        continue
                    n, opt = max(nums, key=lambda x: x[0])
                    if n <= 0:
                        continue
                    Select(sel).select_by_visible_text(opt.text)
                    self.driver.execute_script(
                        "arguments[0].dispatchEvent(new Event('change', {bubbles:true}));", sel
                    )
                    self._sleep()
                    log.debug("1ページの表示件数を %d件 に変更", n)
                    return True
                except WebDriverException:
                    continue
            return False

        # ここではフレームを渡り歩かない。検索を行った文書に留まる必要があり、
        # _in_frames は見つからなかったときに最上位文書へ戻してしまうため。
        pick_max()

    def collect_listings(self, max_pages: int = 200) -> List[Listing]:
        """検索結果一覧から、事業所名と詳細ページURLを集める（ページ送り対応）。

        検索結果ページには事業所名・所在地・電話番号・サービス提供地域・
        営業時間・定休日が載っているので、1件ぶんのHTMLも一緒に持ち帰る。
        """
        self.set_page_size()
        found: Dict[str, Listing] = {}
        prev = -1
        for page in range(max_pages):
            rows = listing_rows(self.html)
            for a in self.driver.find_elements(By.XPATH, "//a[@href]"):
                try:
                    href = a.get_attribute("href") or ""
                except WebDriverException:
                    continue
                if not DETAIL_HREF.search(href):
                    continue
                name = (a.text or "").strip()
                if GENERIC_LINK.search(name):
                    name = ""      # 事業所名は詳細ページの見出しから取る
                m = JIGYOSYO_CD.search(urllib.parse.unquote(href))
                cd = m.group(1) if m else href
                if cd not in found:
                    row = rows.get(cd, "")
                    extra = []
                    for u in detail_links(row, cd):
                        absu = urllib.parse.urljoin(self.driver.current_url, u)
                        if absu != href and absu not in extra:
                            extra.append(absu)
                    found[cd] = Listing(
                        name=name, url=href, jigyosyo_cd=cd,
                        row_html=row, extra_urls=extra,
                    )
            if len(found) == prev:
                # このページで1件も増えなかった＝同じページに留まっている
                log.debug("新規が無いためページ送りを打ち切り (%d件)", len(found))
                break
            prev = len(found)
            if not self._click_text(NAV["next_page"], required=False):
                break
            log.debug("次ページへ (%d件取得済)", len(found))
        return list(found.values())

    def _same_jigyosyo_links(self, listing: Listing) -> List[str]:
        """同じ事業所の別ページ（タブ）へのリンクURLを集める。

        タブの表示文字は当てにしない。`action_kouhyou_detail_*` を含み、
        同じ事業所番号を持つURLは、ほぼ間違いなくタブである。
        """
        urls = []
        for a in self.driver.find_elements(By.XPATH, "//a[@href]"):
            try:
                href = a.get_attribute("href") or ""
            except WebDriverException:
                continue
            if not href or not DETAIL_HREF.search(href):
                continue
            if href.rstrip("#") == listing.url.rstrip("#"):
                continue
            if listing.jigyosyo_cd and listing.jigyosyo_cd not in urllib.parse.unquote(href):
                continue
            urls.append(href)
        return list(dict.fromkeys(urls))

    def detail_pages(self, listing: Listing, max_tabs: int = 8) -> List[str]:
        """詳細ページの各タブのHTMLを返す。

        タブの作りはサイトによって違う（リンク・ボタン・JavaScript）ため、
        次の順で試す。
          1. 同じ事業所番号を持つ詳細URLへのリンクを開く（表示文字に依存しない）
          2. タブの表示文字をクリックする（リンクが無い作り向け）
        """
        pages = []
        self.get(listing.url)
        pages.append(self.html)

        # 検索結果にあった「詳細情報を見る」等のリンクを先に開く
        visited = {listing.url}
        for url in listing.extra_urls[:max_tabs]:
            if url in visited:
                continue
            visited.add(url)
            try:
                self.get(url)
                pages.append(self.html)
            except SiteError as e:
                log.warning("詳細ページ取得失敗: %s", e)

        tab_urls = [u for u in self._same_jigyosyo_links(listing) if u not in visited]
        if not tab_urls:
            tab_urls = self._in_frames(
                lambda: self._same_jigyosyo_links(listing) or None
            ) or []
        for url in tab_urls[:max_tabs]:
            try:
                self.get(url)
                pages.append(self.html)
            except SiteError as e:
                log.warning("タブ取得失敗: %s", e)

        if len(pages) == 1:
            # タブがリンクでない作り: 表示文字をクリックして移動する
            seen_urls = {self.driver.current_url}
            for label in NAV["detail_tabs"][1:]:
                moved = self._click_text([label], required=False)
                if not moved:
                    moved = bool(self._in_frames(
                        lambda lb=label: self._click_text([lb], required=False)
                    ))
                if moved and self.driver.current_url not in seen_urls:
                    seen_urls.add(self.driver.current_url)
                    pages.append(self.html)
        if len(pages) == 1:
            log.warning(
                "詳細ページのタブが見つかりません（%s）。"
                "『詳細ページを調べる.bat』で画面を確認してください", listing.url
            )
        return pages

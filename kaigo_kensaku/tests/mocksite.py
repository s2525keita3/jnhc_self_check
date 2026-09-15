"""テスト用の模擬サイト。

実サイトへアクセスできない環境でも、検索→一覧→ページ送り→詳細タブ→抽出
までの流れを本物のブラウザで検証するために使う。
市区町村の選ばせ方が異なる3パターンを用意している。

  variant "checkbox" : チェックボックスで市区町村とサービスを選び検索ボタン
  variant "link"     : 市区町村はリンク、次の画面でサービスを選び検索ボタン
  variant "select"   : プルダウンで市区町村とサービスを選び検索ボタン
  variant "deep"     : トップに「検索」リンクが無く、2階層たどらないと市区町村に届かない
  variant "deadnext" : 「次へ」が常に出るが同じページに戻る（無限ループ対策の確認用）
  variant "iframe"   : 検索フォームが iframe の中にある構成
  variant "pdftrap"  : トップにPDF等の紛らわしいリンクが並ぶ構成（誤追尾の確認用）
  variant "real"     : 実サイトの導線を再現した構成。
                       トップ →「介護事業所を検索する」→「詳しい条件で探す」
                       → サービスの選択 →（次へ進む）→ 事業所の所在地選択 → 検索。
                       サービスを選ぶまで所在地の選択肢は出ない。
  variant "textbox"  : 市区町村を文字で入力させる構成
  variant "textonly" : 市区町村は文字入力のみで、サービス種別を選ぶ部品が無い構成
"""
from __future__ import annotations

import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

CITIES = ["西宮市", "尼崎市", "芦屋市", "神戸市東灘区", "神戸市灘区", "神戸市中央区"]
SERVICES = ["居宅介護支援", "訪問看護", "訪問介護"]
PER_PAGE = 10


def counts(city: str, svc: str) -> int:
    return {("西宮市", "居宅介護支援"): 12}.get((city, svc), 3)


def cd_of(city: str, svc: str, i: int) -> str:
    return "28%04d%03d-%02d" % (CITIES.index(city) + 1, SERVICES.index(svc) + 1, i)


def name_of(city: str, svc: str, i: int) -> str:
    base = "ケアプランセンター" if svc == "居宅介護支援" else "訪問看護ステーション"
    return f"{base}{city}{i}"


def _page(body: str) -> bytes:
    return (
        "<html><head><meta charset='utf-8'><title>介護事業所・生活関連情報検索</title></head>"
        f"<body>{body}</body></html>"
    ).encode("utf-8")


def _overview(city: str, svc: str, i: int) -> str:
    return f"""
    <h1>{name_of(city, svc, i)}</h1>
    <table>
      <tr><th>介護サービスの種類</th><td>{svc}</td></tr>
      <tr><th>所在地</th><td>〒662-00{i:02d}　{city}松風町1-{i}
          <a href="https://maps.example.invalid/">地図を開く</a></td></tr>
      <tr><th>連絡先</th><td>Tel：0798-31-{1000+i}／Fax：0798-31-{2000+i}
          <a href="https://example.invalid/">ホームページを開く</a></td></tr>
      <tr><th>事業開始年月日</th><td>201{i % 10}年10月1日</td></tr>
      <tr><th>通常の事業の実施地域</th><td>{city}・芦屋市</td></tr>
    </table>
    <table>
      <tr><th rowspan="5">営業時間</th><th>&nbsp;</th><th>営業時間</th></tr>
      <tr><th>平日</th><td>8時30分～17時30分</td></tr>
      <tr><th>土曜</th><td>{'9時00分～12時00分' if i % 2 else '時分～時分'}</td></tr>
      <tr><th>日曜</th><td>時分～時分</td></tr>
      <tr><th>祝日</th><td>時分～時分</td></tr>
      <tr><th>定休日</th><td colspan="2">土・日、年始年末</td></tr>
    </table>"""


def _detail(city: str, svc: str, i: int) -> str:
    if svc == "居宅介護支援":
        staff = """
        <table>
          <tr><th>職種</th><th>常勤</th><th>非常勤</th></tr>
          <tr><th>介護支援専門員</th><td>%d人</td><td>%d人</td></tr>
          <tr><th>事務員</th><td>1人</td><td>0人</td></tr>
        </table>""" % (i % 5 + 1, i % 3)
        kasan = """
        <table>
          <tr><th>特定事業所加算（Ⅰ）</th><td>なし</td></tr>
          <tr><th>特定事業所加算（Ⅱ）</th><td>あり</td></tr>
          <tr><th>特定事業所加算（Ⅲ）</th><td>なし</td></tr>
          <tr><th>特定事業所加算（Ａ）</th><td>なし</td></tr>
        </table>"""
    else:
        staff = """
        <table>
          <tr><th>職種</th><th>常勤</th><th>非常勤</th></tr>
          <tr><th>保健師</th><td>1</td><td>0</td></tr>
          <tr><th>看護師</th><td>%d</td><td>3</td></tr>
          <tr><th>准看護師</th><td>0</td><td>1</td></tr>
          <tr><th>理学療法士</th><td>2</td><td>0</td></tr>
          <tr><th>作業療法士</th><td>1</td><td>0</td></tr>
          <tr><th>言語聴覚士</th><td>0</td><td>0</td></tr>
        </table>""" % (i % 6 + 2)
        kasan = """
        <table>
          <tr><th>緊急時訪問看護加算</th><td>あり</td></tr>
          <tr><th>特別管理加算</th><td>あり</td></tr>
          <tr><th>ターミナルケア加算</th><td>あり</td></tr>
          <tr><th>サービス提供体制強化加算</th><td>なし</td></tr>
          <tr><th>２４時間対応体制</th><td>あり</td></tr>
        </table>"""
    users = """
    <table>
      <tr><th>要介護度</th><th>要支援１</th><th>要支援２</th><th>要介護１</th><th>要介護２</th>
          <th>要介護３</th><th>要介護４</th><th>要介護５</th></tr>
      <tr><th>人数</th><td>0</td><td>1</td><td>11</td><td>19</td><td>5</td><td>9</td><td>3</td></tr>
    </table>"""
    kanri = f"""
    <table><tr><th>管理者の氏名</th><td>森田　愛{i}</td><th>職名</th><td>管理者</td></tr></table>"""
    return staff + users + kanri + kasan


class Handler(BaseHTTPRequestHandler):
    variant = "checkbox"
    pdf_hits = 0

    def log_message(self, *a):  # テスト出力を汚さない
        pass

    def _send(self, body: bytes):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        if u.path.endswith(".pdf"):
            Handler.pdf_hits += 1
            body = b"%PDF-1.4 dummy"
            self.send_response(200)
            self.send_header("Content-Type", "application/pdf")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        q = {k: v[0] for k, v in urllib.parse.parse_qs(u.query).items()}
        if "action_kouhyou_detail" in u.query:
            return self._send(self.detail(q))
        if "action_kouhyou_result" in u.query:
            return self._send(self.result(q))
        if "action_kouhyou_search_svc" in u.query:
            return self._send(self.search_svc(q))
        if "action_kouhyou_menu" in u.query:
            return self._send(self.menu())
        if "action_kouhyou_svc" in u.query:
            return self._send(self.real_svc())
        if "action_kouhyou_area" in u.query:
            return self._send(self.real_area(q))
        if "action_kouhyou_guide" in u.query:
            return self._send(self.guide())
        if "action_kouhyou_search" in u.query:
            return self._send(self.search())
        return self._send(self.top())

    # ------------------------------------------------------------- 画面
    def top(self) -> bytes:
        if Handler.variant == "pdftrap":
            # 実サイトにあった「パンフレットPDF」のような紛らわしいリンク
            return _page(
                "<h1>兵庫県 介護サービス情報公表システム</h1>"
                "<a href='/upload/prefinfo/00/介護サービス情報公表システムパンフレット"
                "（H26.10月版）.pdf'>介護サービス情報公表システムパンフレット</a>"
                "<a href='index.php?action_kouhyou_other=true'>公表情報の読み解き方</a>"
                "<a href='index.php?action_kouhyou_other=true'>介護サービス概算料金の試算</a>"
                "<a href='index.php?action_kouhyou_guide=true'>サービス・エリアからさがす</a>"
            )
        if Handler.variant == "iframe":
            return _page(
                "<h1>兵庫県 介護サービス情報公表システム</h1>"
                "<iframe name='main' src='index.php?action_kouhyou_search=true'"
                " width='900' height='600'></iframe>"
            )
        if Handler.variant == "real":
            return _page(
                "<h1>兵庫県 介護サービス情報公表システム</h1>"
                "<a href='/upload/prefinfo/00/パンフレット.pdf'>パンフレット</a>"
                "<a href='index.php?action_kouhyou_other=true'>公表情報の読み解き方</a>"
                "<a href='index.php?action_kouhyou_menu=true'>介護事業所を検索する</a>"
            )
        if Handler.variant == "deep":
            # トップに検索リンクが無く、案内ページ経由でしか到達できない構成
            return _page(
                "<h1>兵庫県 介護サービス情報公表システム</h1>"
                "<a href='index.php?action_kouhyou_guide=true'>サービス・エリアからさがす</a>"
                "<a href='index.php?action_kouhyou_other=true'>介護保険について</a>"
            )
        return _page(
            "<h1>兵庫県 介護サービス情報公表システム</h1>"
            "<a href='index.php?action_kouhyou_search=true'>介護事業所検索</a>"
            "<a href='index.php?action_kouhyou_other=true'>介護保険について</a>"
        )

    def guide(self) -> bytes:
        return _page(
            "<h2>おさがしの方法を選んでください</h2>"
            "<a href='index.php?action_kouhyou_other2=true'>制度のごあんない</a>"
            "<a href='index.php?action_kouhyou_search=true'>地域から事業所をさがす</a>"
        )

    def menu(self) -> bytes:
        return _page(
            "<h2>検索方法を選んでください</h2>"
            "<a href='index.php?action_kouhyou_kantan=true'>かんたん検索</a>"
            "<a href='index.php?action_kouhyou_svc=true'>詳しい条件で探す</a>"
        )

    def real_svc(self) -> bytes:
        """サービスの選択。ここに市区町村は無い（実サイトと同じ）。"""
        svcs = "".join(
            f"<label for='s{i}'><input type='checkbox' id='s{i}' name='svc' "
            f"value='{s}'>{s}</label> "
            for i, s in enumerate(SERVICES)
        )
        return _page(
            "<h2>サービスの選択</h2>"
            "<form action='index.php' method='get'>"
            "<input type='hidden' name='action_kouhyou_area' value='true'>"
            f"{svcs}<input type='submit' value='次へ進む'></form>"
        )

    def real_area(self, q) -> bytes:
        """事業所の所在地選択。サービスを選んだ後にだけ現れる。"""
        svc = q.get("svc", "居宅介護支援")
        cities = "".join(
            f"<label for='c{i}'><input type='checkbox' id='c{i}' name='city' "
            f"value='{c}'>{c}</label> "
            for i, c in enumerate(CITIES)
        )
        return _page(
            f"<h2>事業所の所在地選択（{svc}）</h2>"
            "<form action='index.php' method='get'>"
            "<input type='hidden' name='action_kouhyou_result' value='true'>"
            f"<input type='hidden' name='svc' value='{svc}'>"
            f"{cities}<input type='submit' value='検索する'></form>"
        )

    def search(self) -> bytes:
        v = Handler.variant
        if v in ("iframe", "pdftrap"):
            v = "checkbox"
        if v == "link":
            links = "".join(
                f"<a href='index.php?action_kouhyou_search_svc=true&city="
                f"{urllib.parse.quote(c)}'>{c} ({counts(c, '居宅介護支援')})</a> "
                for c in CITIES
            )
            return _page(f"<h2>市区町村を選んでください</h2>{links}")
        if v == "select":
            copts = "".join(f"<option value='{c}'>{c}</option>" for c in CITIES)
            sopts = "".join(f"<option value='{s}'>{s}</option>" for s in SERVICES)
            return _page(
                "<form action='index.php' method='get'>"
                "<input type='hidden' name='action_kouhyou_result' value='true'>"
                f"<select name='city'><option value=''>選択してください</option>{copts}</select>"
                f"<select name='svc'><option value=''>選択してください</option>{sopts}</select>"
                "<input type='submit' value='検索する'></form>"
            )
        if v == "textonly":
            return _page(
                "<form action='index.php' method='get'>"
                "<input type='hidden' name='action_kouhyou_result' value='true'>"
                "<label for='cityinput'>市区町村名</label>"
                "<input type='text' id='cityinput' name='city' placeholder='例：西宮市'>"
                "<input type='submit' value='検索する'></form>"
            )
        if v == "textbox":
            svcs = "".join(
                f"<label for='s{i}'><input type='checkbox' id='s{i}' name='svc' "
                f"value='{s}'>{s}</label> "
                for i, s in enumerate(SERVICES)
            )
            return _page(
                "<form action='index.php' method='get'>"
                "<input type='hidden' name='action_kouhyou_result' value='true'>"
                "<label for='cityinput'>市区町村名</label>"
                "<input type='text' id='cityinput' name='city' placeholder='例：西宮市'>"
                f"{svcs}<input type='submit' value='検索する'></form>"
            )
        cities = "".join(
            f"<label for='c{i}'><input type='checkbox' id='c{i}' name='city' "
            f"value='{c}'>{c} ({counts(c, '居宅介護支援')})</label> "
            for i, c in enumerate(CITIES)
        )
        svcs = "".join(
            f"<label for='s{i}'><input type='checkbox' id='s{i}' name='svc' "
            f"value='{s}'>{s}</label> "
            for i, s in enumerate(SERVICES)
        )
        return _page(
            "<form action='index.php' method='get'>"
            "<input type='hidden' name='action_kouhyou_result' value='true'>"
            f"<fieldset><legend>市区町村</legend>{cities}</fieldset>"
            f"<fieldset><legend>サービス種別</legend>{svcs}</fieldset>"
            "<input type='submit' value='検索する'></form>"
        )

    def search_svc(self, q) -> bytes:
        city = q.get("city", "")
        svcs = "".join(
            f"<label for='s{i}'><input type='checkbox' id='s{i}' name='svc' "
            f"value='{s}'>{s}</label> "
            for i, s in enumerate(SERVICES)
        )
        return _page(
            f"<h2>{city} のサービスを選んでください</h2>"
            "<form action='index.php' method='get'>"
            "<input type='hidden' name='action_kouhyou_result' value='true'>"
            f"<input type='hidden' name='city' value='{city}'>"
            f"{svcs}<input type='submit' value='検索する'></form>"
        )

    def result(self, q) -> bytes:
        city = q.get("city", "")
        svc = q.get("svc", "居宅介護支援")
        page = int(q.get("page", "1"))
        n = counts(city, svc)
        start, end = (page - 1) * PER_PAGE, min(page * PER_PAGE, n)
        items = "".join(
            f"<li><a href='index.php?action_kouhyou_detail_022_kani=true&JigyosyoCd="
            f"{cd_of(city, svc, i)}'>{name_of(city, svc, i)}</a></li>"
            for i in range(start + 1, end + 1)
        )
        nav = ""
        if Handler.variant == "deadnext":
            return _page(
                f"<p>{city} {svc} {n}件</p><ul>{items}</ul>"
                f"<a href='index.php?action_kouhyou_result=true&city="
                f"{urllib.parse.quote(city)}&svc={urllib.parse.quote(svc)}"
                f"&page={page}'>次へ</a>"
            )
        if end < n:
            nav = (
                f"<a href='index.php?action_kouhyou_result=true&city="
                f"{urllib.parse.quote(city)}&svc={urllib.parse.quote(svc)}"
                f"&page={page + 1}'>次へ</a>"
            )
        return _page(f"<p>{city} {svc} {n}件</p><ul>{items}</ul>{nav}")

    def detail(self, q) -> bytes:
        cd = q.get("JigyosyoCd", "")
        try:
            ci, si, i = int(cd[2:6]) - 1, int(cd[6:9]) - 1, int(cd.split("-")[1])
            city, svc = CITIES[ci], SERVICES[si]
        except (ValueError, IndexError):
            return _page("<p>該当なし</p>")
        tabs = ""
        for n, label in enumerate(
            ["事業所の概要", "事業所の特色", "事業所の詳細", "運営状況", "その他"], start=22
        ):
            tabs += (
                f"<a href='index.php?action_kouhyou_detail_0{n}_kani=true"
                f"&JigyosyoCd={cd}'>{label}</a> "
            )
        if "detail_024" in self.path:
            body = _detail(city, svc, i)
        elif "detail_022" in self.path:
            body = _overview(city, svc, i)
        else:
            body = f"<h1>{name_of(city, svc, i)}</h1><p>このタブに該当データはありません</p>"
        return _page(tabs + body)


class MockSite:
    def __init__(self, variant: str = "checkbox"):
        Handler.variant = variant
        Handler.pdf_hits = 0
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.port = self.httpd.server_address[1]
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)

    @property
    def pdf_hits(self) -> int:
        return Handler.pdf_hits

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.port}/{{code}}/"

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *exc):
        self.httpd.shutdown()
        self.httpd.server_close()
        return False

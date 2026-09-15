"""二重起動防止ロックと、中断からの再開用の進捗保存。"""
from __future__ import annotations

import json
import os
import time
from typing import Dict, Iterable, List, Optional

LOCK_NAME = "実行中.lock"
OLD_LOCK_NAMES = (".__itakukaigokensaku.lock",)   # 旧版が残したもの

# 取得ロジックを変更したら上げる。これが違う進捗ファイルは読み捨てる
# （古い取り方で集めたデータが再開時に混ざらないようにするため）
DATA_VERSION = 7

# 進捗を「中断からの再開」として使ってよい時間。これを過ぎたら古いデータとみなす。
# 進捗は中断の復旧用であって、前回の結果を使い回すためのものではない。
PROGRESS_MAX_AGE_SEC = 36 * 3600


class AlreadyRunning(RuntimeError):
    pass


def _pid_alive(pid: int) -> bool:
    """そのプロセスが今も動いているか。"""
    if pid <= 0:
        return False
    if os.name == "nt":
        import ctypes

        h = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)   # QUERY_LIMITED
        if not h:
            return False
        ctypes.windll.kernel32.CloseHandle(h)
        return True
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


class Lock:
    """二重起動を防ぐ。

    強制終了やウィンドウを閉じた場合、解放処理が走らずロックが残る。
    残ったロックを利用者に手で消させるのは現実的でないため、書いてある
    PIDが生きているかを確認し、死んでいれば自動的に奪う。
    """

    def __init__(self, base_dir: str):
        self.path = os.path.join(base_dir, LOCK_NAME)
        self.base_dir = base_dir
        self.fd = None

    def _stale_pid(self) -> Optional[int]:
        try:
            with open(self.path, encoding="utf-8") as f:
                pid = int((f.read() or "0").strip() or 0)
        except (OSError, ValueError):
            return 0          # 中身が読めない＝壊れている。奪ってよい
        return None if _pid_alive(pid) else pid

    def __enter__(self):
        for old in OLD_LOCK_NAMES:            # 旧版が残した隠しファイルを片付ける
            try:
                os.remove(os.path.join(self.base_dir, old))
            except OSError:
                pass
        try:
            self.fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_RDWR)
        except FileExistsError:
            if self._stale_pid() is None:
                raise AlreadyRunning(
                    "このツールは別のウィンドウで実行中です。"
                    "そちらの画面をご確認ください。"
                )
            # 前回が異常終了して残ったロック。自動的に引き継ぐ
            try:
                os.remove(self.path)
            except OSError:
                pass
            self.fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_RDWR)
        os.write(self.fd, str(os.getpid()).encode())
        return self

    def __exit__(self, *exc):
        try:
            if self.fd is not None:
                os.close(self.fd)
            os.remove(self.path)
        except OSError:
            pass
        return False


class Progress:
    """(サービス, 市区町村) 単位の完了状況と取得済みデータを保持する。

    これは「中断したときに続きから取得するための一時データ」であり、
    前回の取得結果を使い回すためのものではない。そのため
      - 都道府県が違えば読まない（別の県のデータが混ざるのを防ぐ）
      - 一定時間より古ければ読まない（先月のデータが今日の結果として出るのを防ぐ）
      - 正常に完了したら消す（runner が呼ぶ）
    """

    def __init__(self, path: str, pref: str = ""):
        self.path = path
        self.pref = pref
        self.done: List[str] = []
        self.rows: Dict[str, List[dict]] = {}
        self.stale = False
        self.stale_reason = ""
        self.saved_at = 0.0

    @staticmethod
    def key(service: str, city: str) -> str:
        return f"{service}\t{city}"

    def load(self) -> "Progress":
        try:
            with open(self.path, encoding="utf-8") as f:
                d = json.load(f)
        except (OSError, ValueError):
            return self

        if d.get("version") != DATA_VERSION:
            self._discard("ツールが更新されている")
            return self
        saved_pref = d.get("pref", "")
        if self.pref and saved_pref and saved_pref != self.pref:
            self._discard(f"前回は{saved_pref}の取得だった")
            return self
        saved_at = float(d.get("saved_at") or 0)
        if saved_at and time.time() - saved_at > PROGRESS_MAX_AGE_SEC:
            days = (time.time() - saved_at) / 86400
            self._discard(f"前回の取得から{days:.0f}日経っている")
            return self

        self.done = d.get("done", [])
        self.rows = d.get("rows", {})
        self.saved_at = saved_at
        return self

    def _discard(self, reason: str) -> None:
        self.stale = True
        self.stale_reason = reason
        self.clear()

    def save(self) -> None:
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(
                {"version": DATA_VERSION, "pref": self.pref,
                 "saved_at": time.time(), "done": self.done, "rows": self.rows},
                f, ensure_ascii=False,
            )
        os.replace(tmp, self.path)

    def is_done(self, service: str, city: str) -> bool:
        return self.key(service, city) in self.done

    def put(self, service: str, city: str, rows: List[dict]) -> None:
        k = self.key(service, city)
        self.rows[k] = rows
        if k not in self.done:
            self.done.append(k)

    def collected(self, service: str, cities: Optional[Iterable[str]] = None) -> List[dict]:
        """今回の対象ぶんだけを取り出す。

        cities を省略すると、そのサービスの保存ぶんをすべて返す。
        出力に使うときは必ず cities を渡すこと。渡さないと、過去に取得した
        別の市区町村の行まで出力に混ざる。
        """
        wanted = None if cities is None else set(cities)
        out: List[dict] = []
        for city in (wanted if wanted is not None else self._cities_of(service)):
            out.extend(self.rows.get(self.key(service, city), []))
        return out

    def _cities_of(self, service: str) -> List[str]:
        return [k.split("\t", 1)[1] for k in self.rows if k.split("\t", 1)[0] == service]

    def clear(self) -> None:
        self.done, self.rows = [], {}
        try:
            os.remove(self.path)
        except OSError:
            pass

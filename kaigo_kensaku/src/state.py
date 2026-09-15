"""二重起動防止ロックと、中断からの再開用の進捗保存。"""
from __future__ import annotations

import json
import os
from typing import Dict, List

LOCK_NAME = ".__itakukaigokensaku.lock"

# 取得ロジックを変更したら上げる。これが違う進捗ファイルは読み捨てる
# （古い取り方で集めたデータが再開時に混ざらないようにするため）
DATA_VERSION = 2


class AlreadyRunning(RuntimeError):
    pass


class Lock:
    def __init__(self, base_dir: str):
        self.path = os.path.join(base_dir, LOCK_NAME)
        self.fd = None

    def __enter__(self):
        try:
            self.fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_RDWR)
        except FileExistsError:
            raise AlreadyRunning(
                f"すでに実行中です。終了しているのにこのメッセージが出る場合は "
                f"{LOCK_NAME} を削除してください。"
            )
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
    """(サービス, 市区町村) 単位の完了状況と取得済みデータを保持する。"""

    def __init__(self, path: str):
        self.path = path
        self.done: List[str] = []
        self.rows: Dict[str, List[dict]] = {}
        self.stale = False

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
            # ツールの取得ロジックが変わっている。古いデータは使わない
            self.stale = True
            self.clear()
            return self
        self.done = d.get("done", [])
        self.rows = d.get("rows", {})
        return self

    def save(self) -> None:
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(
                {"version": DATA_VERSION, "done": self.done, "rows": self.rows},
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

    def collected(self, service: str) -> List[dict]:
        out: List[dict] = []
        for k, v in self.rows.items():
            if k.split("\t", 1)[0] == service:
                out.extend(v)
        return out

    def clear(self) -> None:
        self.done, self.rows = [], {}
        try:
            os.remove(self.path)
        except OSError:
            pass

"""ログ設定。コマンドライン版と画面版の両方から呼ぶ。

画面版でログが残らないと、障害が起きたときに「エラーが出ました」以上の
情報が誰にも残らない。exe化（--windowed）すると標準エラー出力も消えるため、
必ずファイルへ書く。
"""
from __future__ import annotations

import logging
import logging.handlers
import os
import sys

LOG_NAME = "itakukaigokensaku.log"


def setup_logging(base_dir: str, debug: bool, to_console: bool = True) -> str:
    """logs/itakukaigokensaku.log への記録を開始し、そのパスを返す。"""
    log_dir = os.path.join(base_dir, "logs")
    os.makedirs(log_dir, exist_ok=True)
    path = os.path.join(log_dir, LOG_NAME)

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    for h in list(root.handlers):
        root.removeHandler(h)
        try:
            h.close()
        except Exception:
            pass

    # 数時間動かすので、際限なく太らないよう上限を設ける
    fh = logging.handlers.RotatingFileHandler(
        path, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    fh.setLevel(logging.DEBUG if debug else logging.INFO)
    fh.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    )
    root.addHandler(fh)

    if to_console and sys.stdout is not None:
        sh = logging.StreamHandler(sys.stdout)
        sh.setLevel(logging.INFO if debug else logging.WARNING)
        sh.setFormatter(logging.Formatter("%(message)s"))
        root.addHandler(sh)

    logging.getLogger("selenium").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    return path

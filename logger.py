"""ロギング設定。

rich によるコンソール出力と、ファイルへの実行ログ出力を同時に構成する。
ファイルは UTF-8 固定で追記する。
"""

from __future__ import annotations

import logging
from pathlib import Path

from rich.console import Console
from rich.logging import RichHandler

_LOGGER_NAME = "codex_orchestrator"

console = Console()


def setup_logger(log_file: Path, *, verbose: bool = False) -> logging.Logger:
    """コンソール（rich）とファイルの両方へ出力するロガーを構成する。

    Args:
        log_file: 実行ログの出力先。親ディレクトリが無ければ作成する。
        verbose: True の場合 DEBUG レベルまで出力する。

    Returns:
        構成済みのロガー。
    """
    logger = logging.getLogger(_LOGGER_NAME)
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)
    logger.handlers.clear()
    logger.propagate = False

    console_handler = RichHandler(
        console=console,
        rich_tracebacks=True,
        show_path=False,
        markup=True,
    )
    console_handler.setLevel(logging.DEBUG if verbose else logging.INFO)
    logger.addHandler(console_handler)

    log_file.parent.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    )
    logger.addHandler(file_handler)

    return logger


def get_logger() -> logging.Logger:
    """構成済みロガーを取得する（未構成でも同名ロガーを返す）。"""
    return logging.getLogger(_LOGGER_NAME)

"""対象ファイル一覧の読込。

対象ファイルは探索せず、事前に用意された一覧を読み込む。
将来的に CSV / JSON / DB などへ差し替えられるよう、抽象基底 TargetLoader を定義する。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from logger import get_logger
from models import TargetFile

DEFAULT_ENCODINGS: tuple[str, ...] = ("utf-8", "cp932")


def read_text_with_fallback(path: Path, encodings: tuple[str, ...] = DEFAULT_ENCODINGS) -> str:
    """複数エンコーディング候補を順に試してテキストを読み込む。

    UTF-8 を基本とし、失敗時は Shift_JIS(cp932) 等へフォールバックする。
    すべて失敗した場合は最後の例外を送出する。
    """
    last_error: UnicodeDecodeError | None = None
    for encoding in encodings:
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError as exc:
            last_error = exc
    if last_error is not None:
        raise last_error
    raise ValueError("エンコーディング候補が指定されていません")


class TargetLoader(ABC):
    """対象ファイル一覧を読み込むための抽象インターフェース。

    実装は raw なパス文字列の列を返す責務のみを持つ。
    存在チェックや重複除外などの共通処理は load() 側で行う。
    """

    def __init__(self, project_root: Path, encodings: tuple[str, ...] = DEFAULT_ENCODINGS) -> None:
        self._project_root = project_root
        self._encodings = encodings

    @abstractmethod
    def _iter_raw_paths(self) -> list[str]:
        """一覧ソースから相対パス文字列の一覧を取り出す。"""

    def load(self) -> list[TargetFile]:
        """対象ファイル一覧を検証済みの TargetFile 列として返す。

        - 空行・コメント（# 始まり）を無視
        - 重複を除外（出現順を維持）
        - 存在しないファイルは警告を出しスキップ
        """
        logger = get_logger()
        seen: set[str] = set()
        targets: list[TargetFile] = []

        for raw in self._iter_raw_paths():
            relative = self._normalize(raw)
            if relative is None or relative in seen:
                continue
            seen.add(relative)

            absolute = (self._project_root / relative).resolve()
            if not absolute.is_file():
                logger.warning("対象ファイルが存在しないためスキップします: %s", relative)
                continue

            targets.append(TargetFile(relative_path=relative, absolute_path=absolute))

        logger.info("対象ファイルを %d 件読み込みました", len(targets))
        return targets

    @staticmethod
    def _normalize(raw: str) -> str | None:
        """1 行を正規化し、無視対象なら None を返す。"""
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            return None
        return stripped.replace("\\", "/")


class TextTargetLoader(TargetLoader):
    """テキストファイル（1 行 1 パス）から対象一覧を読み込む実装。"""

    def __init__(
        self,
        targets_file: Path,
        project_root: Path,
        encodings: tuple[str, ...] = DEFAULT_ENCODINGS,
    ) -> None:
        super().__init__(project_root, encodings)
        self._targets_file = targets_file

    def _iter_raw_paths(self) -> list[str]:
        if not self._targets_file.is_file():
            raise FileNotFoundError(f"対象一覧ファイルが見つかりません: {self._targets_file}")
        content = read_text_with_fallback(self._targets_file, self._encodings)
        return content.splitlines()

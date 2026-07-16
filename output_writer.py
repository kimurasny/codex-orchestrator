"""生成結果の Markdown 保存。

Codex の標準出力を Markdown ファイルとして保存する。
preserve_directory によりディレクトリ構造を保持でき、
output_mode により既存ファイルの上書き / スキップを切り替える。
"""

from __future__ import annotations

from pathlib import Path

from models import OutputMode, TargetFile

MARKDOWN_SUFFIX = ".md"


class OutputWriter:
    """出力先パスの解決と Markdown 保存を担う。"""

    def __init__(
        self,
        output_dir: Path,
        *,
        preserve_directory: bool,
        output_mode: OutputMode,
    ) -> None:
        self._output_dir = output_dir
        self._preserve_directory = preserve_directory
        self._output_mode = output_mode

    def resolve_output_path(self, target: TargetFile) -> Path:
        """対象ファイルに対する出力 Markdown パスを決定する。

        preserve_directory=True の場合は相対ディレクトリ構造を保持する。
        False の場合は output_dir 直下にファイル名のみで保存する。
        """
        stem_name = Path(target.relative_path).with_suffix(MARKDOWN_SUFFIX)
        if self._preserve_directory:
            return self._output_dir / stem_name
        return self._output_dir / stem_name.name

    def should_skip(self, output_path: Path) -> bool:
        """保存モードに基づき、この出力をスキップすべきか判定する。"""
        return self._output_mode is OutputMode.SKIP and output_path.exists()

    def ensure_parent(self, output_path: Path) -> None:
        """出力先の親ディレクトリを用意する（Codex がファイルを書き出す前提の場合に使用）。"""
        output_path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, output_path: Path, content: str) -> None:
        """Markdown を UTF-8 で保存する（親ディレクトリは自動作成）。"""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(content, encoding="utf-8")

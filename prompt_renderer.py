"""プロンプトテンプレート管理とレンダリング。

テンプレートは Markdown ファイルとして templates/ 配下に配置する。
Jinja2 を用い、対象ファイルごとのプレースホルダを差し込む。
"""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, StrictUndefined

from models import TargetFile
from target_loader import DEFAULT_ENCODINGS, read_text_with_fallback

TEMPLATE_SUFFIX = ".md"


class PromptRenderer:
    """テンプレートをロードし、対象ファイル情報でレンダリングする。

    プレースホルダ:
        {{TARGET}}       対象ファイル（相対パス）
        {{ABS_PATH}}     絶対パス
        {{FILE_NAME}}    ファイル名
        {{OUTPUT}}       出力 Markdown パス
        {{PROJECT_ROOT}} プロジェクトルート
    """

    def __init__(
        self,
        templates_dir: Path,
        template_name: str,
        project_root: Path,
        encodings: tuple[str, ...] = DEFAULT_ENCODINGS,
    ) -> None:
        self._templates_dir = templates_dir
        self._template_name = template_name
        self._project_root = project_root
        self._encodings = encodings
        self._environment = Environment(
            variable_start_string="{{",
            variable_end_string="}}",
            undefined=StrictUndefined,
            autoescape=False,
            keep_trailing_newline=True,
        )
        self._template_source = self._load_template_source()

    def _template_path(self) -> Path:
        """テンプレート名から Markdown ファイルパスを解決する。"""
        name = self._template_name
        if not name.endswith(TEMPLATE_SUFFIX):
            name = f"{name}{TEMPLATE_SUFFIX}"
        return self._templates_dir / name

    def _load_template_source(self) -> str:
        path = self._template_path()
        if not path.is_file():
            raise FileNotFoundError(f"テンプレートが見つかりません: {path}")
        return read_text_with_fallback(path, self._encodings)

    def render(self, target: TargetFile, output_path: Path) -> str:
        """対象ファイルと出力先からプロンプト文字列を生成する。"""
        template = self._environment.from_string(self._template_source)
        return template.render(
            TARGET=target.relative_path,
            ABS_PATH=str(target.absolute_path),
            FILE_NAME=target.file_name,
            OUTPUT=str(output_path),
            PROJECT_ROOT=str(self._project_root),
        )

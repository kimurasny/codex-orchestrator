"""設定管理。

YAML ファイルと CLI 引数から実行設定を構築する。
CLI 引数は YAML より優先される（None 以外の値のみ上書き）。
"""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field, field_validator

from models import OutputMode


class OrchestratorConfig(BaseModel):
    """オーケストレーターの実行設定。

    YAML のキーと 1:1 で対応する。相対パスは project_root 基準で解決する。
    """

    project_root: Path = Field(default_factory=Path.cwd)
    targets_file: Path = Path("config/targets.txt")
    template: str = "class_spec"
    output_dir: Path = Path("docs/spec")
    output_mode: OutputMode = OutputMode.OVERWRITE
    preserve_directory: bool = True
    retry: int = 3
    codex_command: str = "codex exec --sandbox workspace-write"
    templates_dir: Path = Path("templates")
    status_file: Path = Path("logs/status.json")
    log_file: Path = Path("logs/run.log")
    encoding_candidates: list[str] = Field(default_factory=lambda: ["utf-8", "cp932"])

    @field_validator("retry")
    @classmethod
    def _validate_retry(cls, value: int) -> int:
        if value < 0:
            raise ValueError("retry は 0 以上である必要があります")
        return value

    def resolve(self, base: Path) -> OrchestratorConfig:
        """相対パス項目を base（=project_root）基準の絶対パスへ解決する。

        project_root 自体が相対の場合は base を起点に解決する。
        """
        root = base if self.project_root == Path() else _absolutize(self.project_root, base)

        def under_root(path: Path) -> Path:
            return _absolutize(path, root)

        return self.model_copy(
            update={
                "project_root": root,
                "targets_file": under_root(self.targets_file),
                "output_dir": under_root(self.output_dir),
                "templates_dir": under_root(self.templates_dir),
                "status_file": under_root(self.status_file),
                "log_file": under_root(self.log_file),
            }
        )


def _absolutize(path: Path, base: Path) -> Path:
    """path が相対なら base 基準で絶対化する。"""
    return path if path.is_absolute() else (base / path)


def load_yaml_config(config_path: Path) -> OrchestratorConfig:
    """YAML から設定を読み込む。ファイルが無い場合は既定値を返す。"""
    if not config_path.exists():
        raise FileNotFoundError(f"設定ファイルが見つかりません: {config_path}")

    raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise ValueError("設定ファイルの形式が不正です（マッピングを期待）")
    return OrchestratorConfig.model_validate(raw)


def merge_cli_overrides(base: OrchestratorConfig, **overrides: object) -> OrchestratorConfig:
    """CLI 由来の上書き値（None を除く）を設定へ反映する。"""
    updates = {key: value for key, value in overrides.items() if value is not None}
    if not updates:
        return base
    return base.model_copy(update=updates)

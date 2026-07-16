"""ドメインモデル定義。

オーケストレーター全体で共有するデータ構造を pydantic / Enum で表現する。
各モジュール間の受け渡しはこれらの型を介して行い、責務の境界を明確にする。
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class OutputMode(StrEnum):
    """既存 Markdown が存在する場合の保存挙動。"""

    OVERWRITE = "overwrite"  # 上書き保存する
    SKIP = "skip"  # 既存ファイルがあればスキップする


class ExecutionState(StrEnum):
    """1 対象ファイルに対する実行状態。"""

    PENDING = "pending"  # 未処理
    SUCCESS = "success"  # 正常終了
    FAILED = "failed"  # 失敗（リトライ上限到達）
    SKIPPED = "skipped"  # 保存モード等によりスキップ


class TargetFile(BaseModel):
    """解析対象となる 1 ファイルを表す。

    Attributes:
        relative_path: リポジトリルートからの相対パス（区切りは POSIX 形式に正規化）。
        absolute_path: 実ファイルの絶対パス。
    """

    model_config = ConfigDict(frozen=True)

    relative_path: str
    absolute_path: Path

    @property
    def file_name(self) -> str:
        """対象ファイルのファイル名（拡張子含む）を返す。"""
        return self.absolute_path.name


class ExecutionResult(BaseModel):
    """1 ファイルに対する Codex 実行結果。"""

    target: TargetFile
    state: ExecutionState
    output_path: Path | None = None
    retries: int = 0
    duration_seconds: float = 0.0
    error_message: str | None = None


class StatusEntry(BaseModel):
    """status.json に永続化する 1 レコード。"""

    relative_path: str
    state: ExecutionState
    output_path: str | None = None
    updated_at: datetime = Field(default_factory=datetime.now)
    retries: int = 0
    error_message: str | None = None


class RunSummary(BaseModel):
    """実行全体の集計結果。"""

    total: int = 0
    success: int = 0
    failed: int = 0
    skipped: int = 0
    total_duration_seconds: float = 0.0

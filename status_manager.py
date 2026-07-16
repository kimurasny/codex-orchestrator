"""実行状態の永続化と再開制御。

logs/status.json に対象ファイルごとの実行状態を保持し、
--resume 時に未処理（成功以外）のファイルのみを対象に絞り込む。
"""

from __future__ import annotations

import json
from pathlib import Path

from logger import get_logger
from models import ExecutionResult, ExecutionState, StatusEntry, TargetFile


class StatusManager:
    """status.json の読み書きと再開判定を担う。"""

    def __init__(self, status_file: Path) -> None:
        self._status_file = status_file
        self._entries: dict[str, StatusEntry] = {}

    def load(self) -> None:
        """既存の status.json を読み込む。無ければ空状態で開始する。"""
        logger = get_logger()
        if not self._status_file.is_file():
            self._entries = {}
            return
        try:
            raw = json.loads(self._status_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("status.json の読み込みに失敗したため空状態で開始します: %s", exc)
            self._entries = {}
            return
        self._entries = {
            item["relative_path"]: StatusEntry.model_validate(item) for item in raw
        }

    def is_completed(self, target: TargetFile) -> bool:
        """再開時にスキップ可能（成功済み）かどうかを判定する。"""
        entry = self._entries.get(target.relative_path)
        return entry is not None and entry.state is ExecutionState.SUCCESS

    def filter_pending(self, targets: list[TargetFile]) -> list[TargetFile]:
        """成功済みを除いた未処理ファイルのみを返す。"""
        return [target for target in targets if not self.is_completed(target)]

    def update(self, result: ExecutionResult) -> None:
        """実行結果を状態へ反映し、即座に永続化する。"""
        self._entries[result.target.relative_path] = StatusEntry(
            relative_path=result.target.relative_path,
            state=result.state,
            output_path=str(result.output_path) if result.output_path else None,
            retries=result.retries,
            error_message=result.error_message,
        )
        self._flush()

    def _flush(self) -> None:
        """現在の状態を status.json へ書き出す。"""
        self._status_file.parent.mkdir(parents=True, exist_ok=True)
        payload = [entry.model_dump(mode="json") for entry in self._entries.values()]
        self._status_file.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )

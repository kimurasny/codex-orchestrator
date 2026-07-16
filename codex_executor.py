"""Codex CLI の実行。

対象ファイルごとに Codex CLI を 1 回起動する。
レンダリング済みプロンプトを標準入力から渡し、標準出力を回収する。
失敗時は指定回数までリトライする。
"""

from __future__ import annotations

import shlex
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from logger import get_logger


@dataclass(frozen=True)
class CodexInvocation:
    """1 回の Codex 実行結果。"""

    succeeded: bool
    stdout: str
    stderr: str
    return_code: int
    retries: int
    duration_seconds: float


class CodexExecutor:
    """Codex CLI をサブプロセスとして実行するランナー。"""

    def __init__(
        self,
        codex_command: str,
        project_root: Path,
        *,
        retry: int = 3,
        timeout_seconds: float | None = None,
    ) -> None:
        self._command = shlex.split(codex_command)
        if not self._command:
            raise ValueError("codex_command が空です")
        self._project_root = project_root
        self._retry = retry
        self._timeout_seconds = timeout_seconds

    def execute(self, prompt: str) -> CodexInvocation:
        """プロンプトを標準入力へ渡して Codex を実行する。

        成功するまで最大 retry 回リトライし、最終結果を返す。
        """
        logger = get_logger()
        start = time.perf_counter()
        attempts = self._retry + 1
        last_stdout = ""
        last_stderr = ""
        last_code = -1

        for attempt in range(attempts):
            try:
                completed = subprocess.run(
                    self._command,
                    input=prompt,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    cwd=self._project_root,
                    timeout=self._timeout_seconds,
                    check=False,
                )
            except FileNotFoundError as exc:
                duration = time.perf_counter() - start
                logger.error("Codex コマンドが見つかりません: %s", exc)
                return CodexInvocation(
                    succeeded=False,
                    stdout="",
                    stderr=str(exc),
                    return_code=-1,
                    retries=attempt,
                    duration_seconds=duration,
                )
            except subprocess.TimeoutExpired as exc:
                last_stderr = f"タイムアウト: {exc}"
                last_code = -1
                logger.warning("Codex 実行がタイムアウトしました (試行 %d)", attempt + 1)
                continue

            last_stdout = completed.stdout or ""
            last_stderr = completed.stderr or ""
            last_code = completed.returncode

            if completed.returncode == 0:
                duration = time.perf_counter() - start
                return CodexInvocation(
                    succeeded=True,
                    stdout=last_stdout,
                    stderr=last_stderr,
                    return_code=0,
                    retries=attempt,
                    duration_seconds=duration,
                )

            logger.warning(
                "Codex 実行が失敗しました (試行 %d/%d, 終了コード=%d)",
                attempt + 1,
                attempts,
                completed.returncode,
            )

        duration = time.perf_counter() - start
        return CodexInvocation(
            succeeded=False,
            stdout=last_stdout,
            stderr=last_stderr,
            return_code=last_code,
            retries=self._retry,
            duration_seconds=duration,
        )

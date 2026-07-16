"""Codex Orchestrator CLI エントリポイント。

設定・対象一覧の読込からテンプレートのレンダリング、Codex 実行、
Markdown 保存、状態管理までを統括する。

使用例:
    python run.py --config config.yaml
    python run.py --targets config/targets.txt
    python run.py --template class_spec
    python run.py --resume
    python run.py --dry-run
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Annotated

import typer
from rich.table import Table

from codex_executor import CodexExecutor
from config import OrchestratorConfig, load_yaml_config, merge_cli_overrides
from logger import console, get_logger, setup_logger
from models import ExecutionResult, ExecutionState, OutputMode, RunSummary, TargetFile
from output_writer import OutputWriter
from prompt_renderer import PromptRenderer
from status_manager import StatusManager
from target_loader import TargetLoader, TextTargetLoader

app = typer.Typer(
    add_completion=False,
    help="Codex CLI を用いてソースコードから仕様書を大量生成するオーケストレーター",
)


class Orchestrator:
    """1 ファイル 1 実行の原則で仕様書生成を統括するコアクラス。"""

    def __init__(
        self,
        config: OrchestratorConfig,
        loader: TargetLoader,
        renderer: PromptRenderer,
        writer: OutputWriter,
        executor: CodexExecutor,
        status: StatusManager,
    ) -> None:
        self._config = config
        self._loader = loader
        self._renderer = renderer
        self._writer = writer
        self._executor = executor
        self._status = status

    def run(self, *, resume: bool) -> RunSummary:
        """対象ファイルを順次処理し、集計結果を返す。"""
        logger = get_logger()
        started_at = time.perf_counter()
        logger.info("実行を開始します: %s", _now())

        targets = self._loader.load()
        self._status.load()
        if resume:
            before = len(targets)
            targets = self._status.filter_pending(targets)
            logger.info("再開モード: %d 件中 %d 件を処理対象とします", before, len(targets))

        summary = RunSummary(total=len(targets))
        for index, target in enumerate(targets, start=1):
            logger.info("[%d/%d] 処理中: %s", index, len(targets), target.relative_path)
            result = self._process_one(target)
            self._status.update(result)
            self._accumulate(summary, result)

        summary.total_duration_seconds = time.perf_counter() - started_at
        logger.info("実行を終了します: %s", _now())
        return summary

    def _process_one(self, target: TargetFile) -> ExecutionResult:
        """1 対象ファイルの処理（スキップ判定・実行・保存）を行う。"""
        logger = get_logger()
        output_path = self._writer.resolve_output_path(target)

        if self._writer.should_skip(output_path):
            logger.info("既存ファイルのためスキップ: %s", output_path)
            return ExecutionResult(
                target=target, state=ExecutionState.SKIPPED, output_path=output_path
            )

        prompt = self._renderer.render(target, output_path)
        invocation = self._executor.execute(prompt)

        if not invocation.succeeded:
            logger.error(
                "失敗: %s (リトライ %d 回, %s)",
                target.relative_path,
                invocation.retries,
                invocation.stderr.strip() or "エラー詳細なし",
            )
            return ExecutionResult(
                target=target,
                state=ExecutionState.FAILED,
                retries=invocation.retries,
                duration_seconds=invocation.duration_seconds,
                error_message=invocation.stderr.strip() or None,
            )

        self._writer.write(output_path, invocation.stdout)
        logger.info(
            "成功: %s -> %s (%.2f 秒, リトライ %d 回)",
            target.relative_path,
            output_path,
            invocation.duration_seconds,
            invocation.retries,
        )
        return ExecutionResult(
            target=target,
            state=ExecutionState.SUCCESS,
            output_path=output_path,
            retries=invocation.retries,
            duration_seconds=invocation.duration_seconds,
        )

    @staticmethod
    def _accumulate(summary: RunSummary, result: ExecutionResult) -> None:
        """集計へ 1 件分の結果を加算する。"""
        if result.state is ExecutionState.SUCCESS:
            summary.success += 1
        elif result.state is ExecutionState.FAILED:
            summary.failed += 1
        elif result.state is ExecutionState.SKIPPED:
            summary.skipped += 1


def _now() -> str:
    """人間可読な現在時刻文字列。"""
    return time.strftime("%Y-%m-%d %H:%M:%S")


def _build_config(
    config_path: Path | None,
    targets: Path | None,
    template: str | None,
    output_dir: Path | None,
    output_mode: OutputMode | None,
) -> OrchestratorConfig:
    """YAML と CLI 引数を統合し、パス解決済みの設定を構築する。"""
    base = load_yaml_config(config_path) if config_path else OrchestratorConfig()
    merged = merge_cli_overrides(
        base,
        targets_file=targets,
        template=template,
        output_dir=output_dir,
        output_mode=output_mode,
    )
    return merged.resolve(Path.cwd())


def _render_dry_run(config: OrchestratorConfig, targets: list[TargetFile]) -> None:
    """Dry Run 表示（対象一覧・出力予定・使用テンプレート）を行う。"""
    writer = OutputWriter(
        config.output_dir,
        preserve_directory=config.preserve_directory,
        output_mode=config.output_mode,
    )
    table = Table(title="Dry Run: 実行予定")
    table.add_column("対象ファイル", style="cyan")
    table.add_column("出力予定", style="green")
    for target in targets:
        table.add_row(target.relative_path, str(writer.resolve_output_path(target)))
    console.print(table)
    console.print(f"使用テンプレート: [bold]{config.template}[/bold]")
    console.print(f"対象件数: [bold]{len(targets)}[/bold]")


def _render_summary(summary: RunSummary) -> None:
    """実行サマリを表形式で表示する。"""
    table = Table(title="実行サマリ")
    table.add_column("項目")
    table.add_column("値", justify="right")
    table.add_row("総件数", str(summary.total))
    table.add_row("成功件数", str(summary.success))
    table.add_row("失敗件数", str(summary.failed))
    table.add_row("スキップ件数", str(summary.skipped))
    table.add_row("総実行時間(秒)", f"{summary.total_duration_seconds:.2f}")
    console.print(table)


@app.command()
def main(
    config: Annotated[
        Path | None, typer.Option("--config", "-c", help="YAML 設定ファイルのパス")
    ] = None,
    targets: Annotated[
        Path | None, typer.Option("--targets", "-t", help="対象ファイル一覧のパス")
    ] = None,
    template: Annotated[
        str | None, typer.Option("--template", help="使用テンプレート名（拡張子省略可）")
    ] = None,
    output_dir: Annotated[
        Path | None, typer.Option("--output-dir", "-o", help="Markdown 出力ディレクトリ")
    ] = None,
    output_mode: Annotated[
        OutputMode | None, typer.Option("--output-mode", help="overwrite / skip")
    ] = None,
    resume: Annotated[
        bool, typer.Option("--resume", help="未処理ファイルのみ再開実行する")
    ] = False,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Codex を起動せず実行予定のみ表示する")
    ] = False,
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="詳細ログを出力する")] = False,
) -> None:
    """仕様書生成を実行する。"""
    try:
        resolved = _build_config(config, targets, template, output_dir, output_mode)
    except (FileNotFoundError, ValueError) as exc:
        console.print(f"[red]設定エラー: {exc}[/red]")
        raise typer.Exit(code=1) from exc

    logger = setup_logger(resolved.log_file, verbose=verbose)

    loader = TextTargetLoader(
        resolved.targets_file,
        resolved.project_root,
        tuple(resolved.encoding_candidates),
    )

    try:
        if dry_run:
            target_list = loader.load()
            _render_dry_run(resolved, target_list)
            return

        renderer = PromptRenderer(
            resolved.templates_dir,
            resolved.template,
            resolved.project_root,
            tuple(resolved.encoding_candidates),
        )
        writer = OutputWriter(
            resolved.output_dir,
            preserve_directory=resolved.preserve_directory,
            output_mode=resolved.output_mode,
        )
        executor = CodexExecutor(
            resolved.codex_command,
            resolved.project_root,
            retry=resolved.retry,
        )
        status = StatusManager(resolved.status_file)
        orchestrator = Orchestrator(resolved, loader, renderer, writer, executor, status)
        summary = orchestrator.run(resume=resume)
        _render_summary(summary)
        if summary.failed > 0:
            raise typer.Exit(code=1)
    except FileNotFoundError as exc:
        logger.error("ファイルが見つかりません: %s", exc)
        raise typer.Exit(code=1) from exc


if __name__ == "__main__":
    app()

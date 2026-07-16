# Codex Orchestrator

Codex CLI を利用して、ソースコードから仕様書（クラス仕様書・画面仕様書・バッチ仕様書・API 仕様書など）を **大量生成** するための Python 製オーケストレーターです。

- **1 回の Codex 実行につき 1 ファイルのみ解析** することを前提としています。
- 対象ファイルはプログラムで探索せず、事前に作成した **相対パス一覧ファイル** を読み込み、ファイルごとに Codex CLI を順次実行します。
- Windows 環境での利用を主眼に置きつつ、UTF-8 を基本とし Shift_JIS(cp932) のファイルも読み込めます。

---

## セットアップ

### 前提

- Python 3.12 以上
- [Codex CLI](https://github.com/openai/codex) がインストール済みで、パスが通っていること

### インストール

```bash
# 仮想環境の作成（例）
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate    # macOS / Linux

# 依存ライブラリのインストール
pip install -r requirements.txt
# もしくは
pip install .
```

使用ライブラリ: `typer` / `rich` / `jinja2` / `pydantic` / `PyYAML`（標準ライブラリの `pathlib` / `subprocess` を併用）。

---

## ディレクトリ構成

```
codex-orchestrator/
├── run.py                 # CLI エントリポイント / オーケストレーション統括
├── config.py              # 設定（YAML + CLI 引数）の読込・マージ
├── models.py              # ドメインモデル（pydantic / Enum）
├── target_loader.py       # 対象一覧の読込（抽象 TargetLoader + テキスト実装）
├── prompt_renderer.py     # Jinja2 によるテンプレートレンダリング
├── codex_executor.py      # Codex CLI のサブプロセス実行 + リトライ
├── output_writer.py       # 生成結果の Markdown 保存
├── status_manager.py      # 実行状態の永続化 / 再開制御
├── logger.py              # ロギング設定（rich + ファイル）
├── templates/             # プロンプトテンプレート（Markdown）
│   ├── class_spec.md
│   ├── screen_spec.md
│   ├── batch_spec.md
│   └── api_spec.md
├── config/                # 動作確認用サンプル設定・対象一覧
│   ├── config.yaml
│   └── targets.txt
├── samples/               # サンプル解析対象ソース
├── docs/spec/             # 生成された仕様書の出力先（既定）
├── logs/                  # 実行ログ / 状態ファイル
│   ├── run.log            # 実行ログ（自動生成）
│   ├── status.json        # 実行状態（自動生成）
│   └── run.sample.log     # サンプル実行ログ
├── config.yaml.sample     # 設定サンプル
├── targets.txt            # 対象一覧サンプル
├── requirements.txt
└── pyproject.toml
```

---

## 設定ファイル

YAML で管理します（`config.yaml.sample` を参照）。相対パスは `project_root`（未指定時はカレントディレクトリ）を基準に解決されます。

| キー | 説明 | 既定値 |
| --- | --- | --- |
| `project_root` | 解析対象プロジェクトのルート | カレントディレクトリ |
| `targets_file` | 対象ファイル一覧のパス | `targets.txt` |
| `template` | 使用テンプレート名（拡張子省略可） | `class_spec` |
| `output_dir` | Markdown 出力ディレクトリ | `docs/spec` |
| `output_mode` | `overwrite`（上書き）/ `skip`（既存はスキップ） | `overwrite` |
| `preserve_directory` | 相対ディレクトリ構造を保持するか | `true` |
| `retry` | 失敗時の最大リトライ回数 | `3` |
| `codex_command` | Codex CLI 実行コマンド | `codex exec --sandbox workspace-write` |
| `templates_dir` | テンプレート配置ディレクトリ | `templates` |
| `status_file` | 実行状態ファイル | `logs/status.json` |
| `log_file` | 実行ログ | `logs/run.log` |
| `encoding_candidates` | 読込エンコーディング候補（順に試行） | `[utf-8, cp932]` |

---

## CLI オプション

```bash
python run.py --config config.yaml     # 設定ファイルを指定して実行
python run.py --targets targets.txt    # 対象一覧を上書き指定
python run.py --template class_spec     # テンプレートを上書き指定
python run.py --resume                  # 未処理ファイルのみ再開実行
python run.py --dry-run                 # Codex を起動せず実行予定のみ表示
```

| オプション | 説明 |
| --- | --- |
| `--config`, `-c` | YAML 設定ファイルのパス |
| `--targets`, `-t` | 対象ファイル一覧のパス（YAML より優先） |
| `--template` | 使用テンプレート名（YAML より優先） |
| `--output-dir`, `-o` | Markdown 出力ディレクトリ（YAML より優先） |
| `--output-mode` | `overwrite` / `skip`（YAML より優先） |
| `--resume` | 成功済みを除いた未処理ファイルのみ実行 |
| `--dry-run` | 対象一覧・出力予定・使用テンプレートのみ表示 |
| `--verbose`, `-v` | 詳細ログ（DEBUG）を出力 |

CLI 引数は YAML 設定より優先されます。

---

## プロンプトテンプレート

テンプレートは `templates/` 配下の Markdown ファイルとして管理します。Jinja2 により以下のプレースホルダを利用できます。

| プレースホルダ | 内容 |
| --- | --- |
| `{{TARGET}}` | 対象ファイル（相対パス） |
| `{{ABS_PATH}}` | 絶対パス |
| `{{FILE_NAME}}` | ファイル名 |
| `{{OUTPUT}}` | 出力 Markdown パス |
| `{{PROJECT_ROOT}}` | プロジェクトルート |

新しいテンプレートは `templates/` に Markdown を追加し、`--template <名前>` で指定するだけで利用できます。

---

## 対象ファイル一覧

対象ファイルは探索せず、事前に用意した一覧ファイルを読み込みます（`targets.txt` を参照）。

- リポジトリルート（`project_root`）からの相対パス
- 空行は無視
- `#` から始まる行はコメントとして無視
- 重複は自動除外
- 存在しないファイルは警告を出しスキップ

将来的に CSV / JSON / DB などへ差し替えられるよう、`TargetLoader` 抽象基底クラスを設計しています。

---

## 実行例

```bash
# サンプル設定で実行予定を確認（Codex は起動しない）
python run.py --config config/config.yaml --dry-run

# サンプル設定で仕様書を生成
python run.py --config config/config.yaml

# 途中停止後、未処理ファイルのみ再開
python run.py --config config/config.yaml --resume
```

実行後は次のサマリが表示されます。

- 総件数 / 成功件数 / 失敗件数 / スキップ件数 / 総実行時間

---

## トラブルシューティング

| 症状 | 対処 |
| --- | --- |
| `Codex コマンドが見つかりません` | Codex CLI がインストール済みか、`codex_command` のパスが正しいか確認してください。 |
| `対象一覧ファイルが見つかりません` | `targets_file` のパス（`project_root` 基準）を確認してください。 |
| `テンプレートが見つかりません` | `templates_dir` に対象テンプレートの Markdown があるか確認してください。 |
| 文字化けする | `encoding_candidates` に対象ファイルのエンコーディング（例: `cp932`）が含まれているか確認してください。 |
| 途中で止まった | `--resume` を付けて再実行すると、成功済みを除いた未処理ファイルのみ処理します。 |
| 失敗が続く | 失敗時は最大 `retry` 回リトライします。`logs/run.log` のエラーメッセージを確認してください。 |

---

## 設計方針と今後の拡張

- **責務分離**: 設定・対象読込・レンダリング・実行・保存・状態管理・ロギングをモジュール単位で分離（SOLID を意識）。
- **拡張ポイント**:
  - `TargetLoader` を実装することで、Git 差分 / フォルダ探索 / CSV / JSON / DB からの対象一覧取得へ差し替え可能。
  - テンプレートの追加のみで新しい仕様書種別に対応可能。
  - 実行状態を `status.json` に保持しているため、並列実行やキュー優先度制御の追加が容易。
  - 仕様書生成後の要件定義成果物（機能一覧・画面一覧・IF 一覧など）の自動生成を後段処理として追加可能。

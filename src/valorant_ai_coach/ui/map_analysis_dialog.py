"""Desktop controls for private, development-only Map analysis."""

from __future__ import annotations

import json
import os
import re
import shutil
import sys
from functools import partial
from pathlib import Path
from tempfile import TemporaryDirectory

from PySide6.QtCore import QProcess, QProcessEnvironment, QSettings
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from valorant_ai_coach.application.map_library import (
    MapLibraryEntry,
    compare_map_packages,
    list_map_packages,
)
from valorant_ai_coach.observability.sanitize import sanitize_text
from valorant_ai_coach.recordings.catalog import RecordingCatalog
from valorant_ai_coach.resources import resource_root
from valorant_ai_coach.temporal.replay import file_sha

_FIELDS = (
    ("video", "録画", False), ("catalog", "録画カタログ", True),
    ("setup", "解析設定 JSON", False), ("python", "解析用 Python", False),
    ("workspace", "作業フォルダー", True), ("library", "結果ライブラリ", True),
)
_PHASES = {
    "registration": "録画登録・用途の確認", "acquisition": "元動画から観測フレームを取得",
    "timeline": "共通タイムラインを作成", "reference": "参照方式でMap解析",
    "adaptive": "学習済みモデルでMap解析", "companion": "補助モデルでMap解析",
    "without_portraits": "肖像なしの比較解析", "ablation": "比較結果を集計",
    "standard": "標準結果を集計", "companion_composed": "補助モデル結果を集計",
    "recovered": "欠測を回復", "display_standard": "標準結果の表示を準備",
    "display_recovered": "回復後の表示を準備", "analysis_standard": "標準結果を評価",
    "analysis_recovered": "回復後の結果を評価", "publication": "ライブラリへ結果を登録",
}


def map_worker_root() -> Path:
    root = resource_root()
    bundled = root / "map_worker"
    return bundled if bundled.is_dir() else root


class MapAnalysisDialog(QDialog):
    def __init__(
        self, data_dir: Path, parent: QWidget | None = None, *, worker: Path | None = None,
    ) -> None:
        super().__init__(parent)
        self.worker = worker
        self.setWindowTitle("開発用 Map解析")
        self.resize(710, 540)
        self.preferences = QSettings(
            str(data_dir / "map_desktop_PRIVATE.ini"), QSettings.Format.IniFormat,
        )
        self.fields: dict[str, QLineEdit] = {}
        self.last_job: dict[str, str] = {}
        try:
            saved = json.loads(str(self.preferences.value("last_job", "{}")))
            if isinstance(saved, dict) and all(isinstance(v, str) for v in saved.values()):
                self.last_job = saved
        except ValueError:
            pass
        self.selected_receipt: Path | None = None
        self.entries: list[MapLibraryEntry] = []
        self._pause_dir: TemporaryDirectory[str] | None = None
        self._pending_close = False
        self._buffer = ""
        self.process = QProcess(self)
        self.process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self.process.readyReadStandardOutput.connect(self._read_output)
        self.process.finished.connect(self._finished)
        self.process.errorOccurred.connect(self._process_error)

        defaults = {
            "workspace": str(data_dir / "map_workflow"),
            "library": os.environ.get("VALORANT_MAP_LIBRARY", str(data_dir / "map_library")),
            "catalog": os.environ.get("VALORANT_RECORDING_CATALOG", ""),
            "python": (shutil.which("python") or shutil.which("python3") or ""
                       if getattr(sys, "frozen", False) else sys.executable),
        }
        layout = QVBoxLayout(self)
        form = QFormLayout()
        layout.addLayout(form)
        for key, title, directory in _FIELDS:
            field = QLineEdit(str(self.preferences.value(key, defaults.get(key, ""))))
            self.fields[key] = field
            row = QHBoxLayout()
            row.addWidget(field)
            pick = QPushButton("選択…")
            pick.clicked.connect(partial(self._pick, key, title, directory))
            row.addWidget(pick)
            if key == "catalog":
                create = QPushButton("新規作成…")
                create.clicked.connect(self._create_catalog)
                row.addWidget(create)
            form.addRow(title, row)

        self.distinct = QCheckBox("新規登録する録画は、既存試合の別録画・切り抜きではありません")
        layout.addWidget(self.distinct)
        actions = QHBoxLayout()
        layout.addLayout(actions)
        self.start_button = QPushButton("登録して解析")
        self.resume_button = QPushButton("前回の解析を再開")
        self.pause_button = QPushButton("中断")
        for button, handler in ((self.start_button, self.start_job),
                                (self.resume_button, self.resume_job),
                                (self.pause_button, self.pause_job)):
            button.clicked.connect(handler)
            actions.addWidget(button)
        self.status = QLabel("準備完了")
        layout.addWidget(self.status)
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.hide()
        layout.addWidget(self.progress)

        results = QFormLayout()
        layout.addLayout(results)
        self.recordings = QComboBox()
        self.before = QComboBox()
        self.after = QComboBox()
        self.recordings.currentIndexChanged.connect(self._versions)
        results.addRow("録画", self.recordings)
        results.addRow("基準結果", self.before)
        results.addRow("表示・比較対象", self.after)
        result_actions = QHBoxLayout()
        layout.addLayout(result_actions)
        for title, handler in (("一覧を更新", self.refresh_results),
                               ("選択結果を開く", self.open_result),
                               ("基準と比較", self.compare_results)):
            button = QPushButton(title)
            button.clicked.connect(handler)
            result_actions.addWidget(button)
        self.comparison = QPlainTextEdit()
        self.comparison.setReadOnly(True)
        self.comparison.setPlaceholderText("同一録画の結果を比較すると、位置秒と観測軌跡の差が表示されます。")
        layout.addWidget(self.comparison)
        self._running(False)
        self.refresh_results()

    def _pick(self, key: str, title: str, directory: bool) -> None:
        if self.process.state() != QProcess.ProcessState.NotRunning:
            return
        start = self.fields[key].text()
        if directory:
            value = QFileDialog.getExistingDirectory(self, title, start)
        else:
            value, _ = QFileDialog.getOpenFileName(self, title, start)
        if value:
            self.fields[key].setText(value)
            if key == "video":
                self.distinct.setChecked(False)

    def _create_catalog(self) -> None:
        if self.process.state() != QProcess.ProcessState.NotRunning:
            return
        start = self.fields["catalog"].text()
        value = QFileDialog.getExistingDirectory(
            self, "新規カタログを保存する非公開フォルダー", start,
        )
        if not value:
            return
        try:
            catalog = RecordingCatalog.create(Path(value))
            self.fields["catalog"].setText(str(catalog.root))
            self._save()
            self.status.setText("録画カタログを作成しました")
        except (OSError, ValueError) as exc:
            self.status.setText(sanitize_text(str(exc)))

    def _save(self) -> None:
        for key, field in self.fields.items():
            self.preferences.setValue(key, field.text())
        self.preferences.setValue("last_job", json.dumps(self.last_job, ensure_ascii=False))
        self.preferences.sync()

    def _running(self, running: bool) -> None:
        self.start_button.setEnabled(not running)
        self.resume_button.setEnabled(not running and bool(self.last_job))
        self.pause_button.setEnabled(running)
        for field in self.fields.values():
            field.setReadOnly(running)
        self.distinct.setEnabled(not running)
        self.progress.setVisible(running)

    def start_job(self) -> None:
        if self.process.state() != QProcess.ProcessState.NotRunning:
            return
        if not self.distinct.isChecked():
            self.status.setText("新規登録する録画が別エンコードや切り抜きではないことを確認してください。")
            return
        try:
            job = {key: field.text().strip() for key, field in self.fields.items()}
            if not all(job.values()):
                raise ValueError("録画・カタログ・設定・Python・出力先を選択してください")
            for key in ("video", "setup", "python"):
                if not Path(job[key]).is_file():
                    raise ValueError("録画・解析設定・Pythonをファイルとして選択してください")
            job["setup_sha256"] = file_sha(Path(job["setup"]))
            info = Path(job["video"]).stat()
            job["video_stat"] = f"{info.st_size}:{info.st_mtime_ns}"
            self.last_job = job
            self._save()
            self._launch()
        except (OSError, ValueError) as exc:
            self.status.setText(sanitize_text(str(exc)))

    def resume_job(self) -> None:
        if self.process.state() != QProcess.ProcessState.NotRunning or not self.last_job:
            return
        try:
            if file_sha(Path(self.last_job["setup"])) != self.last_job["setup_sha256"]:
                raise ValueError(
                    "前回の設定ファイルが変わりました。新しい解析として開始してください"
                )
            if "recording_id" not in self.last_job:
                info = Path(self.last_job["video"]).stat()
                if f"{info.st_size}:{info.st_mtime_ns}" != self.last_job["video_stat"]:
                    raise ValueError("前回の録画ファイルが変わりました")
            for key, field in self.fields.items():
                field.setText(self.last_job[key])
            self._launch()
        except (OSError, ValueError, KeyError) as exc:
            self.status.setText(sanitize_text(str(exc)))

    def _launch(self) -> None:
        root = map_worker_root()
        program = self.worker or root / "scripts/map_learning/workflow.py"
        if not program.is_file():
            raise ValueError("Map解析ワーカーが見つかりません")
        job = self.last_job
        self._pause_dir = TemporaryDirectory(prefix="valorant-map-job-")
        pause_file = Path(self._pause_dir.name) / "pause"
        options = [item for key in ("catalog", "setup", "workspace", "library")
                   for item in (f"--{key}", job[key])]
        selection = (["--recording-id", job["recording_id"]] if "recording_id" in job
                     else ["--video", job["video"], "--confirm-distinct"])
        environment = QProcessEnvironment.systemEnvironment()
        environment.remove("PYTHONHOME")
        inherited = environment.value("PYTHONPATH")
        paths = [str(root), str(root / "src")]
        if inherited:
            paths.append(inherited)
        environment.insert("PYTHONPATH", os.pathsep.join(paths))
        environment.insert("PYTHONIOENCODING", "utf-8")
        self.process.setProcessEnvironment(environment)
        self.process.setWorkingDirectory(str(resource_root()))
        self._buffer = ""
        self.progress.setRange(0, 0)
        self.status.setText("解析を起動中")
        self._running(True)
        self.process.start(
            job["python"], ["-u", str(program), *selection, *options,
                            "--pause-file", str(pause_file)],
        )

    def pause_job(self) -> None:
        if self._pause_dir is not None:
            (Path(self._pause_dir.name) / "pause").touch()
            self.pause_button.setEnabled(False)
            self.status.setText("中断要求を送信しました。処理の終了を待っています")

    def _read_output(self) -> None:
        data = self.process.readAllStandardOutput().data()
        self._buffer += bytes(data).decode("utf-8", errors="replace")
        lines = self._buffer.split("\n")
        self._buffer = lines.pop()[-1000:]
        for line in lines:
            line = line.strip()
            if line.startswith("Map registered recording: "):
                self.last_job["recording_id"] = line.removeprefix("Map registered recording: ")
                self._save()
            elif self.pause_button.isEnabled():
                stage = _PHASES.get(line.removeprefix("Map workflow phase: "))
                if stage:
                    self.progress.setRange(0, 0)
                    self.status.setText(stage)
                elif match := re.fullmatch(r"Measured (\d+) of (\d+) native frames", line):
                    self.progress.setRange(0, int(match[2]))
                    self.progress.setValue(int(match[1]))
                    self.status.setText(f"共通タイムライン  {match[1]} / {match[2]} フレーム")
            if line.startswith((
                "ValueError:", "RuntimeError:", "ModuleNotFoundError:", "OSError:",
            )):
                self.comparison.setPlainText(sanitize_text(line))

    def _finished(self, code: int, what: QProcess.ExitStatus) -> None:
        self._read_output()
        self._cleanup()
        self._running(False)
        if what == QProcess.ExitStatus.NormalExit and code == 0:
            self.refresh_results()
            self.status.setText("解析が完了し、結果をローカルに保存しました")
        elif what == QProcess.ExitStatus.NormalExit and code == 75:
            self.status.setText("中断しました。完了済みの工程から再開できます")
        else:
            self.status.setText("解析が終了しました。解析環境・設定を確認し、再開できます")
        if self._pending_close:
            super().reject()

    def _process_error(self, error: QProcess.ProcessError) -> None:
        if error == QProcess.ProcessError.FailedToStart:
            self._cleanup()
            self._running(False)
            self.status.setText("解析用Pythonを起動できません")

    def _cleanup(self) -> None:
        if self._pause_dir is not None:
            self._pause_dir.cleanup()
            self._pause_dir = None

    def refresh_results(self) -> None:
        recording = self.recordings.currentData()
        try:
            location = self.fields["library"].text().strip()
            self.entries = list_map_packages(Path(location), all_versions=True) if location else []
        except (OSError, ValueError, KeyError, TypeError) as exc:
            self.entries = []
            self.status.setText(sanitize_text(str(exc)))
        self.recordings.clear()
        labels = {entry.recording_id: entry.label for entry in reversed(self.entries)}
        for identifier, label in labels.items():
            self.recordings.addItem(label, identifier)
        match = self.recordings.findData(recording)
        if match >= 0:
            self.recordings.setCurrentIndex(match)
        self._versions()

    def _versions(self) -> None:
        variants = [entry for entry in self.entries
                    if entry.recording_id == self.recordings.currentData()]
        for combo in (self.before, self.after):
            combo.clear()
            for entry in variants:
                title = entry.variant or "既存結果"
                combo.addItem(f"{title} ({entry.receipt.name[:8]})", str(entry.receipt))
        if len(variants) > 1:
            self.before.setCurrentIndex(1)

    def open_result(self) -> None:
        path = self.after.currentData()
        if self.process.state() == QProcess.ProcessState.NotRunning and isinstance(path, str):
            self.selected_receipt = Path(path)
            self.accept()

    def compare_results(self) -> None:
        a, b = self.before.currentData(), self.after.currentData()
        if not isinstance(a, str) or not isinstance(b, str) or a == b:
            self.comparison.setPlainText("異なる2つの結果を選択してください。")
            return
        try:
            result = compare_map_packages(Path(a), Path(b))
            lines = []
            for mode, report in result.items():
                label = "標準" if mode == "standard" else "欠測回復後"
                lines.append(
                    f"{label}  位置 {report['before_seconds']} → {report['after_seconds']} 秒"
                    f"（追加 {report['added_seconds']}、消失 {report['lost_seconds']}）\n"
                    f"観測軌跡の接続  追加 {report['added_edges']}、消失 {report['lost_edges']}"
                )
            self.comparison.setPlainText("\n\n".join(lines))
        except (OSError, ValueError, KeyError, TypeError) as exc:
            self.comparison.setPlainText(sanitize_text(str(exc)))

    def reject(self) -> None:
        if self.process.state() != QProcess.ProcessState.NotRunning:
            self._pending_close = True
            self.pause_job()
        else:
            self._save()
            super().reject()

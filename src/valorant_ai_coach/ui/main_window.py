from __future__ import annotations

import logging
import threading
import uuid
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, QRunnable, Qt, QThreadPool, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import QAction, QCloseEvent
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSlider,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from valorant_ai_coach.observability.sanitize import sanitize_text

from .settings_dialog import SettingsDialog
from .workers import AnalysisWorker, VideoProbeWorker

LOGGER = logging.getLogger(__name__)


class _AudioProbeSignals(QObject):
    completed = Signal(str, object)
    failed = Signal(str, str)
    cancelled = Signal(str)


class _AudioProbeWorker(QRunnable):
    """Read audio stream descriptors without blocking the Qt event loop."""

    def __init__(self, backend: Any, video_path: Path, request_id: str) -> None:
        super().__init__()
        self.backend = backend
        self.video_path = Path(video_path)
        self.request_id = request_id
        self.cancel_event = threading.Event()
        self.signals = _AudioProbeSignals()

    def cancel(self) -> None:
        self.cancel_event.set()

    @Slot()
    def run(self) -> None:
        try:
            metadata = self.backend.probe_video(
                self.video_path,
                cancel_event=self.cancel_event,
            )
            if self.cancel_event.is_set():
                self.signals.cancelled.emit(self.request_id)
            else:
                self.signals.completed.emit(self.request_id, metadata)
        except InterruptedError:
            self.signals.cancelled.emit(self.request_id)
        except Exception as exc:
            if self.cancel_event.is_set():
                self.signals.cancelled.emit(self.request_id)
            else:
                self.signals.failed.emit(self.request_id, str(exc))


class MainWindow(QMainWindow):
    def __init__(self, backend: Any) -> None:
        super().__init__()
        self.backend = backend
        self.video_path: Path | None = None
        self.worker: AnalysisWorker | None = None
        self.probe_worker: VideoProbeWorker | None = None
        self._probe_request_id: str | None = None
        self.audio_probe_worker: _AudioProbeWorker | None = None
        self._audio_probe_request_id: str | None = None
        self._audio_tracks: tuple[Any, ...] = ()
        self._audio_track_cache: dict[Path, tuple[Any, ...]] = {}
        self._current_media_path: Path | None = None
        self._pending_audio_track_index: int | None = None
        self._player_audio_source_ready = False
        self._audio_track_refresh_attempts = 0
        self._audio_track_combos: list[QComboBox] = []
        self._close_after_worker = False
        self._allow_close = False
        self.current_evaluations: list[Any] = []
        self.pool = QThreadPool.globalInstance()

        self.setWindowTitle("VALORANT AI Coach")
        self.setMinimumSize(960, 680)
        self.resize(1280, 840)
        self.setStyleSheet(self._style_sheet())

        self.audio = QAudioOutput(self)
        self.audio.setVolume(0.8)
        self.player = QMediaPlayer(self)
        self.player.setAudioOutput(self.audio)
        self.player.positionChanged.connect(self._position_changed)
        self.player.durationChanged.connect(self._duration_changed)
        self.player.errorOccurred.connect(self._media_error)
        self.player.mediaStatusChanged.connect(self._media_status_changed)
        for signal_name in ("audioTracksChanged", "tracksChanged"):
            signal = getattr(self.player, signal_name, None)
            if signal is not None and hasattr(signal, "connect"):
                signal.connect(self._player_audio_tracks_changed)

        self.pages = QStackedWidget()
        self.home_page = self._build_home()
        self.progress_page = self._build_progress()
        self.results_page = self._build_results()
        self.pages.addWidget(self.home_page)
        self.pages.addWidget(self.progress_page)
        self.pages.addWidget(self.results_page)
        self.setCentralWidget(self.pages)

        settings_action = QAction("設定", self)
        settings_action.setShortcut("Ctrl+,")
        settings_action.triggered.connect(self._open_settings)
        self.menuBar().addAction(settings_action)
        self.statusBar().showMessage("準備完了")
        self._load_history()
        self._show_page(self.home_page)

        if backend.startup_warning:
            QTimer.singleShot(
                0,
                lambda: QMessageBox.warning(
                    self,
                    "設定を一時的に無効化しました",
                    "保存された設定で初期化できなかったため、この起動中は安全なMock設定を"
                    f"使用します。設定画面で修正してください。\n\n{sanitize_text(backend.startup_warning)}",
                ),
            )

    def _build_home(self) -> QWidget:
        page = QWidget()
        root = QVBoxLayout(page)
        root.setContentsMargins(24, 20, 24, 20)
        title = QLabel("VALORANT AI Coach")
        title.setObjectName("pageTitle")
        subtitle = QLabel("録画から、再現可能なGOOD・改善点と根拠クリップを作成します")
        subtitle.setObjectName("muted")
        root.addWidget(title)
        root.addWidget(subtitle)

        action_row = QHBoxLayout()
        self.select_button = QPushButton("録画を選択")
        self.select_button.clicked.connect(self._select_video)
        self.start_button = QPushButton("解析を開始")
        self.start_button.setObjectName("primaryButton")
        self.start_button.setEnabled(False)
        self.start_button.clicked.connect(self._start_analysis)
        self.resume_button = QPushButton("選択した解析を再開")
        self.resume_button.setEnabled(False)
        self.resume_button.clicked.connect(self._resume_selected_analysis)
        self.delete_button = QPushButton("選択した履歴を削除")
        self.delete_button.setEnabled(False)
        self.delete_button.clicked.connect(self._delete_selected_match)
        self.mode_label = QLabel()
        self.mode_label.setObjectName("modeBadge")
        self._refresh_mode_label()
        action_row.addWidget(self.select_button)
        action_row.addWidget(self.start_button)
        action_row.addWidget(self.resume_button)
        action_row.addWidget(self.delete_button)
        action_row.addWidget(self.mode_label)
        action_row.addStretch()
        root.addLayout(action_row)

        self.file_label = QLabel("MP4 / MKV / MOV / AVI / WebM を選択してください")
        self.file_label.setWordWrap(True)
        self.metadata_label = QLabel("")
        self.metadata_label.setObjectName("muted")
        self.metadata_label.setWordWrap(True)
        root.addWidget(self.file_label)
        root.addWidget(self.metadata_label)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        history_box = QWidget()
        history_layout = QVBoxLayout(history_box)
        history_layout.setContentsMargins(0, 0, 8, 0)
        history_layout.addWidget(QLabel("解析履歴（ダブルクリックで開く）"))
        self.history = QListWidget()
        self.history.itemDoubleClicked.connect(self._open_history_item)
        self.history.currentItemChanged.connect(self._history_selection_changed)
        history_layout.addWidget(self.history)
        splitter.addWidget(history_box)
        self.home_video = QVideoWidget()
        self.home_video.setMinimumHeight(280)
        splitter.addWidget(self.home_video)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([390, 810])
        root.addWidget(splitter, 1)

        controls = QHBoxLayout()
        play = QPushButton("再生 / 一時停止")
        play.clicked.connect(self._toggle_playback)
        self.home_seek = QSlider(Qt.Orientation.Horizontal)
        self.home_seek.sliderMoved.connect(self.player.setPosition)
        self.home_time = QLabel("00:00 / 00:00")
        self.home_audio_track = self._new_audio_track_combo()
        controls.addWidget(play)
        controls.addWidget(self.home_seek, 1)
        controls.addWidget(self.home_audio_track)
        controls.addWidget(self.home_time)
        root.addLayout(controls)
        return page

    def _build_progress(self) -> QWidget:
        page = QWidget()
        root = QVBoxLayout(page)
        root.setContentsMargins(40, 40, 40, 40)
        title = QLabel("録画を解析しています")
        title.setObjectName("pageTitle")
        self.progress_text = QLabel("準備しています…")
        self.progress_text.setWordWrap(True)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_log = QListWidget()
        cancel = QPushButton("キャンセル")
        cancel.clicked.connect(self._cancel_analysis)
        root.addWidget(title)
        root.addWidget(self.progress_text)
        root.addWidget(self.progress_bar)
        root.addWidget(QLabel("処理ログ"))
        root.addWidget(self.progress_log, 1)
        root.addWidget(cancel, 0, Qt.AlignmentFlag.AlignLeft)
        return page

    def _build_results(self) -> QWidget:
        page = QWidget()
        root = QVBoxLayout(page)
        root.setContentsMargins(20, 16, 20, 20)
        header = QHBoxLayout()
        back = QPushButton("← ホーム")
        back.clicked.connect(lambda: self._show_page(self.home_page))
        self.result_title = QLabel("解析結果")
        self.result_title.setObjectName("pageTitle")
        header.addWidget(back)
        header.addWidget(self.result_title)
        header.addStretch()
        root.addLayout(header)

        self.result_diagnostics = QLabel()
        self.result_diagnostics.setWordWrap(True)
        self.result_diagnostics.setObjectName("muted")
        self.result_diagnostics.setTextFormat(Qt.TextFormat.PlainText)
        self.result_diagnostics.setVisible(False)
        root.addWidget(self.result_diagnostics)

        filters = QHBoxLayout()
        self.label_filter = QComboBox()
        self.label_filter.addItem("評価（GOOD / 改善）", "scored")
        self.label_filter.addItem("GOOD", "good")
        self.label_filter.addItem("改善", "improve")
        self.label_filter.addItem("要確認（低信頼）", "review")
        self.label_filter.addItem("診断: UNSCORED", "unscored")
        self.label_filter.addItem("すべて", "all")
        self.category_filter = QComboBox()
        self.category_filter.addItem("すべてのカテゴリ", "all")
        self.round_filter = QComboBox()
        self.round_filter.addItem("すべてのラウンド", -1)
        self.label_filter.currentIndexChanged.connect(self._render_cards)
        self.category_filter.currentIndexChanged.connect(self._render_cards)
        self.round_filter.currentIndexChanged.connect(self._render_cards)
        filters.addWidget(QLabel("表示"))
        filters.addWidget(self.label_filter)
        filters.addWidget(self.category_filter)
        filters.addWidget(self.round_filter)
        filters.addStretch()
        root.addLayout(filters)

        content = QSplitter(Qt.Orientation.Horizontal)
        video_box = QWidget()
        video_layout = QVBoxLayout(video_box)
        self.result_player = QVideoWidget()
        self.result_player.setMinimumSize(420, 260)
        video_layout.addWidget(self.result_player, 1)
        controls = QHBoxLayout()
        play = QPushButton("再生 / 一時停止")
        play.clicked.connect(self._toggle_playback)
        replay = QPushButton("先頭から")
        replay.clicked.connect(self._replay)
        self.result_seek = QSlider(Qt.Orientation.Horizontal)
        self.result_seek.sliderMoved.connect(self.player.setPosition)
        self.result_time = QLabel("00:00 / 00:00")
        self.result_audio_track = self._new_audio_track_combo()
        controls.addWidget(play)
        controls.addWidget(replay)
        controls.addWidget(self.result_seek, 1)
        controls.addWidget(self.result_audio_track)
        controls.addWidget(self.result_time)
        video_layout.addLayout(controls)
        content.addWidget(video_box)

        self.cards_container = QWidget()
        self.cards_layout = QVBoxLayout(self.cards_container)
        self.cards_layout.addStretch()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.cards_container)
        content.addWidget(scroll)
        content.setSizes([570, 650])
        root.addWidget(content, 1)
        return page

    def _select_video(self) -> None:
        selected, _ = QFileDialog.getOpenFileName(
            self,
            "VALORANT録画を選択",
            "",
            "動画 (*.mp4 *.mkv *.mov *.avi *.webm);;すべてのファイル (*)",
        )
        if not selected:
            return
        if self.probe_worker is not None:
            self.probe_worker.cancel()
        if self.audio_probe_worker is not None:
            self.audio_probe_worker.cancel()
        self._audio_probe_request_id = None
        self._clear_audio_track_metadata()
        self.player.stop()
        self._player_audio_source_ready = False
        self._current_media_path = None
        self.player.setSource(QUrl())
        selected_path = Path(selected)
        request_id = uuid.uuid4().hex
        self._probe_request_id = request_id
        self.video_path = None
        self.select_button.setEnabled(False)
        self.start_button.setEnabled(False)
        self.resume_button.setEnabled(False)
        self.delete_button.setEnabled(False)
        self.file_label.setText(str(selected_path))
        self.metadata_label.setText("動画メタデータを取得しています…")
        self.probe_worker = VideoProbeWorker(self.backend, selected_path, request_id)
        self.probe_worker.signals.completed.connect(self._on_probe_completed)
        self.probe_worker.signals.failed.connect(self._on_probe_failed)
        self.probe_worker.signals.cancelled.connect(self._on_probe_cancelled)
        self.pool.start(self.probe_worker)

    def _on_probe_completed(self, request_id: str, selected: str, metadata: Any) -> None:
        if request_id != self._probe_request_id:
            return
        self.probe_worker = None
        self._probe_request_id = None
        if self._finish_pending_close():
            return
        self.select_button.setEnabled(True)
        self._history_selection_changed(self.history.currentItem(), None)
        self.video_path = Path(selected)
        audio = "あり" if metadata.has_audio else "なし"
        self.metadata_label.setText(
            f"{metadata.width}×{metadata.height} / {metadata.fps:.2f} fps / "
            f"{metadata.duration_sec:.1f}秒 / {metadata.video_codec} / 音声 {audio} / "
            f"{metadata.file_size / (1024 * 1024):.1f} MB"
        )
        self.start_button.setEnabled(True)
        self.player.setVideoOutput(self.home_video)
        source = self.video_path.resolve()
        self._current_media_path = source
        self._audio_track_cache[source] = tuple(getattr(metadata, "audio_tracks", ()) or ())
        self._player_audio_source_ready = False
        self.player.setSource(QUrl.fromLocalFile(str(self.video_path)))
        self._set_audio_track_metadata(self._audio_track_cache[source])

    def _on_probe_failed(self, request_id: str, message: str, details: str) -> None:
        if request_id != self._probe_request_id:
            return
        LOGGER.error("Video probe failed: %s\n%s", message, details)
        self.probe_worker = None
        self._probe_request_id = None
        self.video_path = None
        self._current_media_path = None
        self._clear_audio_track_metadata()
        self.start_button.setEnabled(False)
        self.metadata_label.setText("動画メタデータを取得できませんでした")
        if self._finish_pending_close():
            return
        self.select_button.setEnabled(True)
        self._history_selection_changed(self.history.currentItem(), None)
        QMessageBox.critical(self, "動画を開けません", sanitize_text(message))

    def _on_probe_cancelled(self, request_id: str) -> None:
        if request_id != self._probe_request_id:
            return
        self.probe_worker = None
        self._probe_request_id = None
        if self._finish_pending_close():
            return
        self.select_button.setEnabled(True)
        self._history_selection_changed(self.history.currentItem(), None)
        self.metadata_label.setText("動画メタデータ取得をキャンセルしました")

    def _start_analysis(self) -> None:
        if self.video_path is None:
            return
        self._launch_analysis(self.video_path)

    def _launch_analysis(
        self, video_path: Path, *, match_id: str | None = None, resume: bool = False
    ) -> None:
        if self.probe_worker is not None:
            return
        settings = self.backend.get_settings()
        if not settings.mock_ai and not self.backend.has_api_key():
            QMessageBox.warning(
                self,
                "APIキーが必要です",
                "設定画面でAPIキーを登録するか、Mock AIを有効にしてください。",
            )
            return
        self.player.pause()
        self._prepare_progress("動画前処理を開始しています…")
        self._show_page(self.progress_page)
        self.worker = AnalysisWorker(
            self.backend,
            video_path,
            match_id=match_id,
            resume=resume,
        )
        self.worker.signals.progress.connect(self._on_progress)
        self.worker.signals.completed.connect(self._on_completed)
        self.worker.signals.failed.connect(self._on_failed)
        self.worker.signals.cancelled.connect(self._on_cancelled)
        self.pool.start(self.worker)

    def _resume_selected_analysis(self) -> None:
        item = self.history.currentItem()
        if item is None:
            return
        match_id = str(item.data(Qt.ItemDataRole.UserRole))
        source_path = Path(str(item.data(Qt.ItemDataRole.UserRole + 2)))
        if not source_path.is_file():
            QMessageBox.warning(
                self,
                "解析を再開できません",
                f"元動画が見つかりません。\n{source_path.name}",
            )
            return
        self.video_path = source_path
        self.file_label.setText(str(source_path))
        self._launch_analysis(source_path, match_id=match_id, resume=True)

    def _cancel_analysis(self) -> None:
        if self.worker is not None:
            self.worker.cancel()
            self.progress_text.setText("安全な区切りでキャンセルしています…")

    def _prepare_progress(self, message: str) -> None:
        self.progress_bar.setValue(0)
        self.progress_text.setText(message)
        self.progress_log.clear()
        self.progress_log.addItem(f"  0%  {message}")

    def _on_progress(self, value: int, text: str) -> None:
        bounded = max(0, min(100, value))
        self.progress_bar.setValue(bounded)
        self.progress_text.setText(text)
        entry = f"{bounded:3d}%  {text}"
        last = self.progress_log.item(self.progress_log.count() - 1)
        if last is None or last.text() != entry:
            self.progress_log.addItem(entry)
            while self.progress_log.count() > 200:
                self.progress_log.takeItem(0)
            self.progress_log.scrollToBottom()

    def _on_completed(self, match_id: str) -> None:
        self.worker = None
        if self._finish_pending_close():
            return
        self._load_history()
        self._show_results(match_id)

    def _on_cancelled(self) -> None:
        self.worker = None
        if self._finish_pending_close():
            return
        self.statusBar().showMessage("解析をキャンセルしました")
        self._load_history()
        self._show_page(self.home_page)

    def _on_failed(self, message: str, details: str) -> None:
        LOGGER.error("Analysis failed: %s\n%s", message, details)
        self.worker = None
        if self._finish_pending_close():
            return
        dialog = QMessageBox(self)
        dialog.setIcon(QMessageBox.Icon.Critical)
        dialog.setWindowTitle("解析に失敗しました")
        dialog.setText(sanitize_text(message))
        dialog.setInformativeText("設定、FFmpeg/FFprobe、ログを確認してください。")
        dialog.exec()
        self._load_history()
        self._show_page(self.home_page)

    def _load_history(self) -> None:
        self.history.clear()
        for match in self.backend.list_matches():
            metadata = match.get("metadata", {})
            duration = float(metadata.get("duration_sec", 0.0))
            label = (
                f"{str(match['created_at']).replace('T', ' ')[:19]}\n"
                f"{Path(str(match['source_video_path'])).name}  "
                f"{duration:.0f}秒  [{match['status']}]"
            )
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, str(match["match_id"]))
            item.setData(Qt.ItemDataRole.UserRole + 1, str(match["status"]))
            item.setData(Qt.ItemDataRole.UserRole + 2, str(match["source_video_path"]))
            self.history.addItem(item)
        self.resume_button.setEnabled(False)
        self.delete_button.setEnabled(False)

    def _history_selection_changed(
        self, current: QListWidgetItem | None, _previous: QListWidgetItem | None
    ) -> None:
        if current is None or self.worker is not None or self.probe_worker is not None:
            self.resume_button.setEnabled(False)
            self.delete_button.setEnabled(False)
            return
        match_id = str(current.data(Qt.ItemDataRole.UserRole))
        self.delete_button.setEnabled(True)
        self.resume_button.setEnabled(self.backend.can_resume(match_id))

    def _delete_selected_match(self) -> None:
        if self.worker is not None or self.probe_worker is not None:
            return
        item = self.history.currentItem()
        if item is None:
            return
        match_id = str(item.data(Qt.ItemDataRole.UserRole))
        source_path = Path(str(item.data(Qt.ItemDataRole.UserRole + 2)))
        answer = QMessageBox.question(
            self,
            "解析履歴を削除しますか",
            (
                f"{source_path.name} の解析結果、根拠フレーム、生成クリップを削除します。\n"
                "元の録画ファイルは削除しません。この操作は取り消せません。"
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.player.stop()
        try:
            self.backend.delete_match(match_id)
        except Exception as exc:
            LOGGER.exception("Could not delete match %s", match_id)
            QMessageBox.critical(self, "解析履歴を削除できません", sanitize_text(str(exc)))
            return
        self.current_evaluations = []
        self._load_history()
        self.statusBar().showMessage("解析履歴を削除しました（元動画は保持されています）", 8000)

    def _open_history_item(self, item: QListWidgetItem) -> None:
        self._show_results(str(item.data(Qt.ItemDataRole.UserRole)))

    def _show_results(self, match_id: str) -> None:
        try:
            result = self.backend.get_match_result(match_id)
        except Exception as exc:
            LOGGER.exception("Could not open match result %s", match_id)
            QMessageBox.critical(self, "解析結果を開けません", sanitize_text(str(exc)))
            return
        self.player.stop()
        self._player_audio_source_ready = False
        self.player.setSource(QUrl())
        if self.audio_probe_worker is not None:
            self.audio_probe_worker.cancel()
        self._audio_probe_request_id = None
        self._clear_audio_track_metadata()
        self.current_evaluations = list(result.evaluations)
        context = [
            value
            for value in (
                f"Map: {result.map_name}" if result.map_name else None,
                f"Agent: {result.player_agent}" if result.player_agent else None,
                "一部のラウンドまたはクリップで失敗"
                if result.status == "partial"
                else None,
                "解析に失敗（履歴から再開可能）"
                if result.status == "failed"
                else None,
            )
            if value
        ]
        suffix = f" — {' / '.join(context)}" if context else ""
        self.result_title.setText(
            f"GOOD {result.good_count} / 改善 {result.improve_count} / "
            f"UNSCORED {result.unscored_count}{suffix}"
        )
        diagnostics = getattr(result, "diagnostics", ())
        self.result_diagnostics.setText("\n".join(diagnostics[:8]))
        self.result_diagnostics.setVisible(bool(diagnostics))
        self.category_filter.blockSignals(True)
        self.round_filter.blockSignals(True)
        self.category_filter.clear()
        self.category_filter.addItem("すべてのカテゴリ", "all")
        for category in sorted({item.category for item in result.evaluations}):
            self.category_filter.addItem(category, category)
        self.round_filter.clear()
        self.round_filter.addItem("すべてのラウンド", -1)
        for round_no in sorted(
            {item.round_no for item in result.evaluations if item.round_no is not None}
        ):
            self.round_filter.addItem(f"ラウンド {round_no}", round_no)
        self.category_filter.blockSignals(False)
        self.round_filter.blockSignals(False)
        self.label_filter.setCurrentIndex(0)
        self._render_cards()
        self._show_page(self.results_page)

    def _render_cards(self) -> None:
        while self.cards_layout.count() > 1:
            child = self.cards_layout.takeAt(0)
            if child is not None and (widget := child.widget()) is not None:
                widget.deleteLater()
        label_filter = self.label_filter.currentData()
        category = self.category_filter.currentData()
        round_no = self.round_filter.currentData()
        displayed = 0
        for evaluation in self.current_evaluations:
            if label_filter == "scored" and evaluation.label not in {"good", "improve"}:
                continue
            if label_filter == "review" and not evaluation.needs_review:
                continue
            if label_filter not in {"all", "scored", "review"} and evaluation.label != label_filter:
                continue
            if category != "all" and evaluation.category != category:
                continue
            if round_no != -1 and evaluation.round_no != round_no:
                continue
            self.cards_layout.insertWidget(
                self.cards_layout.count() - 1, self._evaluation_card(evaluation)
            )
            displayed += 1
        if displayed == 0:
            empty = QLabel("この条件に一致する評価はありません。")
            empty.setObjectName("muted")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.cards_layout.insertWidget(0, empty)

    def _evaluation_card(self, evaluation: Any) -> QWidget:
        card = QFrame()
        card.setObjectName("evaluationCard")
        card.setFrameShape(QFrame.Shape.StyledPanel)
        layout = QVBoxLayout(card)
        colors = {"good": "#58d68d", "improve": "#ffb454", "unscored": "#9ca3af"}
        names = {"good": "GOOD", "improve": "IMPROVE", "unscored": "UNSCORED"}
        head = QLabel(f"{names[evaluation.label]}  {evaluation.title}")
        head.setStyleSheet(f"font-size: 17px; font-weight: 700; color: {colors[evaluation.label]};")
        layout.addWidget(head)
        round_text = f"Round {evaluation.round_no}" if evaluation.round_no else "Match"
        related = (
            f" / 関連: {', '.join(evaluation.related_rule_ids)}"
            if evaluation.related_rule_ids
            else ""
        )
        meta = QLabel(
            f"{evaluation.rule_id}{related} / {evaluation.category} / {round_text} / "
            f"{evaluation.decision_source} / 信頼度 {evaluation.confidence:.0%}"
        )
        meta.setObjectName("muted")
        meta.setWordWrap(True)
        layout.addWidget(meta)
        if evaluation.needs_review:
            review = QLabel("要確認: 信頼度0.75未満の参考評価です")
            review.setObjectName("reviewBadge")
            layout.addWidget(review)
        situation = QLabel(f"状況: {evaluation.situation}")
        situation.setWordWrap(True)
        layout.addWidget(situation)
        if evaluation.evidence:
            evidence = QLabel("根拠:\n" + "\n".join(f"• {line}" for line in evaluation.evidence))
            evidence.setWordWrap(True)
            layout.addWidget(evidence)
        reason = QLabel(f"理由: {evaluation.reason}")
        reason.setWordWrap(True)
        layout.addWidget(reason)
        if evaluation.improvement:
            improvement = QLabel(f"次回: {evaluation.improvement}")
            improvement.setWordWrap(True)
            improvement.setObjectName("improvement")
            layout.addWidget(improvement)
        if evaluation.missing_information:
            missing = QLabel(
                "不足情報:\n" + "\n".join(f"• {line}" for line in evaluation.missing_information)
            )
            missing.setWordWrap(True)
            layout.addWidget(missing)
        if evaluation.unscored_reason_code:
            code = QLabel(f"診断コード: {evaluation.unscored_reason_code}")
            code.setObjectName("muted")
            layout.addWidget(code)
        if evaluation.requires_round_context:
            context = QLabel("この評価は短いクリップだけでなくラウンド全体の文脈を参照しています")
            context.setWordWrap(True)
            context.setObjectName("muted")
            layout.addWidget(context)
        if evaluation.clip_path:
            play = QPushButton("根拠クリップを再生")
            play.clicked.connect(
                lambda _checked=False, path=evaluation.clip_path: self._play_clip(path)
            )
            layout.addWidget(play, 0, Qt.AlignmentFlag.AlignLeft)
        return card

    def _play_clip(self, path: str) -> None:
        clip = Path(path)
        if not clip.is_file():
            QMessageBox.warning(
                self, "クリップを再生できません", "クリップファイルが見つかりません"
            )
            return
        self.player.setVideoOutput(self.result_player)
        self._current_media_path = clip.resolve()
        self._player_audio_source_ready = False
        self.player.setSource(QUrl.fromLocalFile(str(clip)))
        cached_tracks = self._audio_track_cache.get(self._current_media_path)
        if cached_tracks is None:
            self._clear_audio_track_metadata()
            self._start_audio_probe(clip)
        else:
            self._set_audio_track_metadata(cached_tracks)
        self.player.play()

    def _show_page(self, page: QWidget) -> None:
        self.pages.setCurrentWidget(page)
        if page is self.home_page:
            self.player.setVideoOutput(self.home_video)
            if self.video_path is not None:
                self.player.stop()
                self._current_media_path = self.video_path.resolve()
                self._player_audio_source_ready = False
                self.player.setSource(QUrl.fromLocalFile(str(self.video_path)))
                cached_tracks = self._audio_track_cache.get(self._current_media_path)
                if cached_tracks is None:
                    self._clear_audio_track_metadata()
                    self._start_audio_probe(self.video_path)
                else:
                    self._set_audio_track_metadata(cached_tracks)
        elif page is self.results_page:
            self.player.setVideoOutput(self.result_player)

    def _toggle_playback(self) -> None:
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
        else:
            self.player.play()

    def _replay(self) -> None:
        self.player.setPosition(0)
        self.player.play()

    def _position_changed(self, position: int) -> None:
        self.home_seek.setValue(position)
        self.result_seek.setValue(position)
        text = f"{self._format_millis(position)} / {self._format_millis(self.player.duration())}"
        self.home_time.setText(text)
        self.result_time.setText(text)

    def _duration_changed(self, duration: int) -> None:
        self.home_seek.setRange(0, duration)
        self.result_seek.setRange(0, duration)
        self._position_changed(self.player.position())

    def _media_error(self, _error: QMediaPlayer.Error, error_string: str) -> None:
        if error_string:
            self.statusBar().showMessage(f"動画再生エラー: {error_string}", 8000)

    def _new_audio_track_combo(self) -> QComboBox:
        combo = QComboBox()
        combo.setMinimumContentsLength(18)
        combo.setToolTip("再生する音声トラック")
        combo.setVisible(False)
        combo.currentIndexChanged.connect(
            lambda _index, selected=combo: self._audio_track_selected(selected)
        )
        self._audio_track_combos.append(combo)
        return combo

    def _start_audio_probe(self, video_path: Path) -> None:
        if self.audio_probe_worker is not None:
            self.audio_probe_worker.cancel()
        self._clear_audio_track_metadata()
        request_id = uuid.uuid4().hex
        self._audio_probe_request_id = request_id
        worker = _AudioProbeWorker(self.backend, video_path, request_id)
        worker.signals.completed.connect(self._on_audio_probe_completed)
        worker.signals.failed.connect(self._on_audio_probe_failed)
        worker.signals.cancelled.connect(self._on_audio_probe_cancelled)
        self.audio_probe_worker = worker
        self._audio_track_refresh_attempts = 0
        self.pool.start(worker)

    def _on_audio_probe_completed(self, request_id: str, metadata: Any) -> None:
        worker = self.audio_probe_worker
        if (
            request_id != self._audio_probe_request_id
            or worker is None
            or worker.request_id != request_id
        ):
            self._release_audio_probe_worker(request_id)
            self._finish_pending_close()
            return
        source = worker.video_path.resolve()
        self.audio_probe_worker = None
        self._audio_probe_request_id = None
        tracks = tuple(getattr(metadata, "audio_tracks", ()) or ())
        self._audio_track_cache[source] = tracks
        if source == self._current_media_path:
            self._set_audio_track_metadata(tracks)
        self._finish_pending_close()

    def _on_audio_probe_failed(self, request_id: str, message: str) -> None:
        if request_id != self._audio_probe_request_id:
            self._release_audio_probe_worker(request_id)
            self._finish_pending_close()
            return
        LOGGER.warning("Could not read audio track metadata: %s", message)
        self.audio_probe_worker = None
        self._audio_probe_request_id = None
        self._clear_audio_track_metadata()
        self._finish_pending_close()

    def _on_audio_probe_cancelled(self, request_id: str) -> None:
        self._release_audio_probe_worker(request_id)
        if request_id == self._audio_probe_request_id:
            self._audio_probe_request_id = None
            self._clear_audio_track_metadata()
        self._finish_pending_close()

    def _release_audio_probe_worker(self, request_id: str) -> None:
        if (
            self.audio_probe_worker is not None
            and self.audio_probe_worker.request_id == request_id
        ):
            self.audio_probe_worker = None

    def _clear_audio_track_metadata(self) -> None:
        self._audio_tracks = ()
        self._pending_audio_track_index = None
        for combo in self._audio_track_combos:
            combo.blockSignals(True)
            combo.clear()
            combo.setVisible(False)
            combo.setEnabled(False)
            combo.blockSignals(False)

    def _set_audio_track_metadata(self, tracks: tuple[Any, ...]) -> None:
        self._audio_tracks = tuple(tracks)
        self._populate_audio_track_combos()
        self._pending_audio_track_index = (
            self._initial_audio_track_index() if self._audio_tracks else None
        )
        self._refresh_player_audio_tracks()

    def _populate_audio_track_combos(self) -> None:
        multiple_tracks = len(self._audio_tracks) > 1
        for combo in self._audio_track_combos:
            combo.blockSignals(True)
            combo.clear()
            if multiple_tracks:
                for ordinal, track in enumerate(self._audio_tracks):
                    combo.addItem(self._audio_track_label(track, ordinal), int(track.index))
            combo.setVisible(multiple_tracks)
            combo.setEnabled(False)
            combo.blockSignals(False)
        if multiple_tracks:
            selected = self._initial_audio_track_index()
            for combo in self._audio_track_combos:
                combo.blockSignals(True)
                index = combo.findData(selected)
                combo.setCurrentIndex(max(0, index))
                combo.blockSignals(False)

    @staticmethod
    def _audio_track_label(track: Any, ordinal: int) -> str:
        details = [str(value) for value in (track.title, track.language, track.codec) if value]
        suffix = f" — {' / '.join(details)}" if details else ""
        default = " (container default)" if track.is_default is True else ""
        return f"Track {ordinal + 1}{suffix}{default}"

    def _initial_audio_track_index(self) -> int:
        preferred = self._saved_audio_track_index()
        by_index = {int(track.index): track for track in self._audio_tracks}
        if preferred in by_index:
            return int(preferred)
        for track in self._audio_tracks:
            if track.is_default is True:
                return int(track.index)
        return int(self._audio_tracks[0].index)

    def _saved_audio_track_index(self) -> int | None:
        settings = self.backend.get_settings()
        value = settings.preferred_audio_track_index
        return value if isinstance(value, int) and not isinstance(value, bool) else None

    def _audio_track_selected(self, combo: QComboBox) -> None:
        if len(self._audio_tracks) < 2 or not combo.isEnabled():
            return
        selected = combo.currentData()
        if not isinstance(selected, int):
            return
        try:
            self._save_audio_track_preference(selected)
        except Exception as exc:
            LOGGER.exception("Could not save preferred audio track")
            self.statusBar().showMessage(
                f"音声トラック設定を保存できません: {sanitize_text(str(exc))}", 8000
            )
            previous = self._pending_audio_track_index
            if previous is not None:
                self._set_audio_combo_selection(previous)
            return
        self._set_audio_combo_selection(selected)
        self._pending_audio_track_index = selected
        if self._activate_player_audio_track(selected):
            self._pending_audio_track_index = None

    def _save_audio_track_preference(self, index: int | None) -> None:
        self.backend.set_preferred_audio_track_index(index)

    def _set_audio_combo_selection(self, stream_index: int) -> None:
        for combo in self._audio_track_combos:
            combo.blockSignals(True)
            selected = combo.findData(stream_index)
            if selected >= 0:
                combo.setCurrentIndex(selected)
            combo.blockSignals(False)

    def _media_status_changed(self, status: QMediaPlayer.MediaStatus) -> None:
        ready_statuses = {
            QMediaPlayer.MediaStatus.LoadedMedia,
            QMediaPlayer.MediaStatus.BufferedMedia,
        }
        self._player_audio_source_ready = status in ready_statuses
        self._refresh_player_audio_tracks()

    def _player_audio_tracks_changed(self, *_args: Any) -> None:
        self._refresh_player_audio_tracks()

    def _refresh_player_audio_tracks(self) -> None:
        if not self._audio_tracks:
            return
        if not self._player_audio_source_ready:
            return
        list_tracks = getattr(self.player, "audioTracks", None)
        set_active = getattr(self.player, "setActiveAudioTrack", None)
        if not callable(list_tracks) or not callable(set_active):
            self._set_audio_controls_enabled(False)
            return
        try:
            available = list_tracks() or ()
            available_count = len(available)
        except (RuntimeError, TypeError):
            available_count = 0
        if available_count != len(self._audio_tracks):
            self._set_audio_controls_enabled(False)
            self._schedule_audio_track_refresh()
            return
        self._set_audio_controls_enabled(len(self._audio_tracks) > 1)
        if (
            self._pending_audio_track_index is not None
            and self._activate_player_audio_track(self._pending_audio_track_index)
        ):
            self._pending_audio_track_index = None

    def _set_audio_controls_enabled(self, enabled: bool) -> None:
        for combo in self._audio_track_combos:
            combo.setEnabled(enabled and combo.count() > 1)

    def _schedule_audio_track_refresh(self) -> None:
        if self._audio_track_refresh_attempts >= 20:
            return
        self._audio_track_refresh_attempts += 1
        QTimer.singleShot(100, self._refresh_player_audio_tracks)

    def _activate_player_audio_track(self, stream_index: int) -> bool:
        if not self._player_audio_source_ready:
            return False
        list_tracks = getattr(self.player, "audioTracks", None)
        set_active = getattr(self.player, "setActiveAudioTrack", None)
        if not callable(list_tracks) or not callable(set_active):
            return False
        try:
            if len(list_tracks()) != len(self._audio_tracks):
                return False
            ordinal = next(
                offset
                for offset, track in enumerate(self._audio_tracks)
                if int(track.index) == stream_index
            )
            set_active(ordinal)
        except (StopIteration, RuntimeError, TypeError, ValueError):
            return False
        return True

    def _open_settings(self) -> None:
        if (
            self.worker is not None
            or self.probe_worker is not None
            or self.audio_probe_worker is not None
        ):
            QMessageBox.information(self, "処理中", "動画確認・解析中は設定を変更できません")
            return
        dialog = SettingsDialog(self.backend, self, audio_tracks=self._audio_tracks)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            if len(self._audio_tracks) > 1:
                self._pending_audio_track_index = self._initial_audio_track_index()
                self._set_audio_combo_selection(self._pending_audio_track_index)
                self._refresh_player_audio_tracks()
            self._refresh_mode_label()
            self._load_history()

    def _refresh_mode_label(self) -> None:
        settings = self.backend.get_settings()
        ai_mode = "Mock AI" if settings.mock_ai else f"OpenAI: {settings.model_id}"
        hud_mode = "Mock HUD" if settings.hud_mode == "mock" else "実HUD"
        self.mode_label.setText(f"{ai_mode} / {hud_mode}")

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802 - Qt API
        if self._allow_close:
            self.player.stop()
            event.accept()
            return
        if (
            self.worker is not None
            or self.probe_worker is not None
            or self.audio_probe_worker is not None
        ):
            if self._close_after_worker:
                event.ignore()
                return
            answer = QMessageBox.question(
                self,
                "処理を中断しますか",
                "動画確認または解析中です。安全にキャンセルして終了しますか？",
            )
            if answer != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            if self.worker is not None:
                self.worker.cancel()
            if self.probe_worker is not None:
                self.probe_worker.cancel()
            if self.audio_probe_worker is not None:
                self.audio_probe_worker.cancel()
            self._close_after_worker = True
            self.progress_text.setText("処理を中断してから終了します…")
            event.ignore()
            return
        self.player.stop()
        event.accept()

    def _finish_pending_close(self) -> bool:
        """Close only after the background worker has stopped touching app state."""

        if not self._close_after_worker:
            return False
        if (
            self.worker is not None
            or self.probe_worker is not None
            or self.audio_probe_worker is not None
        ):
            return True
        self._close_after_worker = False
        self._allow_close = True
        self.player.stop()
        QTimer.singleShot(0, self.close)
        return True

    @staticmethod
    def _format_millis(value: int) -> str:
        seconds = max(0, value // 1000)
        return f"{seconds // 60:02d}:{seconds % 60:02d}"

    @staticmethod
    def _style_sheet() -> str:
        return """
            QMainWindow, QWidget { background: #111827; color: #e5e7eb; }
            QMenuBar, QStatusBar { background: #0b1220; color: #d1d5db; }
            QLabel#pageTitle { font-size: 25px; font-weight: 700; color: #f9fafb; }
            QLabel#muted { color: #9ca3af; }
            QLabel#modeBadge, QLabel#reviewBadge {
                color: #bfdbfe; background: #1e3a5f; border-radius: 5px; padding: 5px 9px;
            }
            QLabel#privacyNotice { color: #fde68a; background: #3a2f12; padding: 10px; }
            QLabel#improvement { color: #d1fae5; background: #14352b; padding: 8px; }
            QPushButton { background: #263449; border: 1px solid #3d4c63; padding: 7px 12px; }
            QPushButton:hover { background: #34445c; }
            QPushButton:disabled { color: #6b7280; background: #1f2937; }
            QPushButton#primaryButton {
                background: #2563eb; border-color: #3b82f6; font-weight: 700;
            }
            QLineEdit, QComboBox, QListWidget, QScrollArea {
                background: #182233; border: 1px solid #334155; padding: 5px;
            }
            QFrame#evaluationCard { background: #172033; border: 1px solid #334155; padding: 6px; }
            QProgressBar { border: 1px solid #334155; text-align: center; }
            QProgressBar::chunk { background: #2563eb; }
        """


__all__ = ["MainWindow"]

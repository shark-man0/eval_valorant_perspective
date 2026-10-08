from __future__ import annotations

from pathlib import Path
from typing import Any

from valorant_ai_coach.observability.sanitize import sanitize_text

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class SettingsDialog(QDialog):
    def __init__(
        self,
        backend: Any,
        parent: QWidget | None = None,
        *,
        audio_tracks: tuple[Any, ...] = (),
    ) -> None:
        super().__init__(parent)
        self.backend = backend
        settings = backend.get_settings()
        self._saved_audio_track_index = self._load_audio_track_preference(settings)
        self.setWindowTitle("設定")
        self.setMinimumWidth(650)

        privacy = QLabel(
            "実APIモードでは、候補ルールの判定に必要なフレーム画像・イベント・Factのみを"
            "OpenAI APIへ送信します。元動画全体は送信しません。"
        )
        privacy.setWordWrap(True)
        privacy.setObjectName("privacyNotice")

        self.api_key = QLineEdit()
        self.api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key.setPlaceholderText(
            "登録済み・変更しない場合は空欄" if backend.has_api_key() else "OS資格情報ストアへ保存"
        )
        self.model_id = QLineEdit(settings.model_id)
        self.mock_ai = QCheckBox("APIへ送信せず、正本テストデータで評価する")
        self.mock_ai.setChecked(settings.mock_ai)

        self.hud_mode = QComboBox()
        self.hud_mode.addItem("Mock Round Package", "mock")
        self.hud_mode.addItem("実HUD（校正済み設定が必要）", "real")
        index = self.hud_mode.findData(settings.hud_mode)
        self.hud_mode.setCurrentIndex(max(0, index))
        self.mock_case_id = QLineEdit(settings.mock_case_id)
        self.mock_case_id.setPlaceholderText("例: TC-029")
        self.hud_layout_path = QLineEdit(settings.hud_layout_path)
        self.hud_layout_path.setPlaceholderText("空欄なら保存先/hud_layout.json")
        self.visual_profile_path = QLineEdit(getattr(settings, "visual_profile_path", ""))
        from valorant_ai_coach.maps.registry import MapRegistry

        self.manual_map_id = QComboBox()
        self.manual_map_id.addItem("自動検出（未解決なら位置依存解析を停止）", "")
        for map_id, entry in MapRegistry().data["maps"].items():
            if entry.get("production", False):
                self.manual_map_id.addItem(map_id, map_id)
        saved_map = getattr(settings, "manual_map_id", "")
        if saved_map and self.manual_map_id.findData(saved_map) < 0:
            self.manual_map_id.addItem(saved_map, saved_map)
        self.manual_map_id.setCurrentIndex(max(0, self.manual_map_id.findData(saved_map)))
        self.map_client_build = QLineEdit(getattr(settings, "map_client_build", ""))
        self.map_client_build.setPlaceholderText("録画時のbuild（不明なら空欄）")
        self.visual_semantic_enabled = QCheckBox("候補画像を別のVision APIへ送信する（有料）")
        self.visual_semantic_enabled.setChecked(getattr(settings, "visual_semantic_enabled", False))
        self.visual_semantic_model = QLineEdit(getattr(settings, "visual_semantic_model", ""))
        self.visual_semantic_model.setPlaceholderText("画像入力・Structured Outputs対応モデル")

        self.ffmpeg_path = QLineEdit(settings.ffmpeg_path)
        self.ffprobe_path = QLineEdit(settings.ffprobe_path)
        self.data_dir = QLineEdit(settings.data_dir)
        self.delete_temp = QCheckBox()
        self.delete_temp.setChecked(settings.delete_temp_frames)
        self.debug_logging = QCheckBox()
        self.debug_logging.setChecked(settings.debug_logging)

        self.preferred_audio_track = QComboBox()
        self.preferred_audio_track.addItem("自動（コンテナ既定、なければ先頭）", None)
        for ordinal, track in enumerate(audio_tracks):
            details = [str(value) for value in (track.title, track.language, track.codec) if value]
            suffix = f" — {' / '.join(details)}" if details else ""
            default = " (container default)" if track.is_default is True else ""
            self.preferred_audio_track.addItem(
                f"Track {ordinal + 1}{suffix}{default}", int(track.index)
            )
        if (
            self._saved_audio_track_index is not None
            and self.preferred_audio_track.findData(self._saved_audio_track_index) < 0
        ):
            self.preferred_audio_track.addItem(
                f"保存済みトラック {self._saved_audio_track_index}（現在の動画では未確認）",
                self._saved_audio_track_index,
            )
        selected_audio_index = self.preferred_audio_track.findData(self._saved_audio_track_index)
        self.preferred_audio_track.setCurrentIndex(max(0, selected_audio_index))
        self._show_audio_preference = len(audio_tracks) > 1 or (
            self._saved_audio_track_index is not None
        )

        form = QFormLayout()
        form.addRow("OpenAI APIキー", self.api_key)
        form.addRow("OpenAIモデル", self.model_id)
        form.addRow("Mock AI", self.mock_ai)
        form.addRow("HUD解析", self.hud_mode)
        form.addRow("Mockケース", self.mock_case_id)
        form.addRow(
            "Visualプロファイル",
            self._file_field(self.visual_profile_path, "Visualプロファイルを選択", "JSON (*.json)"),
        )
        form.addRow("Visual Semantic", self.visual_semantic_enabled)
        form.addRow("Map選択", self.manual_map_id)
        form.addRow("Map検証用build", self.map_client_build)
        form.addRow("Visual専用モデル", self.visual_semantic_model)
        form.addRow(
            "HUDレイアウト",
            self._file_field(
                self.hud_layout_path, "HUDレイアウトを選択", "JSON (*.json);;すべて (*)"
            ),
        )
        form.addRow(
            "FFmpeg",
            self._file_field(self.ffmpeg_path, "FFmpegを選択", "実行ファイル (*.exe);;すべて (*)"),
        )
        form.addRow(
            "FFprobe",
            self._file_field(
                self.ffprobe_path, "FFprobeを選択", "実行ファイル (*.exe);;すべて (*)"
            ),
        )
        form.addRow("データ保存先", self._directory_field(self.data_dir))
        form.addRow("一時フレームを削除", self.delete_temp)
        form.addRow("デバッグログ", self.debug_logging)
        if self._show_audio_preference:
            form.addRow("再生する音声トラック", self.preferred_audio_track)

        hud_note = QLabel(
            "実HUD解析には校正済みテンプレートプロファイルが必要です。HUDレイアウトを"
            "空欄にすると、保存先/data_dir/hud_layout.json があれば使い、なければ"
            "同梱の1080p ROIを使用します。"
        )
        hud_note.setWordWrap(True)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(privacy)
        layout.addLayout(form)
        layout.addWidget(hud_note)
        layout.addWidget(buttons)

    def _file_field(self, field: QLineEdit, title: str, file_filter: str) -> QWidget:
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(field, 1)
        button = QPushButton("参照…")
        button.clicked.connect(lambda: self._browse_file(field, title, file_filter))
        layout.addWidget(button)
        return container

    def _directory_field(self, field: QLineEdit) -> QWidget:
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(field, 1)
        button = QPushButton("参照…")
        button.clicked.connect(lambda: self._browse_directory(field))
        layout.addWidget(button)
        return container

    def _browse_file(self, field: QLineEdit, title: str, file_filter: str) -> None:
        selected, _ = QFileDialog.getOpenFileName(
            self, title, field.text() or str(Path.home()), file_filter
        )
        if selected:
            field.setText(selected)

    def _browse_directory(self, field: QLineEdit) -> None:
        selected = QFileDialog.getExistingDirectory(
            self, "データ保存先を選択", field.text() or str(Path.home())
        )
        if selected:
            field.setText(selected)

    @staticmethod
    def _load_audio_track_preference(settings: Any) -> int | None:
        value = getattr(settings, "preferred_audio_track_index", None)
        return value if isinstance(value, int) and not isinstance(value, bool) else None

    def _save(self) -> None:
        values = {
            "data_dir": self.data_dir.text().strip(),
            "ffmpeg_path": self.ffmpeg_path.text().strip() or "ffmpeg",
            "ffprobe_path": self.ffprobe_path.text().strip() or "ffprobe",
            "model_id": self.model_id.text().strip(),
            "mock_ai": self.mock_ai.isChecked(),
            "hud_mode": str(self.hud_mode.currentData()),
            "hud_layout_path": self.hud_layout_path.text().strip(),
            "visual_profile_path": self.visual_profile_path.text().strip(),
            "manual_map_id": self.manual_map_id.currentData(),
            "map_client_build": self.map_client_build.text().strip(),
            "visual_semantic_enabled": self.visual_semantic_enabled.isChecked(),
            "visual_semantic_model": self.visual_semantic_model.text().strip(),
            "mock_case_id": self.mock_case_id.text().strip(),
            "delete_temp_frames": self.delete_temp.isChecked(),
            "debug_logging": self.debug_logging.isChecked(),
        }
        if self._show_audio_preference:
            values["preferred_audio_track_index"] = self.preferred_audio_track.currentData()
        if not values["data_dir"]:
            QMessageBox.warning(self, "設定を確認してください", "データ保存先が空です")
            return
        try:
            self.backend.update_settings(values, api_key=self.api_key.text().strip() or None)
        except Exception as exc:  # Keep settings failures inside the dialog.
            QMessageBox.critical(self, "設定を保存できません", sanitize_text(str(exc)))
            return
        self.accept()


__all__ = ["SettingsDialog"]

from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtGui import QCloseEvent  # noqa: E402
from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402

from valorant_ai_coach.settings import AppSettings, SettingsStore  # noqa: E402
from valorant_ai_coach.ui.backend import BackendFacade  # noqa: E402
from valorant_ai_coach.ui.contracts import VideoMetadataView  # noqa: E402
from valorant_ai_coach.ui.main_window import MainWindow, _AudioProbeWorker  # noqa: E402
from valorant_ai_coach.ui.settings_dialog import SettingsDialog  # noqa: E402
from valorant_ai_coach.video import AudioTrackMetadata  # noqa: E402


class MemoryCredentials:
    def get_password(self, _service: str, _username: str) -> str | None:
        return None

    def set_password(self, _service: str, _username: str, _password: str) -> None:
        return None


def test_main_window_starts_with_scored_results_filter(tmp_path: Path) -> None:
    app = QApplication.instance() or QApplication([])
    store = SettingsStore(tmp_path / "settings.json", credential_backend=MemoryCredentials())
    store.save(AppSettings.defaults(tmp_path))
    window = MainWindow(BackendFacade(store))

    assert window.windowTitle() == "VALORANT AI Coach"
    assert window.label_filter.currentData() == "scored"
    assert window.start_button.isEnabled() is False

    window.close()
    app.processEvents()


def test_audio_track_selector_prefers_saved_track_then_container_default(
    tmp_path: Path,
) -> None:
    app = QApplication.instance() or QApplication([])
    store = SettingsStore(tmp_path / "settings.json", credential_backend=MemoryCredentials())
    store.save(AppSettings.defaults(tmp_path))
    backend = BackendFacade(store)
    window = MainWindow(backend)
    window._audio_tracks = (
        AudioTrackMetadata(1, "aac", "jpn", "Japanese", False),
        AudioTrackMetadata(2, "aac", "eng", "English", True),
        AudioTrackMetadata(3, "aac", "fra", "French", False),
    )

    window._populate_audio_track_combos()
    assert window.home_audio_track.count() == 3
    assert window.home_audio_track.currentData() == 2
    assert window.result_audio_track.currentData() == 2
    assert window.home_audio_track.isHidden() is False

    store.update({"preferred_audio_track_index": 3})
    window._populate_audio_track_combos()
    assert window.home_audio_track.currentData() == 3

    store.update({"preferred_audio_track_index": 99})
    window._populate_audio_track_combos()
    assert window.home_audio_track.currentData() == 2

    store.update({"preferred_audio_track_index": None})
    window._audio_tracks = (
        AudioTrackMetadata(4, "aac", None, None, False),
        AudioTrackMetadata(5, "aac", None, None, None),
    )
    window._populate_audio_track_combos()
    assert window.home_audio_track.currentData() == 4

    window.close()
    app.processEvents()


def test_audio_track_choice_is_persisted_from_playback_selector(tmp_path: Path) -> None:
    app = QApplication.instance() or QApplication([])
    store = SettingsStore(tmp_path / "settings.json", credential_backend=MemoryCredentials())
    store.save(AppSettings.defaults(tmp_path))
    window = MainWindow(BackendFacade(store))
    window._audio_tracks = (
        AudioTrackMetadata(1, "aac", "jpn", "Japanese", True),
        AudioTrackMetadata(2, "aac", "eng", "English", False),
    )
    window._populate_audio_track_combos()
    window.home_audio_track.setEnabled(True)
    window.home_audio_track.setCurrentIndex(window.home_audio_track.findData(2))

    assert store.load().preferred_audio_track_index == 2

    window.close()
    app.processEvents()


def test_settings_dialog_exposes_audio_preference_for_multiple_tracks(tmp_path: Path) -> None:
    app = QApplication.instance() or QApplication([])
    store = SettingsStore(tmp_path / "settings.json", credential_backend=MemoryCredentials())
    store.save(AppSettings.defaults(tmp_path))
    store.update({"preferred_audio_track_index": 8})
    backend = BackendFacade(store)
    tracks = (
        AudioTrackMetadata(7, "aac", "jpn", "Japanese", True),
        AudioTrackMetadata(8, "aac", "eng", "English", False),
    )
    dialog = SettingsDialog(backend, audio_tracks=tracks)

    assert dialog.preferred_audio_track.count() == 3
    assert dialog.preferred_audio_track.currentData() == 8
    assert dialog._show_audio_preference is True

    dialog.close()
    app.processEvents()


def test_selection_probe_uses_audio_metadata_without_a_second_probe(tmp_path: Path) -> None:
    app = QApplication.instance() or QApplication([])
    store = SettingsStore(tmp_path / "settings.json", credential_backend=MemoryCredentials())
    store.save(AppSettings.defaults(tmp_path))
    backend = BackendFacade(store)
    window = MainWindow(backend)
    video = tmp_path / "recording.mp4"
    video.write_bytes(b"video")
    started: list[object] = []

    class FakePool:
        @staticmethod
        def start(worker: object) -> None:
            started.append(worker)

    class FakePlayer:
        def setVideoOutput(self, _output: object) -> None:
            pass

        def setSource(self, _source: object) -> None:
            pass

        def stop(self) -> None:
            pass

    window.pool = FakePool()  # type: ignore[assignment]
    window.player = FakePlayer()  # type: ignore[assignment]
    window._probe_request_id = "selection-1"
    tracks = (
        AudioTrackMetadata(1, "aac", "jpn", "Japanese", False),
        AudioTrackMetadata(2, "aac", "eng", "English", True),
    )
    metadata = VideoMetadataView(20, 1920, 1080, 60, "h264", True, 123, tracks)

    window._on_probe_completed("selection-1", str(video), metadata)

    assert started == []
    assert window.home_audio_track.count() == 2
    assert window.home_audio_track.currentData() == 2
    assert window._audio_track_cache[video.resolve()] == tracks
    window.close()
    app.processEvents()


def test_clip_audio_metadata_worker_uses_backend_facade(tmp_path: Path) -> None:
    path = tmp_path / "clip.mp4"
    path.write_bytes(b"clip")
    tracks = (AudioTrackMetadata(1, "aac", "eng", "English", True),)
    expected = VideoMetadataView(3, 1920, 1080, 60, "h264", True, 123, tracks)
    observed: list[tuple[Path, object]] = []

    class FakeBackend:
        def probe_video(self, video_path: Path, *, cancel_event: object) -> VideoMetadataView:
            observed.append((video_path, cancel_event))
            return expected

    worker = _AudioProbeWorker(FakeBackend(), path, "clip-1")
    results: list[tuple[str, object]] = []

    def collect_result(request_id: str, metadata: object) -> None:
        results.append((request_id, metadata))

    worker.signals.completed.connect(collect_result)
    worker.run()

    assert observed == [(path, worker.cancel_event)]
    assert results == [("clip-1", expected)]


def test_video_probe_is_dispatched_without_blocking_gui(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    app = QApplication.instance() or QApplication([])
    store = SettingsStore(tmp_path / "settings.json", credential_backend=MemoryCredentials())
    store.save(AppSettings.defaults(tmp_path))
    backend = BackendFacade(store)
    video = tmp_path / "selected.mp4"
    video.write_bytes(b"video")
    window = MainWindow(backend)
    queued: list[object] = []

    class FakePool:
        @staticmethod
        def start(worker: object) -> None:
            queued.append(worker)

    window.pool = FakePool()  # type: ignore[assignment]
    monkeypatch.setattr(
        "valorant_ai_coach.ui.main_window.QFileDialog.getOpenFileName",
        lambda *_args, **_kwargs: (str(video), ""),
    )

    def unexpected_probe(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("probe must not run synchronously from _select_video")

    monkeypatch.setattr(backend, "probe_video", unexpected_probe)
    window._select_video()

    assert len(queued) == 1
    assert window.probe_worker is queued[0]
    assert window.video_path is None
    assert window.select_button.isEnabled() is False
    assert window.start_button.isEnabled() is False
    assert "取得しています" in window.metadata_label.text()

    window.probe_worker.cancel()
    assert window._probe_request_id is not None
    window._on_probe_cancelled(window._probe_request_id)
    assert window.select_button.isEnabled() is True
    window.close()
    app.processEvents()


def test_analysis_failure_dialog_hides_traceback_and_private_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    app = QApplication.instance() or QApplication([])
    store = SettingsStore(tmp_path / "settings.json", credential_backend=MemoryCredentials())
    store.save(AppSettings.defaults(tmp_path))
    window = MainWindow(BackendFacade(store))
    captured: dict[str, str] = {}

    def fake_exec(dialog: QMessageBox) -> int:
        captured["text"] = dialog.text()
        captured["details"] = dialog.detailedText()
        return int(QMessageBox.StandardButton.Ok)

    monkeypatch.setattr(QMessageBox, "exec", fake_exec)
    window._on_failed(
        "failed at /home/alice/private/video.mp4 api_key=sk-supersecretvalue",
        "Traceback (most recent call last):\n  File /home/alice/project/app.py",
    )

    assert "/home/alice" not in captured["text"]
    assert "sk-supersecretvalue" not in captured["text"]
    assert captured["details"] == ""

    window.close()
    app.processEvents()


def test_close_waits_until_analysis_worker_has_stopped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    app = QApplication.instance() or QApplication([])
    store = SettingsStore(tmp_path / "settings.json", credential_backend=MemoryCredentials())
    store.save(AppSettings.defaults(tmp_path))
    window = MainWindow(BackendFacade(store))

    class FakeWorker:
        cancelled = False

        def cancel(self) -> None:
            self.cancelled = True

    worker = FakeWorker()
    window.worker = worker  # type: ignore[assignment]
    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *_args, **_kwargs: QMessageBox.StandardButton.Yes,
    )

    event = QCloseEvent()
    window.closeEvent(event)

    assert event.isAccepted() is False
    assert worker.cancelled is True
    assert window._close_after_worker is True

    window._on_cancelled()
    app.processEvents()
    assert window._allow_close is True


def test_history_exposes_resumable_job_and_forwards_identity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    app = QApplication.instance() or QApplication([])
    store = SettingsStore(tmp_path / "settings.json", credential_backend=MemoryCredentials())
    store.save(AppSettings.defaults(tmp_path))
    backend = BackendFacade(store)
    video = tmp_path / "resume.mp4"
    video.write_bytes(b"video")
    backend.services.repository.create_match("M-RESUME-UI", video, status="cancelled")
    backend.services.repository.save_job_checkpoint(
        "M-RESUME-UI",
        "cancelled",
        {
            "completed_rounds": [1],
            "source_fingerprint": "source-fingerprint",
            "config_fingerprint": "config-fingerprint",
        },
    )
    window = MainWindow(backend)
    window.history.setCurrentRow(0)
    app.processEvents()
    forwarded: list[tuple[Path, str | None, bool]] = []
    monkeypatch.setattr(
        window,
        "_launch_analysis",
        lambda path, *, match_id=None, resume=False: forwarded.append(
            (path, match_id, resume)
        ),
    )

    assert window.resume_button.isEnabled() is True
    window._resume_selected_analysis()

    assert forwarded == [(video, "M-RESUME-UI", True)]
    window.close()
    app.processEvents()


def test_history_delete_removes_analysis_but_keeps_source_video(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    app = QApplication.instance() or QApplication([])
    store = SettingsStore(tmp_path / "settings.json", credential_backend=MemoryCredentials())
    store.save(AppSettings.defaults(tmp_path))
    backend = BackendFacade(store)
    video = tmp_path / "recording.mp4"
    video.write_bytes(b"video")
    backend.services.repository.create_match("M-DELETE-UI", video, status="completed")
    window = MainWindow(backend)
    window.history.setCurrentRow(0)
    app.processEvents()
    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *_args, **_kwargs: QMessageBox.StandardButton.Yes,
    )

    assert window.delete_button.isEnabled() is True
    window._delete_selected_match()

    assert backend.services.repository.get_match("M-DELETE-UI") is None
    assert video.is_file()
    assert window.history.count() == 0
    assert window.delete_button.isEnabled() is False

    window.close()
    app.processEvents()

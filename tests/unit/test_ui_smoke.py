from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtCore import QCoreApplication, QEvent  # noqa: E402
from PySide6.QtGui import QCloseEvent  # noqa: E402
from PySide6.QtWidgets import QApplication, QLabel, QMessageBox, QWidget  # noqa: E402

from valorant_ai_coach.settings import AppSettings, SettingsStore  # noqa: E402
from valorant_ai_coach.ui.backend import BackendFacade  # noqa: E402
from valorant_ai_coach.ui.contracts import (  # noqa: E402
    EvaluationView,
    MatchResultView,
    VideoMetadataView,
)
from valorant_ai_coach.ui.main_window import MainWindow, _AudioProbeWorker  # noqa: E402
from valorant_ai_coach.ui.settings_dialog import SettingsDialog  # noqa: E402
from valorant_ai_coach.video import AudioTrackMetadata  # noqa: E402


def _destroy_widget(widget: QWidget, app: QApplication) -> None:
    """Destroy Qt-owned multimedia children while QApplication is still alive."""
    widget.close()
    widget.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    app.processEvents()


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

    _destroy_widget(window, app)


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

    _destroy_widget(window, app)


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

    _destroy_widget(window, app)


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

    _destroy_widget(dialog, app)


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
    _destroy_widget(window, app)


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
    _destroy_widget(window, app)


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
        return 0

    monkeypatch.setattr(QMessageBox, "exec", fake_exec)
    window._on_failed(
        "failed at /home/alice/private/video.mp4 api_key=sk-supersecretvalue",
        "Traceback (most recent call last):\n  File /home/alice/project/app.py",
    )

    assert "/home/alice" not in captured["text"]
    assert "sk-supersecretvalue" not in captured["text"]
    assert captured["details"] == ""

    _destroy_widget(window, app)


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
    _destroy_widget(window, app)


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

    _destroy_widget(window, app)


def _evaluation_view(
    label: str,
    evaluation_id: str,
    *,
    clip_path: str | None = None,
) -> EvaluationView:
    return EvaluationView(
        evaluation_id=evaluation_id,
        label=label,
        title=f"title-{evaluation_id}",
        rule_id="AIM-02" if label != "unscored" else "PEEK-02",
        related_rule_ids=(),
        situation="観測された場面",
        evidence=("00:30  first_shot_stationary=True（deterministic_fact）",)
        if label != "unscored"
        else (),
        missing_information=("必要な視覚情報が不足しています",)
        if label == "unscored"
        else (),
        reason="保存済み根拠に基づく評価",
        improvement="停止して初弾を撃つ" if label == "improve" else None,
        confidence=0.91 if label != "unscored" else 0.4,
        category="Aim",
        round_no=1,
        requires_round_context=False,
        decision_source="deterministic" if label != "unscored" else "hybrid",
        clip_path=clip_path,
        needs_review=False,
        unscored_reason_code="insufficient_visual_evidence"
        if label == "unscored"
        else None,
        fact_refs=("F-SAFE-1",) if label != "unscored" else (),
        time_range=(29.5, 30.5) if label != "unscored" else None,
    )


def test_real_main_window_renders_results_filters_evidence_and_page_transition(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    app = QApplication.instance() or QApplication([])
    store = SettingsStore(tmp_path / "settings.json", credential_backend=MemoryCredentials())
    store.save(AppSettings.defaults(tmp_path))
    backend = BackendFacade(store)
    clip = tmp_path / "clip.mp4"
    clip.write_bytes(b"clip")
    result = MatchResultView(
        match_id="M-UI-RESULT",
        source_video_path=str(tmp_path / "source.mp4"),
        status="completed",
        evaluations=(
            _evaluation_view("good", "g1", clip_path=str(clip)),
            _evaluation_view("improve", "i1"),
            _evaluation_view("unscored", "u1"),
        ),
        good_count=1,
        improve_count=1,
        unscored_count=1,
        map_name="Ascent",
        player_agent="Omen",
    )
    monkeypatch.setattr(backend, "get_match_result", lambda _match_id: result)

    window = MainWindow(backend)
    window._show_results("M-UI-RESULT")

    assert window.pages.currentWidget() is window.results_page
    assert "GOOD 1 / 改善 1 / UNSCORED 1" in window.result_title.text()
    assert window.label_filter.currentData() == "scored"

    cards = [
        window.cards_layout.itemAt(index).widget()
        for index in range(window.cards_layout.count() - 1)
    ]
    assert len(cards) == 2
    scored_text = "\n".join(
        label.text()
        for card in cards
        if card is not None
        for label in card.findChildren(QLabel)
    )
    assert "使用したfact: F-SAFE-1" in scored_text
    assert "該当時刻: 00:30" in scored_text
    assert any(card is not None and card.findChildren(QPushButton) for card in cards)

    window.label_filter.setCurrentIndex(window.label_filter.findData("unscored"))
    window._render_cards()
    unscored_card = window.cards_layout.itemAt(0).widget()
    assert unscored_card is not None
    unscored_text = "\n".join(label.text() for label in unscored_card.findChildren(QLabel))
    assert "UNSCORED" in unscored_text
    assert "必要な視覚情報が不足しています" in unscored_text
    assert "insufficient_visual_evidence" in unscored_text
    assert not unscored_card.findChildren(QPushButton)

    window._show_page(window.home_page)
    assert window.pages.currentWidget() is window.home_page
    _destroy_widget(window, app)


def test_play_clip_switches_source_replays_and_uses_cached_audio_tracks(
    tmp_path: Path,
) -> None:
    app = QApplication.instance() or QApplication([])
    store = SettingsStore(tmp_path / "settings.json", credential_backend=MemoryCredentials())
    store.save(AppSettings.defaults(tmp_path))
    store.update({"preferred_audio_track_index": 2})
    window = MainWindow(BackendFacade(store))
    first = tmp_path / "first.mp4"
    second = tmp_path / "second.mp4"
    first.write_bytes(b"first")
    second.write_bytes(b"second")
    tracks = (
        AudioTrackMetadata(1, "aac", "jpn", "Japanese", False),
        AudioTrackMetadata(2, "aac", "eng", "English", True),
    )
    window._audio_track_cache[first.resolve()] = tracks
    window._audio_track_cache[second.resolve()] = tracks

    class FakePlayer:
        def __init__(self) -> None:
            self.outputs: list[object] = []
            self.sources: list[object] = []
            self.positions: list[int] = []
            self.play_count = 0
            self.stop_count = 0

        def setVideoOutput(self, output: object) -> None:
            self.outputs.append(output)

        def setSource(self, source: object) -> None:
            self.sources.append(source)

        def play(self) -> None:
            self.play_count += 1

        def stop(self) -> None:
            self.stop_count += 1

        def setPosition(self, position: int) -> None:
            self.positions.append(position)

    fake = FakePlayer()
    window.player = fake  # type: ignore[assignment]

    window._play_clip(str(first))
    assert window._current_media_path == first.resolve()
    assert fake.outputs[-1] is window.result_player
    assert Path(fake.sources[-1].toLocalFile()).resolve() == first.resolve()
    assert fake.play_count == 1
    assert window.result_audio_track.count() == 2
    assert window.result_audio_track.currentData() == 2

    window._play_clip(str(second))
    assert window._current_media_path == second.resolve()
    assert Path(fake.sources[-1].toLocalFile()).resolve() == second.resolve()
    assert window._player_audio_source_ready is False

    window._replay()
    assert fake.positions[-1] == 0
    assert fake.play_count == 3

    _destroy_widget(window, app)


def test_play_clip_missing_file_is_safe_and_does_not_replace_current_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    app = QApplication.instance() or QApplication([])
    store = SettingsStore(tmp_path / "settings.json", credential_backend=MemoryCredentials())
    store.save(AppSettings.defaults(tmp_path))
    window = MainWindow(BackendFacade(store))
    current = tmp_path / "current.mp4"
    current.write_bytes(b"current")
    window._current_media_path = current.resolve()
    warnings: list[tuple[str, str]] = []

    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda _parent, title, message: warnings.append((title, message)),
    )
    window._play_clip(str(tmp_path / "missing.mp4"))

    assert window._current_media_path == current.resolve()
    assert warnings == [("クリップを再生できません", "クリップファイルが見つかりません")]
    _destroy_widget(window, app)

from __future__ import annotations

import json
from pathlib import Path
from threading import Event

import pytest

from valorant_ai_coach.bootstrap import build_services
from valorant_ai_coach.resources import executable_path, resource_path
from valorant_ai_coach.rules import MockEvaluator
from valorant_ai_coach.settings import AppSettings, SettingsStore
from valorant_ai_coach.ui.backend import BackendFacade
from valorant_ai_coach.video import AudioTrackMetadata


class MemoryCredentials:
    def __init__(self) -> None:
        self.values: dict[tuple[str, str], str] = {}

    def get_password(self, service: str, username: str) -> str | None:
        return self.values.get((service, username))

    def set_password(self, service: str, username: str, password: str) -> None:
        self.values[(service, username)] = password

    def delete_password(self, service: str, username: str) -> None:
        self.values.pop((service, username), None)


def make_store(tmp_path: Path) -> SettingsStore:
    store = SettingsStore(tmp_path / "settings.json", credential_backend=MemoryCredentials())
    store.save(AppSettings.defaults(tmp_path))
    return store


def test_composition_root_uses_canonical_rules_and_mock_boundaries(tmp_path: Path) -> None:
    store = make_store(tmp_path)

    services = build_services(store)

    assert services.settings.mock_ai is True
    assert services.pipeline.data_dir == tmp_path.resolve()
    assert len(services.rules_by_id) == 44
    assert services.role_resolver.resolve("future agent") == "unknown"
    assert services.repository.path == (tmp_path / "app.db").resolve()


def test_invalid_real_hud_path_is_rejected_and_settings_are_rolled_back(
    tmp_path: Path,
) -> None:
    store = make_store(tmp_path)
    backend = BackendFacade(store)
    before = store.load()

    with pytest.raises(RuntimeError, match="hud_layout"):
        backend.update_settings(
            {
                "hud_mode": "real",
                "hud_layout_path": str(tmp_path / "missing.json"),
            }
        )

    assert store.load() == before
    assert backend.get_settings().hud_mode == "mock"


def test_backend_maps_saved_schema_output_to_ui_views(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    backend = BackendFacade(store)
    repository = backend.services.repository
    package = json.loads(resource_path("tests/cases/TC-029/input.json").read_text(encoding="utf-8"))
    package["match_id"] = "M-UI"
    package["source_video"]["path"] = str(tmp_path / "match.mp4")
    repository.create_match(
        "M-UI", package["source_video"]["path"], {"duration_sec": 120}, "completed"
    )
    repository.save_round_package(package)
    repository.save_analysis_result(MockEvaluator().evaluate(package))

    result = backend.get_match_result("M-UI")

    assert result.map_name == "Ascent"
    assert result.player_agent == "MOCK_AGENT"
    assert result.good_count == 1
    assert result.improve_count == 1
    assert {item.rule_id for item in result.evaluations} == {"AIM-02", "DEC-01"}
    assert all(item.clip_path is None for item in result.evaluations)


def test_backend_audio_preference_does_not_rebuild_services(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    backend = BackendFacade(store)
    services = backend.services

    backend.set_preferred_audio_track_index(2)

    assert backend.services is services
    assert backend.get_settings().preferred_audio_track_index == 2


def test_bundled_ffmpeg_is_resolved_but_custom_path_is_preserved(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundled = tmp_path / "bin" / "ffmpeg.exe"
    bundled.parent.mkdir()
    bundled.write_bytes(b"exe")
    monkeypatch.setattr("valorant_ai_coach.resources.sys._MEIPASS", str(tmp_path), raising=False)

    assert executable_path("ffmpeg", "ffmpeg") == str(bundled)
    assert executable_path("D:/tools/ffmpeg.exe", "ffmpeg") == "D:/tools/ffmpeg.exe"


def test_backend_only_offers_resume_for_fingerprinted_jobs(tmp_path: Path) -> None:
    backend = BackendFacade(make_store(tmp_path))
    repository = backend.services.repository
    repository.create_match("M-RESUME-GATE", tmp_path / "match.mp4", status="cancelled")
    repository.save_job_checkpoint("M-RESUME-GATE", "cancelled", {})

    assert backend.can_resume("M-RESUME-GATE") is False

    repository.save_job_checkpoint(
        "M-RESUME-GATE",
        "cancelled",
        {"source_fingerprint": "source", "config_fingerprint": "config"},
    )
    assert backend.can_resume("M-RESUME-GATE") is True


def test_backend_forwards_video_probe_cancellation(tmp_path: Path) -> None:
    backend = BackendFacade(make_store(tmp_path))
    cancel = Event()
    observed: list[Event | None] = []
    metadata = type(
        "Metadata",
        (),
        {
            "duration_sec": 10.0,
            "width": 1920,
            "height": 1080,
            "fps": 60.0,
            "video_codec": "h264",
            "has_audio": True,
            "file_size": 123,
            "audio_tracks": (AudioTrackMetadata(1, "aac", "jpn", "Japanese", True),),
        },
    )()

    def probe(_path: Path, *, cancel_event: Event | None = None) -> object:
        observed.append(cancel_event)
        return metadata

    backend.services.video.probe = probe  # type: ignore[method-assign]
    result = backend.probe_video(tmp_path / "match.mp4", cancel_event=cancel)

    assert observed == [cancel]
    assert result.duration_sec == 10.0
    assert result.audio_tracks == (AudioTrackMetadata(1, "aac", "jpn", "Japanese", True),)

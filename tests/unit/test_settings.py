from __future__ import annotations

import json
from pathlib import Path

import pytest

from valorant_ai_coach.settings import AppSettings, SettingsStore


class MemoryCredentials:
    def __init__(self) -> None:
        self.values: dict[tuple[str, str], str] = {}
        self.fail_write = False

    def get_password(self, service: str, username: str) -> str | None:
        return self.values.get((service, username))

    def set_password(self, service: str, username: str, password: str) -> None:
        if self.fail_write:
            raise RuntimeError("keyring unavailable")
        self.values[(service, username)] = password

    def delete_password(self, service: str, username: str) -> None:
        self.values.pop((service, username), None)


def test_defaults_and_settings_round_trip(tmp_path: Path) -> None:
    store = SettingsStore(tmp_path / "settings.json", credential_backend=MemoryCredentials())
    defaults = store.load()
    assert defaults.data_dir == tmp_path
    assert defaults.model_id == "gpt-5.6-terra"
    updated = store.update({"model_id": "custom-model", "ffmpeg_path": "C:/tools/ffmpeg.exe"})
    loaded = store.load()
    assert updated.model_id == "custom-model"
    assert loaded.ffmpeg_path == "C:/tools/ffmpeg.exe"
    assert loaded.data_dir == tmp_path
    assert loaded.preferred_audio_track_index is None
    updated = store.update({"preferred_audio_track_index": 2})
    assert updated.preferred_audio_track_index == 2
    assert store.load().preferred_audio_track_index == 2


@pytest.mark.parametrize("invalid", [-1, True, 1.5, "2"])
def test_preferred_audio_track_index_requires_nonnegative_integer_or_none(
    tmp_path: Path, invalid: object
) -> None:
    store = SettingsStore(tmp_path / "settings.json", credential_backend=MemoryCredentials())
    with pytest.raises(ValueError, match="preferred_audio_track_index"):
        store.update({"preferred_audio_track_index": invalid})


def test_invalid_persisted_audio_track_preference_is_ignored(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    path.write_text('{"preferred_audio_track_index": -1}', encoding="utf-8")
    settings = SettingsStore(path, credential_backend=MemoryCredentials()).load()
    assert settings.preferred_audio_track_index is None


def test_keyring_is_preferred_and_secret_never_enters_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    credentials = MemoryCredentials()
    store = SettingsStore(tmp_path / "settings.json", credential_backend=credentials)
    store.save(AppSettings.defaults(tmp_path))
    monkeypatch.setenv("OPENAI_API_KEY", "environment-key")

    store.update({"mock_ai": False}, api_key="  keyring-secret  ")

    assert store.get_api_key() == "keyring-secret"
    serialized = json.loads((tmp_path / "settings.json").read_text(encoding="utf-8"))
    assert "api_key" not in serialized
    assert "keyring-secret" not in json.dumps(serialized)


def test_real_api_mode_without_key_is_rejected_without_partial_save(tmp_path: Path) -> None:
    credentials = MemoryCredentials()
    store = SettingsStore(tmp_path / "settings.json", credential_backend=credentials)
    old = AppSettings.defaults(tmp_path)
    store.save(old)

    with pytest.raises(RuntimeError, match="APIキー"):
        store.update({"mock_ai": False})

    assert store.load() == old


def test_keyring_write_failure_keeps_existing_settings(tmp_path: Path) -> None:
    credentials = MemoryCredentials()
    store = SettingsStore(tmp_path / "settings.json", credential_backend=credentials)
    old = AppSettings.defaults(tmp_path)
    store.save(old)
    credentials.fail_write = True

    with pytest.raises(RuntimeError, match="keyring unavailable"):
        store.update({"mock_ai": False}, api_key="secret")

    assert store.load() == old


def test_settings_write_failure_rolls_back_new_credential(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    credentials = MemoryCredentials()
    store = SettingsStore(tmp_path / "settings.json", credential_backend=credentials)
    old = AppSettings.defaults(tmp_path)
    store.save(old)

    def fail_save(_settings: AppSettings) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(store, "save", fail_save)
    with pytest.raises(OSError, match="disk full"):
        store.update({"mock_ai": False}, api_key="new-secret")

    assert store.get_stored_api_key() is None
    assert json.loads((tmp_path / "settings.json").read_text(encoding="utf-8"))["mock_ai"] is True

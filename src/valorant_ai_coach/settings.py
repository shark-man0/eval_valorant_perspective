from __future__ import annotations

import json
import os
import tempfile
from contextlib import suppress
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import Any, Protocol


class CredentialBackend(Protocol):
    def get_password(self, service: str, username: str) -> str | None: ...
    def set_password(self, service: str, username: str, password: str) -> None: ...


def default_data_dir() -> Path:
    """Return a per-user, writable data directory on Windows and Unix."""
    if os.name == "nt":
        root = os.environ.get("LOCALAPPDATA")
        base = Path(root) if root else Path.home() / "AppData" / "Local"
        return base / "ValorantAICoach"
    root = os.environ.get("XDG_DATA_HOME")
    base = Path(root) if root else Path.home() / ".local" / "share"
    return base / "valorant-ai-coach"


@dataclass(frozen=True, slots=True)
class AppSettings:
    data_dir: Path = field(default_factory=default_data_dir)
    ffmpeg_path: str = "ffmpeg"
    ffprobe_path: str = "ffprobe"
    model_id: str = "gpt-5.6-terra"
    escalation_model_id: str = "gpt-5.6-terra"
    enable_escalation: bool = False
    mock_ai: bool = True
    hud_mode: str = "mock"
    hud_layout_path: str = ""
    scene_reference_profile_path: str = ""
    visual_profile_path: str = ""
    manual_map_id: str = ""
    map_client_build: str = ""
    visual_semantic_enabled: bool = False
    visual_semantic_model: str = ""
    mock_case_id: str = "TC-029"
    delete_temp_frames: bool = True
    debug_logging: bool = False
    preferred_audio_track_index: int | None = None
    round_boundary_mode: str = "strict"
    unedited_input_contract_path: str = ""
    native_png_budget_mb: int = 8192

    def __post_init__(self) -> None:
        if self.round_boundary_mode not in {"strict", "practical"}:
            raise ValueError("round_boundary_mode must be strict or practical")
        if (type(self.native_png_budget_mb) is not int
                or not 64 <= self.native_png_budget_mb <= 65536):
            raise ValueError("native_png_budget_mb must be an integer between 64 and 65536")
        if not isinstance(self.unedited_input_contract_path, str):
            raise ValueError("unedited_input_contract_path must be a path string")
        if self.round_boundary_mode == "practical" and (
            self.hud_mode != "real" or not self.unedited_input_contract_path.strip()
        ):
            raise ValueError("Practical Mode requires real HUD and an explicit input contract")

    @classmethod
    def defaults(cls, data_dir: Path | None = None) -> AppSettings:
        return cls(data_dir=Path(data_dir) if data_dir else default_data_dir())


class SettingsStore:
    """JSON configuration plus keyring-backed credentials.

    API keys are never included in the JSON settings file. The keyring is read
    before the environment fallback so a user's explicit saved credential wins.
    """

    service_name = "ValorantAICoach"
    key_username = "openai_api_key"

    def __init__(
        self,
        path: Path | None = None,
        *,
        credential_backend: CredentialBackend | None = None,
    ) -> None:
        self.path = Path(path) if path else default_data_dir() / "settings.json"
        self._credential_backend = credential_backend

    def _credentials(self) -> CredentialBackend | None:
        if self._credential_backend is not None:
            return self._credential_backend
        try:
            import keyring
        except ImportError:
            return None
        return keyring

    def load(self) -> AppSettings:
        if not self.path.exists():
            return AppSettings.defaults(self.path.parent)
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"設定ファイルを読み込めません: {self.path}") from exc
        if not isinstance(raw, dict):
            raise ValueError("設定ファイルのトップレベルはJSON objectである必要があります")

        defaults = AppSettings.defaults(self.path.parent)
        allowed = set(AppSettings.__dataclass_fields__)
        values = {key: value for key, value in raw.items() if key in allowed}
        if "data_dir" in values:
            values["data_dir"] = Path(values["data_dir"])
        preferred_track = values.get("preferred_audio_track_index")
        if preferred_track is not None and (
            isinstance(preferred_track, bool)
            or not isinstance(preferred_track, int)
            or preferred_track < 0
        ):
            values["preferred_audio_track_index"] = None
        return replace(defaults, **values)

    def save(self, settings: AppSettings) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = asdict(settings)
        payload["data_dir"] = str(settings.data_dir)
        encoded = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
        fd, temporary = tempfile.mkstemp(
            prefix=f".{self.path.name}.", suffix=".tmp", dir=self.path.parent
        )
        tmp_path = Path(temporary)
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
                stream.write(encoded)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(tmp_path, self.path)
            if os.name != "nt":
                with suppress(OSError):
                    self.path.chmod(0o600)
        except Exception:
            tmp_path.unlink(missing_ok=True)
            raise

    def update(self, values: dict[str, Any], api_key: str | None = None) -> AppSettings:
        current = self.load()
        changes = dict(values)
        if "data_dir" in changes:
            changes["data_dir"] = Path(changes["data_dir"])
        unknown = changes.keys() - set(AppSettings.__dataclass_fields__)
        if unknown:
            raise ValueError(f"不明な設定項目: {', '.join(sorted(unknown))}")
        preferred_track = changes.get("preferred_audio_track_index")
        if (
            "preferred_audio_track_index" in changes
            and preferred_track is not None
            and (
                isinstance(preferred_track, bool)
                or not isinstance(preferred_track, int)
                or preferred_track < 0
            )
        ):
            raise ValueError("preferred_audio_track_indexは0以上の整数またはNoneで指定してください")

        updated = replace(current, **changes)
        if not updated.model_id.strip():
            raise ValueError("OpenAIモデルIDが空です")
        if updated.hud_mode not in {"mock", "real"}:
            raise ValueError("hud_modeはmockまたはrealで指定してください")
        if not updated.mock_case_id.startswith("TC-"):
            raise ValueError("mock_case_idはTC-から始まるケースIDで指定してください")

        normalized_key = api_key.strip() if api_key is not None else ""
        if not updated.mock_ai and not (normalized_key or self.get_api_key()):
            raise RuntimeError("実APIモードにはOpenAI APIキーが必要です")
        backend = self._credentials()
        previous_stored = None
        credential_changed = False
        if normalized_key:
            if backend is None:
                raise RuntimeError("APIキーの安全な保存にはkeyringが必要です")
            try:
                previous_stored = backend.get_password(self.service_name, self.key_username)
            except Exception:
                previous_stored = None
            try:
                self.set_api_key(normalized_key)
                credential_changed = True
            except Exception:
                try:
                    if previous_stored:
                        backend.set_password(self.service_name, self.key_username, previous_stored)
                    else:
                        delete_password = getattr(backend, "delete_password", None)
                        if callable(delete_password):
                            delete_password(self.service_name, self.key_username)
                except Exception:
                    pass
                raise
        try:
            self.save(updated)
        except Exception:
            if credential_changed and backend is not None:
                try:
                    if previous_stored:
                        backend.set_password(self.service_name, self.key_username, previous_stored)
                    else:
                        delete_password = getattr(backend, "delete_password", None)
                        if callable(delete_password):
                            delete_password(self.service_name, self.key_username)
                except Exception:
                    # Preserve the original settings error; credential rollback is best effort.
                    pass
            raise
        return updated

    def set_api_key(self, api_key: str) -> None:
        value = api_key.strip()
        if not value:
            raise ValueError("APIキーが空です")
        backend = self._credentials()
        if backend is None:
            raise RuntimeError("APIキーの安全な保存にはkeyringが必要です")
        backend.set_password(self.service_name, self.key_username, value)
        stored = backend.get_password(self.service_name, self.key_username)
        if stored != value:
            raise RuntimeError("APIキーを資格情報ストアから確認できません")

    def get_api_key(self) -> str | None:
        backend = self._credentials()
        if backend is not None:
            try:
                saved = backend.get_password(self.service_name, self.key_username)
            except Exception:
                saved = None
            if saved:
                return saved
        env_value = os.environ.get("OPENAI_API_KEY")
        return env_value or None

    def get_stored_api_key(self) -> str | None:
        """Return only the OS credential-store value, excluding environment fallback."""
        backend = self._credentials()
        if backend is None:
            return None
        try:
            return backend.get_password(self.service_name, self.key_username) or None
        except Exception:
            return None

    def delete_api_key(self) -> None:
        backend = self._credentials()
        if backend is None:
            return
        delete_password = getattr(backend, "delete_password", None)
        if callable(delete_password):
            try:
                delete_password(self.service_name, self.key_username)
            except Exception:
                return

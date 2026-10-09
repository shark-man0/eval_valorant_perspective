"""Versioned, API-key-free settings profiles.

Profiles intentionally exclude the data directory: changing it silently can hide
existing analysis history. Credential Manager is never read or exported here.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from valorant_ai_coach.non_video.features import _atomic_write
from valorant_ai_coach.settings import AppSettings, SettingsStore

PROFILE_FIELDS = frozenset(AppSettings.__dataclass_fields__) - {"data_dir"}
PROFILE_VERSION = 1


class ProfileStore:
    def __init__(self, settings: SettingsStore):
        self.settings = settings
        self.path = settings.path.parent / "settings_profiles.json"

    def _load(self) -> dict[str, dict[str, Any]]:
        if not self.path.is_file():
            return {}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (ValueError, OSError) as exc:
            raise ValueError("プロファイルファイルを読み込めません") from exc
        if not isinstance(data, dict) or data.get("version") != PROFILE_VERSION:
            raise ValueError("未対応のプロファイル形式です")
        profiles = data.get("profiles")
        if not isinstance(profiles, dict):
            raise ValueError("profilesの形式が不正です")
        return {self._name(k): self._validate(v) for k, v in profiles.items()}

    @staticmethod
    def _name(name: str) -> str:
        if not isinstance(name, str) or not 1 <= len(name.strip()) <= 60:
            raise ValueError("プロファイル名は1〜60文字で指定してください")
        if name != name.strip() or "/" in name or "\\" in name:
            raise ValueError("プロファイル名が不正です")
        return name

    @staticmethod
    def _validate(data: Any) -> dict[str, Any]:
        if not isinstance(data, dict):
            raise ValueError("プロファイル設定はJSON objectで指定してください")
        if set(data) - PROFILE_FIELDS:
            raise ValueError("未知または禁止された設定項目があります")
        defaults = asdict(AppSettings.defaults())
        for key, value in data.items():
            if value is None:
                if defaults[key] is not None:
                    raise ValueError(f"{key}にnullは使えません")
            elif key == "preferred_audio_track_index":
                if type(value) is not int or value < 0:
                    raise ValueError("preferred_audio_track_indexは0以上の整数またはnullです")
            elif type(value) is not type(defaults[key]):
                raise ValueError(f"{key}の型が正しくありません")
        if data.get("hud_mode", "mock") not in ("mock", "real"):
            raise ValueError("hud_modeが不正です")
        if data.get("model_id", "model").strip() == "":
            raise ValueError("model_idが不正です")
        for key in data:
            if "api_key" in key.lower() or "secret" in key.lower():
                raise ValueError("資格情報はプロファイルに含められません")
        return dict(data)

    def list_names(self) -> list[str]:
        return sorted(self._load())

    def _write(self, values: dict[str, dict[str, Any]]) -> None:
        _atomic_write(self.path, json.dumps(
            {"version": PROFILE_VERSION, "profiles": values},
            ensure_ascii=False, indent=2
        ) + "\n")

    def create(self, name: str) -> None:
        name = self._name(name)
        profiles = self._load()
        if name in profiles:
            raise ValueError("同名のプロファイルが存在します")
        source = asdict(self.settings.load())
        profiles[name] = self._validate({k: v for k, v in source.items() if k in PROFILE_FIELDS})
        self._write(profiles)

    def rename(self, old: str, new: str) -> None:
        profiles = self._load()
        new = self._name(new)
        if old not in profiles:
            raise KeyError("プロファイルが存在しません")
        if new in profiles:
            raise ValueError("同名のプロファイルが存在します")
        profiles[new] = profiles.pop(old)
        self._write(profiles)

    def delete(self, name: str) -> None:
        profiles = self._load()
        if name not in profiles:
            raise KeyError("プロファイルが存在しません")
        del profiles[name]
        self._write(profiles)

    def activate(self, name: str, backend: Any) -> None:
        profiles = self._load()
        if name not in profiles:
            raise KeyError("プロファイルが存在しません")
        # BackendFacade performs validation, safe service rebuild and rollback.
        backend.update_settings(profiles[name])

    def reset_settings(self, backend: Any) -> None:
        defaults = asdict(AppSettings.defaults(self.settings.load().data_dir))
        backend.update_settings({k: v for k, v in defaults.items() if k in PROFILE_FIELDS})

    def export_file(self, name: str, path: Path) -> None:
        profiles = self._load()
        if name not in profiles:
            raise KeyError("プロファイルが存在しません")
        _atomic_write(path, json.dumps(
            {"version": PROFILE_VERSION, "settings": profiles[name]},
            ensure_ascii=False, indent=2
        ) + "\n")

    def import_file(self, path: Path, name: str) -> None:
        name = self._name(name)
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, OSError) as exc:
            raise ValueError("インポートファイルを読み込めません") from exc
        if not isinstance(raw, dict) or raw.get("version") != PROFILE_VERSION:
            raise ValueError("未対応のプロファイル形式です")
        new = self._validate(raw.get("settings"))
        profiles = self._load()
        if name in profiles:
            raise ValueError("同名のプロファイルが存在します")
        profiles[name] = new
        self._write(profiles)

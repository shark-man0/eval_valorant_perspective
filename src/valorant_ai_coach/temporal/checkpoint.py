"""Private, exact-binding native observation checkpoints for development runs."""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from pathlib import Path
from typing import Any

from .evidence import digest


class ObservationCheckpoint:
    def __init__(self, directory: Path, binding: dict[str, Any]):
        self.directory = directory.expanduser().resolve()
        if self.directory.exists() and not self.directory.is_dir():
            raise ValueError("Checkpoint path must be a directory")
        if any((p / ".git").exists() for p in (self.directory, *self.directory.parents)):
            raise ValueError("Private checkpoint directory outside Git required")
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.manifest_path = self.directory / "manifest_PRIVATE.json"
        if self.manifest_path.exists():
            manifest = self._read(self.manifest_path)
            if (
                manifest.get("schema") != "native_observation_checkpoint_v1"
                or manifest.get("binding") != binding
            ):
                raise ValueError("Checkpoint binding mismatch")
            if not isinstance(manifest.get("epoch"), str) or len(manifest["epoch"]) != 32:
                raise ValueError("Invalid checkpoint epoch")
            if not isinstance(manifest.get("passes"), dict):
                raise ValueError("Invalid checkpoint manifest")
        else:
            if any(self.directory.iterdir()):
                raise ValueError("Unmanifested checkpoint data")
            manifest = {
                "schema": "native_observation_checkpoint_v1",
                "binding": binding,
                "epoch": uuid.uuid4().hex,
                "passes": {},
            }
            self._atomic_json(self.manifest_path, manifest)
        self.manifest = manifest

    @property
    def epoch(self) -> str:
        value = self.manifest["epoch"]
        assert isinstance(value, str)
        return value

    @staticmethod
    def _read(path: Path) -> dict[str, Any]:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise ValueError("Invalid or truncated checkpoint") from exc
        if not isinstance(value, dict):
            raise ValueError("Invalid checkpoint object")
        return value

    @staticmethod
    def _atomic_json(path: Path, value: dict[str, Any]) -> None:
        temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
        payload = json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        try:
            with temporary.open("xb") as handle:
                os.chmod(temporary, 0o600)
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)

    def load(self, name: str, request: dict[str, Any]) -> tuple[list[dict[str, Any]], bool] | None:
        entry = self.manifest["passes"].get(name)
        if entry is None:
            return None
        if entry.get("request") != request or entry.get("file") != f"{name}_PRIVATE.json":
            raise ValueError("Checkpoint pass request mismatch")
        path = self.directory / entry["file"]
        try:
            payload = path.read_bytes()
        except OSError as exc:
            raise ValueError("Missing checkpoint pass") from exc
        if hashlib.sha256(payload).hexdigest() != entry.get("sha256"):
            raise ValueError("Checkpoint pass checksum mismatch")
        value = self._read(path)
        if value.get("request") != request or value.get("epoch") != self.epoch:
            raise ValueError("Checkpoint pass identity mismatch")
        rows = value.get("records")
        if not isinstance(rows, list) or not rows:
            raise ValueError("Empty checkpoint pass")
        if digest(rows) != value.get("records_digest"):
            raise ValueError("Checkpoint rows changed")
        if type(value.get("complete")) is not bool:
            raise ValueError("Checkpoint completion flag missing")
        return rows, value["complete"]

    def save(
        self, name: str, request: dict[str, Any], rows: list[dict[str, Any]], *, complete: bool
    ) -> None:
        if not rows:
            raise ValueError("Checkpoint pass must be nonempty")
        filename = f"{name}_PRIVATE.json"
        path = self.directory / filename
        if path.exists() and name not in self.manifest["passes"]:
            raise ValueError("Unmanifested checkpoint pass")
        self._atomic_json(
            path,
            {
                "request": request,
                "epoch": self.epoch,
                "records": rows,
                "records_digest": digest(rows),
                "complete": complete,
            },
        )
        updated = {
            **self.manifest,
            "passes": {
                **self.manifest["passes"],
                name: {
                    "file": filename,
                    "request": request,
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                },
            },
        }
        self._atomic_json(self.manifest_path, updated)
        self.manifest = updated

    def size_bytes(self) -> int:
        return sum(p.stat().st_size for p in self.directory.iterdir() if p.is_file())

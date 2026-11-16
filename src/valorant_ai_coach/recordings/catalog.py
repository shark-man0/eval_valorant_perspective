"""One authoritative private catalog for recordings and everything derived from them (#62).

Why this exists
---------------
Recordings were registered by three separate mechanisms (the nine-file private intake,
the staged six-source reservation and the second-recording activation), each with its
own JSON and its own idea of a split. Nothing tied a model or a label back to the
recordings it came from, so "was this ever trained on a hold-out match?" could not be
answered by a program. This module provides that single place.

Contract
--------
* **Append-only journal.** Every change is one JSON line in ``journal.jsonl`` whose
  ``prev`` field holds the SHA-256 of the previous line. The current state is *derived*
  by replaying the journal; ``catalog.json`` is only a materialised view that ``verify``
  re-derives and compares. Editing or deleting a line breaks the chain.
* **Write-once split.** DEVELOPMENT / QUALIFICATION / FINAL_HOLDOUT is fixed when a
  recording is registered. There is no operation that changes it. A physical match has
  exactly one split, whatever number of files it has.
* **Content-blind allocation.** Unless the operator states the split explicitly, it is
  derived from ``sha256(seed + physical_match_id)`` with the ratios fixed when the
  catalog was created, before any metadata or pixel is looked at.
* **Exposure is history, not a split.** Viewing, annotating, tuning or an explicit user
  decision to use a hold-out match for development is journaled as an exposure event.
  A QUALIFICATION / FINAL_HOLDOUT recording with any exposure is permanently
  ``blind = False``; it keeps its split label so that the history stays visible.
* **Lineage.** Frames, features, labels, analysis results and models are registered as
  artifacts with their parents. ``guard`` refuses any training/tuning use whose
  ancestry reaches a non-authorised QUALIFICATION / FINAL_HOLDOUT recording, and any
  evaluation of hold-out material that has not been explicitly opened.
* **Private by construction.** The catalog must live outside a Git checkout. Only
  ``public_summary`` (counts) may leave it; ``leak_check`` scans files headed for Git
  for source hashes, recording ids and private paths.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from collections import Counter
from collections.abc import Iterable, Iterator, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

CATALOG_VERSION = "recording_catalog.v1"
SPLITS: tuple[str, ...] = ("DEVELOPMENT", "QUALIFICATION", "FINAL_HOLDOUT")
PROTECTED_SPLITS: frozenset[str] = frozenset({"QUALIFICATION", "FINAL_HOLDOUT"})
LEGACY_SPLIT_NAMES: Mapping[str, str] = {
    "DEVELOPMENT": "DEVELOPMENT",
    "QUALIFICATION": "QUALIFICATION",
    "QUALIFICATION_CANDIDATE": "QUALIFICATION",
    "FINAL_HOLDOUT": "FINAL_HOLDOUT",
    "FINAL_HOLDOUT_CANDIDATE": "FINAL_HOLDOUT",
}
EXPOSURE_KINDS: tuple[str, ...] = (
    "development_use",
    "source_viewed",
    "annotation",
    "prediction_opened",
    "tuning",
    "user_authorized_development_use",
    "qualification_opened",
    "final_evaluation_opened",
    "unknown_prior_exposure",
)
# Exposures that authorise development use of a protected recording.
DEVELOPMENT_AUTHORISING: frozenset[str] = frozenset({"user_authorized_development_use"})
ARTIFACT_KINDS: tuple[str, ...] = (
    "derived_video",
    "frames",
    "features",
    "labels",
    "timeline",
    "analysis_result",
    "model",
    "report",
)
# Kinds that are always cut from one physical match. They inherit its id and may never
# mix two matches (a crop archive spanning two matches would leak a split boundary).
SINGLE_MATCH_KINDS: frozenset[str] = frozenset(
    {"derived_video", "frames", "timeline", "analysis_result"}
)
PURPOSES: tuple[str, ...] = (
    "training",
    "tuning",
    "development_analysis",
    "qualification",
    "final_evaluation",
)
DEFAULT_RATIOS: Mapping[str, float] = {
    "DEVELOPMENT": 0.6,
    "QUALIFICATION": 0.2,
    "FINAL_HOLDOUT": 0.2,
}
VIDEO_SUFFIXES: frozenset[str] = frozenset({".mp4", ".mkv", ".mov", ".avi", ".webm"})
_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,95}$")
_SHA = re.compile(r"^[0-9a-f]{64}$")
_CHUNK = 8 * 1024 * 1024


class CatalogError(ValueError):
    """The catalog refused an operation; nothing was written."""


class SplitImmutableError(CatalogError):
    """An operation would move a recording or a physical match to another split."""


class LeakageError(CatalogError):
    """A use would let protected material reach training, tuning or a blind evaluation."""


class CatalogIntegrityError(CatalogError):
    """The journal or the materialised view does not match its own history."""


def utc_now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(_CHUNK), b""):
            digest.update(block)
    return digest.hexdigest()


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _line_hash(line: str) -> str:
    return hashlib.sha256(line.encode("utf-8")).hexdigest()


def _safe_id(value: str, what: str) -> str:
    if not isinstance(value, str) or not _SAFE_ID.match(value):
        raise CatalogError(
            f"{what}は英数字・ハイフン・アンダースコア（96文字以内）で指定してください"
        )
    return value


def _require_sha(value: str) -> str:
    if not isinstance(value, str) or not _SHA.match(value):
        raise CatalogError("SHA-256（小文字16進64桁）が必要です")
    return value


def hash_bucket(seed: str, physical_match_id: str) -> float:
    value = hashlib.sha256(f"{seed}:{physical_match_id}".encode("utf-8")).digest()  # noqa: UP012
    return int.from_bytes(value[:8], "big") / 2**64


def allocate_split(seed: str, ratios: Mapping[str, float], physical_match_id: str) -> str:
    bucket = hash_bucket(seed, physical_match_id)
    edge = 0.0
    for split in SPLITS:
        edge += float(ratios[split])
        if bucket < edge:
            return split
    return SPLITS[-1]


# --------------------------------------------------------------------- state


@dataclass(slots=True)
class Recording:
    recording_id: str
    source_sha256: str
    size_bytes: int
    physical_match_id: str
    split: str
    allocation: str
    registered_at: str
    origin: str
    status: str = "registered"
    metadata: dict[str, Any] = field(default_factory=dict)
    locations: dict[str, dict[str, Any]] = field(default_factory=dict)
    exposures: list[dict[str, Any]] = field(default_factory=list)
    legacy: dict[str, Any] = field(default_factory=dict)
    legacy_anchors: list[str] = field(default_factory=list)

    @property
    def blind(self) -> bool:
        """A protected recording nobody has looked at, tuned on or opened."""
        return self.split in PROTECTED_SPLITS and not self.exposures

    @property
    def independent_until_opened(self) -> bool:
        """No exposure other than evaluation openings: usable as independent hold-out."""
        return self.split in PROTECTED_SPLITS and all(
            item["kind"] in {"qualification_opened", "final_evaluation_opened"}
            for item in self.exposures
        )

    @property
    def development_authorised(self) -> bool:
        return self.split == "DEVELOPMENT" or any(
            item["kind"] in DEVELOPMENT_AUTHORISING for item in self.exposures
        )

    def opened_for(self, purpose: str) -> bool:
        wanted = {
            "qualification": "qualification_opened",
            "final_evaluation": "final_evaluation_opened",
        }.get(purpose)
        return wanted is not None and any(item["kind"] == wanted for item in self.exposures)

    def to_dict(self) -> dict[str, Any]:
        return {
            "recording_id": self.recording_id,
            "source_sha256": self.source_sha256,
            "size_bytes": self.size_bytes,
            "physical_match_id": self.physical_match_id,
            "split": self.split,
            "allocation": self.allocation,
            "registered_at": self.registered_at,
            "origin": self.origin,
            "status": self.status,
            "blind": self.blind,
            "development_authorised": self.development_authorised,
            "independent_until_opened": self.independent_until_opened,
            "metadata": dict(self.metadata),
            "locations": {key: dict(value) for key, value in sorted(self.locations.items())},
            "exposures": [dict(item) for item in self.exposures],
            "legacy": dict(self.legacy),
            "legacy_anchors": list(self.legacy_anchors),
        }


@dataclass(slots=True)
class Artifact:
    artifact_id: str
    kind: str
    sha256: str
    parents: tuple[str, ...]
    producer: dict[str, Any]
    registered_at: str
    path: str | None = None
    physical_match_ids: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_id": self.artifact_id,
            "physical_match_ids": list(self.physical_match_ids),
            "kind": self.kind,
            "sha256": self.sha256,
            "parents": list(self.parents),
            "producer": dict(self.producer),
            "registered_at": self.registered_at,
            "path": self.path,
        }


@dataclass(slots=True)
class CatalogState:
    config: dict[str, Any] = field(default_factory=dict)
    recordings: dict[str, Recording] = field(default_factory=dict)
    artifacts: dict[str, Artifact] = field(default_factory=dict)
    events: int = 0
    head: str | None = None

    def physical_matches(self, nodes: Iterable[str]) -> tuple[str, ...]:
        return tuple(sorted({
            self.recordings[rid].physical_match_id
            for node in nodes for rid in self.ancestry(node)
        }))

    # -- lookups -------------------------------------------------------------------

    def by_sha(self, sha: str) -> Recording | None:
        return next((r for r in self.recordings.values() if r.source_sha256 == sha), None)

    def split_of_physical(self, physical_match_id: str) -> str | None:
        return next(
            (r.split for r in self.recordings.values()
             if r.physical_match_id == physical_match_id),
            None,
        )

    def ancestry(self, node: str) -> set[str]:
        """All recording ids an artifact (or recording) descends from."""
        seen: set[str] = set()
        stack = [node]
        recordings: set[str] = set()
        while stack:
            current = stack.pop()
            if current in seen:
                continue
            seen.add(current)
            if current in self.recordings:
                recordings.add(current)
            elif current in self.artifacts:
                stack.extend(self.artifacts[current].parents)
            else:
                raise CatalogError(f"未登録の参照です: {current}")
        return recordings

    def descendants(self, recording_id: str) -> list[str]:
        result: list[str] = []
        frontier = {recording_id}
        changed = True
        while changed:
            changed = False
            for artifact in self.artifacts.values():
                if artifact.artifact_id not in result and frontier & set(artifact.parents):
                    result.append(artifact.artifact_id)
                    frontier.add(artifact.artifact_id)
                    changed = True
        return sorted(result)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": CATALOG_VERSION,
            "config": dict(self.config),
            "events": self.events,
            "journal_head_sha256": self.head,
            "recordings": [r.to_dict() for _, r in sorted(self.recordings.items())],
            "artifacts": [a.to_dict() for _, a in sorted(self.artifacts.items())],
        }


def _apply(state: CatalogState, event: Mapping[str, Any]) -> None:
    """Replay one journal event. Every invariant is re-checked on replay."""
    kind = event["type"]
    data = event["data"]
    if kind == "init":
        if state.config:
            raise CatalogIntegrityError("initイベントが重複しています")
        state.config = dict(data)
        return
    if not state.config:
        raise CatalogIntegrityError("initより前にイベントがあります")
    if kind == "register":
        recording = Recording(**data)
        if recording.split not in SPLITS:
            raise CatalogIntegrityError("未知のsplitです")
        if recording.recording_id in state.recordings:
            raise CatalogIntegrityError("recording_idが重複しています")
        if state.by_sha(recording.source_sha256) is not None:
            raise CatalogIntegrityError("同じSHA-256の録画が重複しています")
        existing = state.split_of_physical(recording.physical_match_id)
        if existing is not None and existing != recording.split:
            raise CatalogIntegrityError("同じ物理試合が複数のsplitにあります")
        state.recordings[recording.recording_id] = recording
    elif kind == "location":
        state.recordings[data["recording_id"]].locations[data["role"]] = {
            "path": data["path"],
            "size_bytes": data["size_bytes"],
            "mtime_ns": data["mtime_ns"],
            "verified_at": event["at"],
        }
    elif kind == "metadata":
        state.recordings[data["recording_id"]].metadata = dict(data["metadata"])
    elif kind == "anchor":
        anchors = state.recordings[data["recording_id"]].legacy_anchors
        if data["sha256"] not in anchors:
            anchors.append(data["sha256"])
    elif kind == "status":
        state.recordings[data["recording_id"]].status = data["status"]
    elif kind == "exposure":
        state.recordings[data["recording_id"]].exposures.append(
            {"kind": data["kind"], "note": data.get("note", ""), "at": event["at"]}
        )
    elif kind == "artifact":
        artifact = Artifact(**{
            **data,
            "parents": tuple(data["parents"]),
            "physical_match_ids": tuple(data.get("physical_match_ids", ())),
        })
        if artifact.artifact_id in state.artifacts or artifact.artifact_id in state.recordings:
            raise CatalogIntegrityError("artifact_idが重複しています")
        for parent in artifact.parents:
            if parent not in state.recordings and parent not in state.artifacts:
                raise CatalogIntegrityError("親のないartifactです")
        inherited = state.physical_matches(artifact.parents)
        if artifact.physical_match_ids != inherited:
            raise CatalogIntegrityError("artifactの物理試合IDが親と一致しません")
        if artifact.kind in SINGLE_MATCH_KINDS and len(inherited) != 1:
            raise CatalogIntegrityError("1試合から作るartifactが複数の物理試合にまたがっています")
        state.artifacts[artifact.artifact_id] = artifact
    else:
        raise CatalogIntegrityError(f"未知のイベントです: {kind}")


# ------------------------------------------------------------------- catalog


@dataclass(frozen=True, slots=True)
class RegistrationResult:
    recording_id: str
    added: bool
    split: str
    warnings: tuple[str, ...] = ()


def _git_root(path: Path) -> Path | None:
    for candidate in (path, *path.parents):
        if (candidate / ".git").exists():
            return candidate
    return None


class RecordingCatalog:
    """The single private registry. ``root`` must be outside any Git checkout."""

    JOURNAL = "journal.jsonl"
    VIEW = "catalog.json"
    HEAD = "HEAD.json"
    LOCK = ".catalog.lock"

    def __init__(self, root: Path) -> None:
        self.root = Path(root).expanduser().resolve()
        if _git_root(self.root) is not None:
            raise CatalogError("カタログはGitリポジトリの外（非公開の場所）に置いてください")
        self.state = self._replay()

    # -- creation / persistence ----------------------------------------------------

    @classmethod
    def create(
        cls,
        root: Path,
        *,
        seed: str | None = None,
        ratios: Mapping[str, float] | None = None,
    ) -> RecordingCatalog:
        root = Path(root).expanduser().resolve()
        if _git_root(root) is not None:
            raise CatalogError("カタログはGitリポジトリの外（非公開の場所）に置いてください")
        if (root / cls.JOURNAL).exists():
            raise CatalogError("カタログは既に存在します")
        chosen = dict(ratios or DEFAULT_RATIOS)
        if set(chosen) != set(SPLITS) or abs(sum(chosen.values()) - 1.0) > 1e-9 or any(
            value < 0 for value in chosen.values()
        ):
            raise CatalogError("比率はDEVELOPMENT/QUALIFICATION/FINAL_HOLDOUTの合計1.0が必要です")
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        catalog = cls.__new__(cls)
        catalog.root = root
        catalog.state = CatalogState()
        with catalog._locked():
            catalog._append(
                "init",
                {
                    "version": CATALOG_VERSION,
                    "seed": seed or hashlib.sha256(os.urandom(32)).hexdigest()[:32],
                    "ratios": chosen,
                    "allocation_unit": "physical_match_id",
                },
            )
        return catalog

    @contextmanager
    def _locked(self) -> Iterator[None]:
        lock = self.root / self.LOCK
        try:
            lock.mkdir(mode=0o700)
        except FileExistsError as exc:
            raise CatalogError(
                "カタログは別の処理が使用中です（異常終了した場合はロックを確認してから削除）"
            ) from exc
        try:
            # Re-read inside the lock: another process may have appended meanwhile.
            self.state = self._replay()
            yield
            self._write_view()
        finally:
            lock.rmdir()

    def _journal_lines(self) -> list[str]:
        path = self.root / self.JOURNAL
        if not path.exists():
            return []
        return path.read_text(encoding="utf-8").splitlines()

    def _replay(self) -> CatalogState:
        state = CatalogState()
        previous: str | None = None
        lines = self._journal_lines()
        for number, line in enumerate(lines, start=1):
            event = json.loads(line)
            if event.get("prev") != previous or event.get("seq") != number:
                raise CatalogIntegrityError(f"journalの{number}行目で履歴の連鎖が切れています")
            _apply(state, event)
            previous = _line_hash(line)
            state.events = number
        state.head = previous
        # The chain cannot see lines removed from its *end*. HEAD.json records the last
        # appended (seq, sha); it is written after the journal line is durable, so the
        # journal may be at most one event ahead after a crash, never behind.
        anchor_path = self.root / self.HEAD
        if lines and not anchor_path.exists():
            raise CatalogIntegrityError("HEAD.jsonがありません（履歴末尾を検証できません）")
        if anchor_path.exists():
            anchor = json.loads(anchor_path.read_text(encoding="utf-8"))
            seq, sha = int(anchor["seq"]), str(anchor["sha256"])
            if state.events < seq:
                raise CatalogIntegrityError(
                    f"履歴の末尾が削除されています（HEAD {seq}件、journal {state.events}件）"
                )
            if state.events == seq and sha != state.head:
                raise CatalogIntegrityError("HEADとjournal末尾のハッシュが一致しません")
            if state.events > seq + 1:
                raise CatalogIntegrityError("HEADより2件以上新しい履歴があります")
            if state.events == seq + 1 and seq and _line_hash(lines[seq - 1]) != sha:
                raise CatalogIntegrityError("HEADの位置の履歴が書き換えられています")
        return state

    def _write_head(self) -> None:
        anchor = self.root / self.HEAD
        temporary = anchor.with_name(f".{anchor.name}.tmp")
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(json.dumps({"seq": self.state.events, "sha256": self.state.head}) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(anchor)

    def head_anchor(self) -> str:
        """``SEQ:SHA256`` of the journal head, to keep outside the catalog (trusted anchor)."""
        return f"{self.state.events}:{self.state.head}"

    def _append(self, kind: str, data: Mapping[str, Any]) -> None:
        event = {
            "seq": self.state.events + 1,
            "prev": self.state.head,
            "at": utc_now(),
            "type": kind,
            "data": dict(data),
        }
        line = _canonical(event)
        _apply(self.state, json.loads(line))  # validate before it becomes history
        path = self.root / self.JOURNAL
        flags = os.O_WRONLY | os.O_APPEND | os.O_CREAT
        descriptor = os.open(path, flags, 0o600)
        try:
            os.write(descriptor, (line + "\n").encode("utf-8"))
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        self.state.events += 1
        self.state.head = _line_hash(line)
        self._write_head()

    def _write_view(self) -> None:
        view = self.root / self.VIEW
        temporary = view.with_name(f".{view.name}.tmp")
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(json.dumps(self.state.to_dict(), ensure_ascii=False, indent=1) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(view)

    # -- registration --------------------------------------------------------------

    def _known_location(self, path: Path) -> Recording | None:
        stat = path.stat()
        for recording in self.state.recordings.values():
            for location in recording.locations.values():
                if (
                    location["path"] == str(path)
                    and location["size_bytes"] == stat.st_size
                    and location["mtime_ns"] == stat.st_mtime_ns
                ):
                    return recording
        return None

    def register(
        self,
        path: Path,
        *,
        physical_match_id: str | None = None,
        recording_id: str | None = None,
        split: str | None = None,
        role: str = "original",
        source_sha256: str | None = None,
        metadata: Mapping[str, Any] | None = None,
        confirm_distinct: bool = False,
        derived_from: str | None = None,
    ) -> RegistrationResult:
        """Register one recording file. Re-registering the same bytes is a no-op.

        ``derived_from`` marks a re-encoded or trimmed copy of a registered recording.
        It inherits the parent's physical match id and split; a conflicting
        ``physical_match_id`` or ``split`` is refused.
        """
        path = Path(path).expanduser().resolve()
        if not path.is_file() or path.is_symlink():
            raise CatalogError("通常ファイルの録画が必要です")
        with self._locked():
            return self._register_locked(
                path,
                physical_match_id=physical_match_id,
                recording_id=recording_id,
                split=split,
                role=role,
                source_sha256=source_sha256,
                metadata=metadata,
                confirm_distinct=confirm_distinct,
                derived_from=derived_from,
            )

    def _register_locked(
        self,
        path: Path,
        *,
        physical_match_id: str | None,
        recording_id: str | None,
        split: str | None,
        role: str,
        source_sha256: str | None,
        metadata: Mapping[str, Any] | None,
        confirm_distinct: bool,
        derived_from: str | None = None,
    ) -> RegistrationResult:
        stat = path.stat()
        parent: Recording | None = None
        if derived_from is not None:
            parent = self.state.recordings.get(derived_from)
            if parent is None:
                raise CatalogError(f"派生元の録画が未登録です: {derived_from}")
            if physical_match_id not in (None, parent.physical_match_id):
                raise SplitImmutableError("派生動画は派生元と同じ物理試合IDを継承します")
            if split is not None and LEGACY_SPLIT_NAMES.get(split, split) != parent.split:
                raise SplitImmutableError("派生動画は派生元と同じsplitを継承します")
            physical_match_id = parent.physical_match_id
        known = self._known_location(path)
        digest = source_sha256 or (known.source_sha256 if known else sha256_file(path))
        _require_sha(digest)
        existing = self.state.by_sha(digest)
        if existing is not None:
            if physical_match_id and physical_match_id != existing.physical_match_id:
                raise CatalogError("同じ内容の録画が別の物理試合として登録済みです")
            if split and split != existing.split:
                raise SplitImmutableError("登録済み録画のsplitは変更できません")
            if role not in existing.locations or existing.locations[role]["path"] != str(path):
                self._append(
                    "location",
                    {"recording_id": existing.recording_id, "role": role, "path": str(path),
                     "size_bytes": stat.st_size, "mtime_ns": stat.st_mtime_ns},
                )
            return RegistrationResult(existing.recording_id, False, existing.split)
        identifier = _safe_id(recording_id or f"rec_{digest[:12]}", "recording_id")
        if identifier in self.state.recordings:
            raise CatalogError("recording_idは使用済みです")
        physical = _safe_id(physical_match_id or identifier, "physical_match_id")
        warnings: list[str] = []
        similar = [
            r.recording_id
            for r in self.state.recordings.values()
            if r.size_bytes == stat.st_size and r.physical_match_id != physical
        ]
        if similar and not confirm_distinct and parent is None:
            raise CatalogError(
                "同じサイズの別録画があります。別の試合であることを確認してから"
                "confirm_distinctを指定してください"
            )
        if similar:
            warnings.append("same_size_confirmed_distinct")
        bound = self.state.split_of_physical(physical)
        if parent is not None:
            chosen, allocation = parent.split, "derived_from_parent"
        elif split is not None:
            split = LEGACY_SPLIT_NAMES.get(split, split)
            if split not in SPLITS:
                raise CatalogError(f"未知のsplitです: {split}")
            if bound is not None and bound != split:
                raise SplitImmutableError("同じ物理試合は同じsplitにしか登録できません")
            allocation = "explicit_operator_decision" if bound is None else "physical_match_bound"
            chosen = split
        elif bound is not None:
            chosen, allocation = bound, "physical_match_bound"
        else:
            chosen = allocate_split(
                self.state.config["seed"], self.state.config["ratios"], physical
            )
            allocation = "content_blind_hash_bucket"
        self._append(
            "register",
            {
                "recording_id": identifier,
                "source_sha256": digest,
                "size_bytes": stat.st_size,
                "physical_match_id": physical,
                "split": chosen,
                "allocation": allocation,
                "registered_at": utc_now(),
                "origin": "intake" if parent is None else f"derived:{parent.recording_id}",
            },
        )
        self._append(
            "location",
            {"recording_id": identifier, "role": role, "path": str(path),
             "size_bytes": stat.st_size, "mtime_ns": stat.st_mtime_ns},
        )
        if metadata:
            self._append("metadata", {"recording_id": identifier, "metadata": dict(metadata)})
        return RegistrationResult(identifier, True, chosen, tuple(warnings))

    def register_directory(
        self,
        directory: Path,
        *,
        workers: int = 4,
        probe: bool = False,
        ffprobe: str = "ffprobe",
        confirm_distinct: bool = False,
        max_new_files: int | None = None,
        split: str | None = None,
    ) -> list[RegistrationResult]:
        """Incremental intake of every video file under ``directory``.

        Files whose path, size and mtime match a known location are skipped without
        hashing; new files are hashed in parallel *outside* the lock and registered
        afterwards. Each file is its own physical match unless already bound.
        """
        directory = Path(directory).expanduser().resolve()
        files = sorted(
            p for p in directory.rglob("*")
            if p.is_file() and not p.is_symlink() and p.suffix.lower() in VIDEO_SUFFIXES
            and not p.name.startswith(".")
        )
        pending = [p for p in files if self._known_location(p) is None]
        if max_new_files is not None:
            # Bounded batch: the rest stays unregistered and is picked up next run.
            pending = pending[: max(0, max_new_files)]
            files = [p for p in files if p in set(pending) or self._known_location(p)]
        with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
            hashes = dict(zip(pending, pool.map(sha256_file, pending), strict=True))
        results: list[RegistrationResult] = []
        for path in files:
            known = self._known_location(path)
            if known is not None and path not in hashes:
                results.append(RegistrationResult(known.recording_id, False, known.split))
                continue
            metadata = probe_metadata(path, ffprobe) if probe else None
            results.append(
                self.register(
                    path,
                    source_sha256=hashes[path],
                    metadata=metadata,
                    confirm_distinct=confirm_distinct,
                    split=split,
                )
            )
        return results

    def import_legacy(self, path: Path) -> dict[str, Any]:
        """Adopt an existing frozen allocation without re-deciding any split.

        Accepts the JSON written by ``scripts/diagnostics/register_private_sources``
        (``manifest.json``/``allocation.json``) and by the staged/second validation
        registries (``allocation.json``). Splits are mapped name-for-name (``*_CANDIDATE``
        keeps its split), recorded exposure becomes exposure history, rejected sources are
        not adopted, and a conflict with the catalog is reported and left untouched.
        """
        path = Path(path).expanduser().resolve()
        anchor = sha256_file(path)
        document = json.loads(path.read_text(encoding="utf-8"))
        records = document.get("records")
        if not isinstance(records, list):
            raise CatalogError("recordsを持つ割当ファイルが必要です")
        report: dict[str, Any] = {"adopted": 0, "already_present": 0, "skipped_rejected": 0,
                                  "conflicts": []}
        with self._locked():
            for row in records:
                sha = _require_sha(str(row.get("source_sha256")))
                rid = _safe_id(str(row.get("video_id") or row.get("source_id")), "recording_id")
                physical = _safe_id(str(row.get("physical_match_id") or rid), "physical_match_id")
                split = LEGACY_SPLIT_NAMES.get(str(row.get("split")))
                if split is None:
                    report["conflicts"].append({"recording_id": rid, "reason": "unknown_split"})
                    continue
                if row.get("status") == "rejected":
                    report["skipped_rejected"] += 1
                    continue
                existing = self.state.by_sha(sha)
                if existing is not None:
                    if existing.split != split or existing.physical_match_id != physical:
                        report["conflicts"].append(
                            {"recording_id": rid, "reason": "split_or_match_differs"}
                        )
                    else:
                        report["already_present"] += 1
                        if anchor not in existing.legacy_anchors:
                            self._append("anchor", {"recording_id": existing.recording_id,
                                                    "sha256": anchor})
                    continue
                bound = self.state.split_of_physical(physical)
                if (bound is not None and bound != split) or rid in self.state.recordings:
                    report["conflicts"].append({"recording_id": rid, "reason": "identity_conflict"})
                    continue
                locations: dict[str, Path] = {}
                for role, key in (("managed", "managed_path"), ("original", "original_path"),
                                  ("original", "path")):
                    value = row.get(key)
                    if isinstance(value, str) and value and role not in locations:
                        locations[role] = Path(value)
                sizes = [p.stat().st_size for p in locations.values() if p.is_file()]
                self._append(
                    "register",
                    {
                        "recording_id": rid,
                        "source_sha256": sha,
                        "size_bytes": sizes[0] if sizes else int(row.get("size_bytes") or -1),
                        "physical_match_id": physical,
                        "split": split,
                        "allocation": "legacy_frozen_allocation",
                        "registered_at": utc_now(),
                        "origin": f"legacy:{anchor}",
                        "legacy": {
                            "split_label": row.get("split"),
                            "exposure_label": row.get("exposure"),
                            "status": row.get("status"),
                            "allocation_rule": document.get("allocation_rule")
                            or document.get("version"),
                        },
                    },
                )
                for role, location in locations.items():
                    if location.is_file():
                        stat = location.stat()
                        self._append(
                            "location",
                            {"recording_id": rid, "role": role, "path": str(location),
                             "size_bytes": stat.st_size, "mtime_ns": stat.st_mtime_ns},
                        )
                exposure = {
                    "DEVELOPMENT": "development_use",
                    "UNKNOWN_EXPOSURE": "unknown_prior_exposure",
                }.get(str(row.get("exposure")))
                self._append("anchor", {"recording_id": rid, "sha256": anchor})
                if exposure is not None:
                    self._append(
                        "exposure",
                        {"recording_id": rid, "kind": exposure,
                         "note": "legacy registry exposure label"},
                    )
                metadata = {
                    key: row[key]
                    for key in ("duration_sec", "fps", "native_time_base", "video_codec",
                                "width", "height")
                    if key in row
                }
                if metadata:
                    self._append("metadata", {"recording_id": rid, "metadata": metadata})
                report["adopted"] += 1
        return report

    # -- exposure / status ---------------------------------------------------------

    def record_exposure(self, recording_id: str, kind: str, note: str = "") -> None:
        if kind not in EXPOSURE_KINDS:
            raise CatalogError(f"未知のexposure種別です: {kind}")
        with self._locked():
            if recording_id not in self.state.recordings:
                raise CatalogError(f"未登録の録画です: {recording_id}")
            self._append("exposure", {"recording_id": recording_id, "kind": kind, "note": note})

    def open_for_evaluation(self, recording_ids: Sequence[str], purpose: str, note: str) -> None:
        """Explicitly open hold-out material. It is exposed from now on, forever."""
        if purpose not in {"qualification", "final_evaluation"}:
            raise CatalogError("評価目的はqualificationかfinal_evaluationです")
        if not note.strip():
            raise CatalogError("開封理由（承認の記録）が必要です")
        kind = "qualification_opened" if purpose == "qualification" else "final_evaluation_opened"
        with self._locked():
            for recording_id in recording_ids:
                recording = self.state.recordings.get(recording_id)
                if recording is None:
                    raise CatalogError(f"未登録の録画です: {recording_id}")
                expected = "QUALIFICATION" if purpose == "qualification" else "FINAL_HOLDOUT"
                if recording.split != expected:
                    raise LeakageError(f"{recording_id}は{expected}ではありません")
                if not recording.independent_until_opened:
                    raise LeakageError(
                        f"{recording_id}は開発等で露出済みのため独立した評価には使えません"
                    )
            for recording_id in recording_ids:
                self._append("exposure", {"recording_id": recording_id, "kind": kind,
                                          "note": note})

    # -- lineage --------------------------------------------------------------------

    def register_artifact(
        self,
        *,
        kind: str,
        parents: Sequence[str],
        producer: Mapping[str, Any],
        path: Path | None = None,
        sha256: str | None = None,
        artifact_id: str | None = None,
    ) -> str:
        if kind not in ARTIFACT_KINDS:
            raise CatalogError(f"未知のartifact種別です: {kind}")
        if not parents:
            raise CatalogError("artifactには少なくとも1つの親が必要です")
        if not isinstance(producer.get("name"), str) or not producer.get("name"):
            raise CatalogError("producer.nameが必要です")
        digest = sha256 or (sha256_file(Path(path)) if path is not None else None)
        if digest is None:
            raise CatalogError("artifactのpathかsha256が必要です")
        _require_sha(digest)
        identifier = _safe_id(
            artifact_id or f"{kind}_{digest[:12]}", "artifact_id"
        )
        with self._locked():
            wanted_parents = tuple(sorted(set(parents)))
            existing = self.state.artifacts.get(identifier)
            if existing is not None:
                # Re-registration must describe the same thing: same content, kind,
                # parents and producer. Anything else would silently rewrite lineage.
                if existing.sha256 != digest:
                    raise CatalogError("artifact_idは別の内容で使用済みです")
                if (existing.kind, existing.parents, existing.producer) != (
                    kind, wanted_parents, dict(producer)
                ):
                    raise LeakageError("登録済みartifactと種類・親・生成器が一致しません")
                return identifier
            same_content = [
                a for a in self.state.artifacts.values()
                if a.sha256 == digest and a.kind == kind and a.parents != wanted_parents
            ]
            if same_content:
                raise LeakageError("同じ内容のartifactが別の系譜で登録済みです")
            ancestry = set().union(*(self.state.ancestry(p) for p in parents))
            physical = self.state.physical_matches(parents)
            if kind in SINGLE_MATCH_KINDS and len(physical) != 1:
                raise CatalogError(f"{kind}は1つの物理試合からだけ作れます")
            if kind == "model":
                self._guard_locked(ancestry, "training")
            self._append(
                "artifact",
                {
                    "artifact_id": identifier,
                    "kind": kind,
                    "sha256": digest,
                    "parents": sorted(set(parents)),
                    "producer": dict(producer),
                    "registered_at": utc_now(),
                    "path": None if path is None else str(Path(path).resolve()),
                    "physical_match_ids": list(physical),
                },
            )
        return identifier

    def lineage(self, node: str) -> dict[str, Any]:
        recordings = sorted(self.state.ancestry(node))
        return {
            "node": node,
            "recordings": [
                {
                    "recording_id": rid,
                    "split": self.state.recordings[rid].split,
                    "blind": self.state.recordings[rid].blind,
                }
                for rid in recordings
            ],
            "descendants": self.state.descendants(node) if node in self.state.recordings else [],
        }

    # -- guard ----------------------------------------------------------------------

    def guard(self, nodes: Iterable[str], purpose: str) -> None:
        """Raise LeakageError unless every recording behind ``nodes`` may serve ``purpose``."""
        ancestry: set[str] = set()
        for node in nodes:
            ancestry |= self.state.ancestry(node)
        self._guard_locked(ancestry, purpose)

    def _guard_locked(self, recording_ids: Iterable[str], purpose: str) -> None:
        if purpose not in PURPOSES:
            raise CatalogError(f"未知の用途です: {purpose}")
        problems: list[str] = []
        for rid in sorted(recording_ids):
            recording = self.state.recordings[rid]
            if recording.status == "quarantined":
                problems.append(f"{rid}: 隔離中")
            elif purpose in {"training", "tuning", "development_analysis"}:
                if not recording.development_authorised:
                    problems.append(f"{rid}: {recording.split}は開発用途に使えません")
            elif not recording.independent_until_opened:
                problems.append(f"{rid}: 露出済みのため独立した評価には使えません")
            elif purpose == "qualification":
                if recording.split != "QUALIFICATION" or not recording.opened_for(purpose):
                    problems.append(f"{rid}: 開封済みQUALIFICATIONではありません")
            elif recording.split != "FINAL_HOLDOUT" or not recording.opened_for(purpose):
                problems.append(f"{rid}: 開封済みFINAL_HOLDOUTではありません")
        if problems:
            raise LeakageError("; ".join(problems))

    # -- verification ---------------------------------------------------------------

    def verify(
        self,
        *,
        full: bool = True,
        quarantine: bool = True,
        recording_ids: Iterable[str] | None = None,
        trusted_head: str | None = None,
    ) -> dict[str, Any]:
        """Re-derive the state, re-hash locations and quarantine changed sources.

        ``recording_ids`` limits re-hashing to a batch (large libraries are verified in
        several runs). ``trusted_head`` is a ``SEQ:SHA256`` anchor kept outside the
        catalog; the journal must still contain that exact event.
        """
        selected = None if recording_ids is None else set(recording_ids)
        with self._locked():
            view_path = self.root / self.VIEW
            view_matches = True
            if view_path.exists():
                stored = json.loads(view_path.read_text(encoding="utf-8"))
                view_matches = stored == json.loads(json.dumps(self.state.to_dict()))
            if trusted_head is not None:
                seq_text, _, sha = trusted_head.partition(":")
                lines = self._journal_lines()
                seq = int(seq_text)
                if seq < 1 or seq > len(lines) or _line_hash(lines[seq - 1]) != sha:
                    raise CatalogIntegrityError("信頼できるHEADの位置と履歴が一致しません")
            missing: list[str] = []
            changed: list[str] = []
            checked = 0
            for recording in sorted(self.state.recordings.values(), key=lambda r: r.recording_id):
                if selected is not None and recording.recording_id not in selected:
                    continue
                for role, location in sorted(recording.locations.items()):
                    path = Path(location["path"])
                    if not path.is_file():
                        missing.append(f"{recording.recording_id}:{role}")
                        continue
                    checked += 1
                    stat = path.stat()
                    same_stat = (
                        stat.st_size == location["size_bytes"]
                        and stat.st_mtime_ns == location["mtime_ns"]
                    )
                    if (full or not same_stat) and sha256_file(path) != recording.source_sha256:
                        changed.append(f"{recording.recording_id}:{role}")
                        if quarantine and recording.status != "quarantined":
                            self._append(
                                "status",
                                {"recording_id": recording.recording_id,
                                 "status": "quarantined"},
                            )
            return {
                "journal_events": self.state.events,
                "journal_chain": "ok",
                "materialised_view_matches_journal": view_matches,
                "locations_checked": checked,
                "missing_locations": missing,
                "changed_sources": changed,
                "mode": "full_sha256" if full else "size_mtime_then_sha256",
                "journal_head": self.head_anchor(),
            }

    # -- incremental processing -----------------------------------------------------

    def plan(
        self,
        producer: Mapping[str, Any],
        *,
        purpose: str = "development_analysis",
        artifact_kind: str | None = None,
    ) -> list[str]:
        """Recordings allowed for ``purpose`` that this exact producer has not processed."""
        key = {k: producer.get(k) for k in ("name", "version", "config_sha256")}
        done = {
            parent
            for artifact in self.state.artifacts.values()
            if {k: artifact.producer.get(k) for k in key} == key
            and (artifact_kind is None or artifact.kind == artifact_kind)
            for parent in artifact.parents
        }
        allowed: list[str] = []
        for rid in sorted(self.state.recordings):
            if rid in done:
                continue
            try:
                self._guard_locked([rid], purpose)
            except LeakageError:
                continue
            allowed.append(rid)
        return allowed

    # -- views ----------------------------------------------------------------------

    def learning_view(
        self,
        *,
        seed: str = "continual-v1",
        ratios: Mapping[str, float] | None = None,
        include_authorised_exposed: bool = False,
    ) -> list[dict[str, Any]]:
        """Records for the continual-learning registry (#105/#154): TRAIN/VALIDATION/FROZEN_TEST.

        All three come from development-authorised recordings only, sub-split by physical
        match. QUALIFICATION / FINAL_HOLDOUT never enter this view unless the user
        authorised their development use *and* ``include_authorised_exposed`` is set;
        they are then marked ``exposed_holdout``.
        """
        chosen = dict(ratios or {"TRAIN": 0.6, "VALIDATION": 0.2, "FROZEN_TEST": 0.2})
        if set(chosen) != {"TRAIN", "VALIDATION", "FROZEN_TEST"}:
            raise CatalogError("学習用比率はTRAIN/VALIDATION/FROZEN_TESTです")
        rows: list[dict[str, Any]] = []
        for order, (rid, recording) in enumerate(sorted(self.state.recordings.items())):
            if recording.status == "quarantined" or not recording.development_authorised:
                continue
            if recording.split != "DEVELOPMENT" and not include_authorised_exposed:
                continue
            bucket = hash_bucket(seed, recording.physical_match_id)
            edge, sub = 0.0, "FROZEN_TEST"
            for name in ("TRAIN", "VALIDATION", "FROZEN_TEST"):
                edge += chosen[name]
                if bucket < edge:
                    sub = name
                    break
            location = recording.locations.get("managed") or recording.locations.get("original")
            rows.append(
                {
                    "source_id": rid,
                    "physical_match_id": recording.physical_match_id,
                    "archive": None if location is None else location["path"],
                    "archive_sha256": recording.source_sha256,
                    "archive_bytes": recording.size_bytes,
                    "split": sub,
                    "catalog_split": recording.split,
                    "exposed_holdout": recording.split != "DEVELOPMENT",
                    "order": order,
                }
            )
        return rows

    def learning_archives(
        self,
        *,
        artifact_kind: str = "frames",
        seed: str = "continual-v1",
        ratios: Mapping[str, float] | None = None,
        include_authorised_exposed: bool = False,
    ) -> list[dict[str, Any]]:
        """Derived archives (e.g. HUD crop zips) for the continual-learning registry.

        Each archive inherits its recording's physical match id and authorisation, and
        the TRAIN/VALIDATION/FROZEN_TEST sub-split is decided per physical match, so all
        archives of one match land in the same sub-split.
        """
        by_recording = {
            row["source_id"]: row
            for row in self.learning_view(
                seed=seed, ratios=ratios, include_authorised_exposed=include_authorised_exposed
            )
        }
        rows: list[dict[str, Any]] = []
        for artifact in sorted(self.state.artifacts.values(), key=lambda a: a.artifact_id):
            if artifact.kind != artifact_kind or artifact.path is None:
                continue
            recordings = sorted(self.state.ancestry(artifact.artifact_id))
            parents = [by_recording.get(rid) for rid in recordings]
            if not parents or any(row is None for row in parents):
                continue  # some ancestor is not allowed for development
            splits = {row["split"] for row in parents if row is not None}
            if len(artifact.physical_match_ids) != 1 or len(splits) != 1:
                continue
            path = Path(artifact.path)
            rows.append(
                {
                    "source_id": artifact.artifact_id,
                    "physical_match_id": artifact.physical_match_ids[0],
                    "archive": str(path),
                    "archive_sha256": artifact.sha256,
                    "archive_bytes": path.stat().st_size if path.is_file() else None,
                    "split": splits.pop(),
                    "recording_ids": recordings,
                    "exposed_holdout": any(
                        row is not None and row["exposed_holdout"] for row in parents
                    ),
                }
            )
        return rows

    def sync_learning_registry(
        self, registry: Any, rows: Sequence[Mapping[str, Any]]
    ) -> dict[str, int]:
        """Feed rows into a continual-learning ``DatasetRegistry`` (#154) duck-typed.

        The catalog decides the split; the registry's own hash bucket is not used. A
        registry that already holds a physical match in another split raises its own
        ``LeakageError`` and nothing is forced.
        """
        added = existing = 0
        for row in rows:
            archive = Path(str(row["archive"]))
            if sha256_file(archive) != row["archive_sha256"]:
                raise CatalogIntegrityError("学習用アーカイブの内容が登録時と異なります")
            _, is_new = registry.intake(
                str(row["source_id"]), str(row["physical_match_id"]), archive,
                split=str(row["split"]), note="recording_catalog",
            )
            added += int(bool(is_new))
            existing += int(not is_new)
        return {"added": added, "already_present": existing}

    def recordings_under(self, prefix: Path) -> list[str]:
        """Recording ids with a location under ``prefix`` (e.g. one recording folder)."""
        root = str(Path(prefix).expanduser().resolve())
        return sorted(
            rid for rid, recording in self.state.recordings.items()
            if any(
                item["path"] == root or item["path"].startswith(root.rstrip("/\\") + os.sep)
                for item in recording.locations.values()
            )
        )

    def public_summary(self) -> dict[str, Any]:
        """Counts only: no ids, hashes, paths, names or timestamps."""
        recordings = list(self.state.recordings.values())
        return {
            "kind": "anonymous_recording_catalog_summary",
            "version": CATALOG_VERSION,
            "recordings": len(recordings),
            "physical_matches": len({r.physical_match_id for r in recordings}),
            "by_split": {s: sum(r.split == s for r in recordings) for s in SPLITS},
            "blind_by_split": {
                s: sum(r.split == s and r.blind for r in recordings) for s in PROTECTED_SPLITS
            },
            "development_authorised_protected": sum(
                r.split in PROTECTED_SPLITS and r.development_authorised for r in recordings
            ),
            "quarantined": sum(r.status == "quarantined" for r in recordings),
            "artifacts_by_kind": dict(sorted(Counter(a.kind for a in
                                                     self.state.artifacts.values()).items())),
            "allocation_methods": dict(sorted(Counter(r.allocation for r in recordings).items())),
        }

    def private_tokens(self) -> set[str]:
        """Strings that must never appear in a public (Git) file."""
        tokens: set[str] = set()
        for recording in self.state.recordings.values():
            tokens.add(recording.source_sha256)
            tokens.add(recording.recording_id)
            tokens.add(recording.physical_match_id)
            tokens.update(item["path"] for item in recording.locations.values())
            tokens.update(Path(item["path"]).name for item in recording.locations.values())
        for artifact in self.state.artifacts.values():
            tokens.add(artifact.sha256)
            if artifact.path:
                tokens.add(artifact.path)
        tokens.add(str(self.root))
        return {token for token in tokens if len(token) >= 6}

    def leak_check(self, files: Iterable[Path]) -> list[dict[str, str]]:
        tokens = self.private_tokens()
        findings: list[dict[str, str]] = []
        for path in files:
            try:
                text = Path(path).read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for token in tokens:
                if token in text:
                    # Report the kind of token, never the token itself.
                    kind = (
                        "sha256" if _SHA.match(token)
                        else "path" if ("/" in token or "\\" in token)
                        else "identifier_or_filename"
                    )
                    findings.append({"file": str(path), "token_kind": kind})
        return findings


def probe_metadata(path: Path, ffprobe: str = "ffprobe") -> dict[str, Any]:
    """Container metadata only (no decoding of frames)."""
    result = subprocess.run(
        [ffprobe, "-v", "error", "-select_streams", "v:0", "-show_entries",
         "stream=codec_name,width,height,avg_frame_rate,time_base:format=duration",
         "-of", "json", str(path)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=120, check=False,
    )
    if result.returncode:
        raise CatalogError("ffprobeでメタデータを取得できません")
    data = json.loads(result.stdout or "{}")
    stream = (data.get("streams") or [{}])[0]
    return {
        "video_codec": stream.get("codec_name"),
        "width": stream.get("width"),
        "height": stream.get("height"),
        "avg_frame_rate": stream.get("avg_frame_rate"),
        "native_time_base": stream.get("time_base"),
        "duration_sec": (data.get("format") or {}).get("duration"),
    }

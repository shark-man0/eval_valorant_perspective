"""Private, source-bound incremental features and append-only experiment history.

This consumes accepted DEVELOPMENT receipts; it does not register videos, infer
physical identity or change Source/GT splits. No trial can update Production.
"""

from __future__ import annotations

import io
import json
import zipfile
from collections.abc import Callable
from dataclasses import asdict
from pathlib import Path
from typing import Any

import numpy as np

from .development_learning_dataset import FrameRecord, validate_dataset
from .development_marker_features import Array, _digest, _private_model_output


def append_snapshot(
    previous: list[FrameRecord],
    additions: list[FrameRecord],
) -> tuple[list[FrameRecord], dict[str, Any]]:
    """Exact extraction dedup, preserving caller-verified physical-match groups."""
    if len(previous) + len(additions) > 16384:
        raise ValueError("Bounded incremental snapshot required")
    validate_dataset([*previous, *additions])
    seen = {_digest(asdict(f)) for f in previous}
    merged = list(previous)
    duplicates = 0
    for frame in additions:
        key = _digest(asdict(frame))
        if key in seen:
            duplicates += 1
        else:
            merged.append(frame)
            seen.add(key)
    old_sources = {f.source_sha256 for f in previous}
    old_groups = {f.leakage_group_id for f in previous}
    return merged, {
        "snapshot_fingerprint": _digest([asdict(f) for f in merged]),
        "added_extractions": len(merged) - len(previous),
        "exact_duplicates": duplicates,
        "new_source_hashes": len({f.source_sha256 for f in merged} - old_sources),
        "new_declared_physical_groups": len({f.leakage_group_id for f in merged} - old_groups),
        "physical_identity_not_inferred_from_hash": True,
        "qualification": "development_only",
        "formal_outputs": 0,
    }


class DevelopmentFeatureCache:
    """Current source/epoch/pixels/ROI/Profile/feature/build identity in every key."""

    def __init__(self, root: Path) -> None:
        _private_model_output(root / "placeholder")
        root.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.root = root.resolve()
        self.hits = self.misses = 0

    def get_or_compute(
        self,
        frame: FrameRecord,
        *,
        feature_fingerprint: str,
        profile_fingerprint: str,
        map_build: str,
        patch_sha256: str,
        compute: Callable[[], Array],
    ) -> tuple[Array, bool, str]:
        frame.validate()
        if (
            any(
                not isinstance(s, str)
                or len(s) != 64
                or any(c not in "0123456789abcdef" for c in s)
                for s in (feature_fingerprint, profile_fingerprint, patch_sha256)
            )
            or not isinstance(map_build, str)
            or not map_build
        ):
            raise ValueError("Current feature/Profile/patch fingerprints and build scope required")
        key = _digest(
            {
                "frame": asdict(frame),
                "feature": feature_fingerprint,
                "profile": profile_fingerprint,
                "patch": patch_sha256,
                "build": map_build,
            }
        )
        path = self.root / (key + ".npz")
        if path.exists():
            result = self._read(path, key)
            self.hits += 1
            return result, True, key
        result = compute()
        if (
            not isinstance(result, np.ndarray)
            or result.ndim != 1
            or not 1 <= len(result) <= 512
            or not np.isfinite(result).all()
        ):
            raise ValueError("Bounded finite feature vector required")
        result = result.astype(np.float64, copy=True)
        content = io.BytesIO()
        np.savez_compressed(
            content, features=result, key=np.frombuffer(key.encode("ascii"), np.uint8)
        )
        try:
            with path.open("xb") as stream:
                stream.write(content.getvalue())
        except FileExistsError:
            if not np.array_equal(self._read(path, key), result):
                raise ValueError("Same cache identity produced different features") from None
        self.misses += 1
        return result, False, key

    @staticmethod
    def _read(path: Path, key: str) -> Array:
        if path.stat().st_size > 16384:
            raise ValueError("Bounded feature cache entry required")
        content = path.read_bytes()
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            if (
                set(archive.namelist()) != {"features.npy", "key.npy"}
                or len(archive.infolist()) != 2
                or sum(member.file_size for member in archive.infolist()) > 16384
            ):
                raise ValueError("Bounded tensor-only feature cache required")
        with np.load(io.BytesIO(content), allow_pickle=False) as data:
            features, raw = data["features"], data["key"]
            if (
                raw.dtype != np.uint8
                or raw.ndim != 1
                or raw.tobytes() != key.encode("ascii")
                or features.ndim != 1
                or features.dtype != np.float64
                or not 1 <= len(features) <= 512
                or not np.isfinite(features).all()
            ):
                raise ValueError("Feature cache content/identity mismatch")
            return np.array(features, copy=True)


class DevelopmentTrialHistory:
    """Immutable start/end records and explicit non-adoption; no active model pointer."""

    def __init__(self, root: Path) -> None:
        _private_model_output(root / "placeholder")
        root.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.root = root.resolve()

    def begin(
        self,
        *,
        snapshot_fingerprint: str,
        code_fingerprint: str,
        previous_model_fingerprint: str,
        trial_name: str,
    ) -> str:
        if (
            not trial_name
            or len(trial_name) > 128
            or any(
                len(s) != 64
                for s in (snapshot_fingerprint, code_fingerprint, previous_model_fingerprint)
            )
        ):
            raise ValueError("Bounded versioned experiment identity required")
        start = {
            "snapshot_fingerprint": snapshot_fingerprint,
            "code_fingerprint": code_fingerprint,
            "previous_model_fingerprint": previous_model_fingerprint,
            "trial_name": trial_name,
            "status": "started",
            "production_adoption": False,
        }
        key = _digest(start)
        self._write(key + "_start.json", start)
        return key

    def finish(
        self,
        key: str,
        *,
        candidate_model_fingerprint: str,
        baseline: dict[str, Any],
        candidate: dict[str, Any],
        failure: str | None = None,
    ) -> dict[str, Any]:
        if len(key) != 64 or any(c not in "0123456789abcdef" for c in key):
            raise ValueError("Exact trial identity required")
        start = json.loads((self.root / (key + "_start.json")).read_text(encoding="utf-8"))
        if _digest(start) != key or len(candidate_model_fingerprint) != 64:
            raise ValueError("Bound experiment/model identity required")
        fields = {"TP", "FP", "FN", "old_correct_lost", "known_negative_matches"}
        measurable = all(
            fields <= m.keys() and all(type(m[f]) is int and m[f] >= 0 for f in fields)
            for m in (baseline, candidate)
        )
        # A gain is meaningful only on the same fixed input/annotation scope.
        # A missing observation or a changed positive denominator is not a win.
        measurable = bool(
            measurable
            and isinstance(baseline.get("input_fingerprint"), str)
            and len(baseline["input_fingerprint"]) == 64
            and all(c in "0123456789abcdef" for c in baseline["input_fingerprint"])
            and baseline["input_fingerprint"] == candidate.get("input_fingerprint")
            and baseline["TP"] + baseline["FN"] == candidate["TP"] + candidate["FN"]
        )
        gain = bool(
            not failure
            and measurable
            and candidate["TP"] > baseline["TP"]
            and candidate["FP"] <= baseline["FP"]
            and candidate["old_correct_lost"] == 0
            and candidate["known_negative_matches"] <= baseline["known_negative_matches"]
        )
        result = {
            "trial_id": key,
            "candidate_model_fingerprint": candidate_model_fingerprint,
            "baseline": baseline,
            "candidate": candidate,
            "failure": failure,
            "development_gain": gain,
            "status": "failed"
            if failure
            else "research_candidate"
            if gain
            else "rejected"
            if measurable
            else "insufficient_evidence",
            "retained_default_model_fingerprint": start["previous_model_fingerprint"],
            "production_adoption": False,
            "qualification": "development_only",
            "ownership": "UNKNOWN",
            "formal_outputs": 0,
        }
        self._write(key + "_end.json", result)
        return result

    def _write(self, name: str, value: dict[str, Any]) -> None:
        content = json.dumps(value, sort_keys=True, allow_nan=False).encode("utf-8")
        path = self.root / name
        try:
            with path.open("xb") as stream:
                stream.write(content)
        except FileExistsError:
            if path.read_bytes() != content:
                raise ValueError("Experiment history is immutable") from None

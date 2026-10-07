"""Point-frame E2E suites with evaluator-only expectations.

The runner must construct its decode request from each frame's ``pts_sec``
only. This module is the evaluator boundary: it never prepares recognizer input.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

CATEGORIES = (
    "live",
    "spectator",
    "combat_report",
    "buy_menu",
    "unknown",
    "hp_numeric",
    "timer_score",
    "known_false_positive",
    "regression_protection",
    "round_boundary",
)
VALID_CATEGORIES = frozenset(CATEGORIES)
EXPECTED_STATES = frozenset(
    {
        "live_first_person",
        "spectator_first_person",
        "remote_control_view",
        "buy_menu_open",
        "expanded_tactical_map",
        "unknown",
    }
)
_STATE_BY_CATEGORY = {
    "live": "live_first_person",
    "spectator": "spectator_first_person",
    "buy_menu": "buy_menu_open",
}
_VALUE_FIELDS = {
    "hp": "hp",
    "timer": "round_time_remaining_sec",
    "score_player": "score_ally",
    "score_enemy": "score_enemy",
}
_NUMERIC_CATEGORIES = {
    "hp": "hp_numeric",
    "timer": "timer_score",
    "score_player": "timer_score",
    "score_enemy": "timer_score",
}
_REPO_ROOT = Path(__file__).resolve().parents[2]


def _finite_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _validate_suite(suite: Any, mode: str, source_sha256: str) -> None:
    if not isinstance(suite, dict) or suite.get("schema_version") != 1:
        raise ValueError("suite schema_version must be 1")
    if suite.get("mode") != mode:
        raise ValueError(f"suite mode mismatch: expected {mode!r}")
    if suite.get("source_sha256") != source_sha256:
        raise ValueError("suite source_sha256 does not match requested video")
    if not isinstance(suite.get("suite_id"), str) or not suite["suite_id"]:
        raise ValueError("suite_id must be a non-empty string")
    if not isinstance(suite.get("video_id"), str) or not suite["video_id"]:
        raise ValueError("video_id must be a non-empty string")
    prefix = suite.get("calibration_prefix")
    if not isinstance(prefix, list) or not prefix or not all(_finite_number(x) for x in prefix):
        raise ValueError("calibration_prefix must be a non-empty list of finite PTS values")
    frames = suite.get("frames")
    if not isinstance(frames, list) or not frames:
        raise ValueError("frames must be a non-empty list")
    previous = -math.inf
    for index, frame in enumerate(frames):
        if not isinstance(frame, dict) or not _finite_number(frame.get("pts_sec")):
            raise ValueError(f"frame {index} requires finite pts_sec")
        pts = frame["pts_sec"]
        if pts <= previous:
            raise ValueError("frame PTS values must be distinct and strictly sorted")
        previous = pts
        cats = frame.get("categories")
        if (
            not isinstance(cats, list)
            or not cats
            or any(not isinstance(c, str) or c not in VALID_CATEGORIES for c in cats)
            or len(set(cats)) != len(cats)
        ):
            raise ValueError(f"frame {index} has invalid or duplicate categories")
        if "expected_state" in frame and frame["expected_state"] not in EXPECTED_STATES:
            raise ValueError(f"frame {index} has unsupported expected_state")
        numeric = frame.get("expected_numeric", {})
        if not isinstance(numeric, dict):
            raise ValueError(f"frame {index} expected_numeric must be an object")
        for field, value in numeric.items():
            if field not in _VALUE_FIELDS or not (
                isinstance(value, str) if field == "timer" else _finite_number(value)
            ):
                raise ValueError(
                    f"frame {index} has unsupported expected numeric field/value: {field}"
                )
            needed = _NUMERIC_CATEGORIES[field]
            if needed not in cats:
                raise ValueError(f"frame {index} numeric label {field} requires category {needed}")
        if (
            "provenance" not in frame
            or not isinstance(frame["provenance"], list)
            or not frame["provenance"]
        ):
            raise ValueError(f"frame {index} requires provenance")


def load_suite(
    path: str | Path, mode: str, source_sha256: str, categories: Iterable[str] = ()
) -> dict:
    """Load, validate, bind to source video, and optionally select categories.

    Historical provenance files may be absent in a portable checkout. That is
    surfaced in ``provenance_diagnostics``; an extant file with a changed hash
    is also reported without silently changing labels.
    """
    p = Path(path)
    suite = json.loads(p.read_text(encoding="utf-8"))
    _validate_suite(suite, mode, source_sha256)
    requested = list(categories)
    if len(requested) != len(set(requested)) or any(x not in VALID_CATEGORIES for x in requested):
        raise ValueError("categories must be distinct valid suite categories")
    if requested:
        requested_set = set(requested)
        suite["frames"] = [
            frame for frame in suite["frames"] if requested_set.intersection(frame["categories"])
        ]
    suite["selected_categories"] = sorted(requested)
    suite["suite_sha256"] = hashlib.sha256(p.read_bytes()).hexdigest()
    suite["manifest_path"] = str(p)
    diagnostics = []
    for frame in suite["frames"]:
        for evidence in frame["provenance"]:
            evidence_path = Path(evidence["path"])
            if not evidence_path.is_absolute():
                evidence_path = _REPO_ROOT / evidence_path
            expected = evidence.get("sha256")
            if not isinstance(expected, str) or len(expected) != 64:
                diagnostics.append({"path": evidence["path"], "status": "invalid_hash"})
            elif not evidence_path.is_file():
                diagnostics.append({"path": evidence["path"], "status": "missing"})
            else:
                actual = hashlib.sha256(evidence_path.read_bytes()).hexdigest()
                if actual != expected:
                    raise ValueError(
                        "provenance hash mismatch for "
                        f"{evidence['path']}: expected {expected}, got {actual}"
                    )
    suite["provenance_diagnostics"] = diagnostics
    return suite


def selected_frames(suite: Mapping[str, Any], categories: Iterable[str] = ()) -> list[dict]:
    """Return recognizer-safe PTS requests matching categories in PTS order.

    Labels, categories, notes, and provenance stay on the evaluator side.
    """
    wanted = set(categories)
    if wanted - VALID_CATEGORIES:
        raise ValueError(f"invalid categories: {sorted(wanted - VALID_CATEGORIES)}")
    return [
        {"pts_sec": f["pts_sec"]}
        for f in suite["frames"]
        if not wanted or wanted.intersection(f["categories"])
    ]


def _timer_seconds(value: str) -> float | None:
    parts = value.split(":")
    if len(parts) != 2 or not all(part.isdigit() for part in parts):
        return None
    minutes, seconds = map(int, parts)
    if seconds >= 60:
        return None
    return float(minutes * 60 + seconds)


def _actual_value(observation: Mapping[str, Any], expected_field: str) -> Any:
    values = observation.get("values")
    if not isinstance(values, Mapping):
        return None
    return values.get(_VALUE_FIELDS[expected_field])


def evaluate_frames(suite: Mapping[str, Any], observations: Iterable[Mapping[str, Any]]) -> dict:
    """Compare fixed point labels to raw observations without inferring labels.

    Unknown-scene taxonomy entries and all frames without an independent
    expected field are reported as not evaluated.
    """
    obs = [
        row
        for row in observations
        if isinstance(row, Mapping) and _finite_number(row.get("time_sec"))
    ]
    counts = {"passed": 0, "failed": 0, "not_evaluated": 0}
    failures = []
    not_evaluated = []
    states = {"unknown": 0, "live": 0, "spectator": 0, "menu": 0}
    category_counts: dict[str, int] = {}
    for frame in suite["frames"]:
        for category in frame["categories"]:
            category_counts[category] = category_counts.get(category, 0) + 1
        pts = frame["pts_sec"]
        assertions = []
        if "expected_state" in frame and not (
            frame["expected_state"] == "unknown" and "unknown" in frame["categories"]
        ):
            assertions.append(("primary_state", frame["expected_state"], "primary_state"))
        for field, expected in frame.get("expected_numeric", {}).items():
            wanted = _timer_seconds(expected) if field == "timer" else expected
            assertions.append((field, wanted, field))
        matches = [row for row in obs if abs(row["time_sec"] - pts) <= 1e-6]
        if len(matches) != 1:
            if assertions:
                counts["failed"] += 1
                reason = (
                    "expected_value_unavailable" if not matches else "observation_pts_ambiguous"
                )
                failures.extend(
                    {
                        "pts_sec": pts,
                        "categories": frame["categories"],
                        "field": field,
                        "expected": expected,
                        "actual": None,
                        "reason": reason,
                    }
                    for field, expected, _ in assertions
                )
            else:
                counts["not_evaluated"] += 1
                not_evaluated.append(
                    {
                        "pts_sec": pts,
                        "categories": frame["categories"],
                        "reason": "observation_missing"
                        if not matches
                        else "observation_pts_ambiguous",
                    }
                )
            continue
        actual = matches[0]
        state = actual.get("primary_state")
        states[
            "unknown"
            if state is None or state == "unknown"
            else "live"
            if state == "live_first_person"
            else "spectator"
            if state == "spectator_first_person"
            else "menu"
            if state == "buy_menu_open"
            else "unknown"
        ] += 1
        assertions = [
            (
                field,
                expected,
                state if field == "primary_state" else _actual_value(actual, field),
            )
            for field, expected, _ in assertions
        ]
        if not assertions:
            counts["not_evaluated"] += 1
            not_evaluated.append(
                {
                    "pts_sec": pts,
                    "categories": frame["categories"],
                    "reason": "no_independent_expected_label",
                }
            )
            continue
        failed = False
        for field, expected, got in assertions:
            field_failed = False
            if got is None:
                field_failed = True
                reason = "expected_value_unavailable"
            elif expected is None:
                field_failed = True
                reason = "invalid_expected_label"
            elif isinstance(expected, (int, float)) and isinstance(got, (int, float)):
                if not math.isclose(float(got), float(expected), abs_tol=1e-6):
                    field_failed = True
                    reason = "value_mismatch"
            elif got != expected:
                field_failed = True
                reason = "value_mismatch"
            if field_failed:
                failed = True
                failures.append(
                    {
                        "pts_sec": pts,
                        "categories": frame["categories"],
                        "field": field,
                        "expected": expected,
                        "actual": got,
                        "reason": reason,
                    }
                )
        if failed:
            counts["failed"] += 1
        else:
            counts["passed"] += 1
    return {
        "schema_version": 1,
        "suite_id": suite["suite_id"],
        "mode": suite["mode"],
        "video_id": suite["video_id"],
        "source_sha256": suite["source_sha256"],
        "suite_sha256": suite.get("suite_sha256"),
        "selected_categories": suite.get("selected_categories", []),
        "counts": counts,
        "failures": failures,
        "not_evaluated_frames": not_evaluated,
        "coverage": {
            "frame_count": len(suite["frames"]),
            "category_counts": category_counts,
            "state_counts": states,
            "asserted_frames": counts["passed"] + counts["failed"],
            "calibration_prefix": suite.get("calibration_prefix", []),
            "limitations": [
                "point frames only; no full-pack assertions or continuous event/round claims"
            ],
        },
    }


def compare_metrics(current: Mapping[str, Any], previous: Mapping[str, Any]) -> list[dict]:
    """Compare only reports with the same mode, suite selection, and source."""
    identity = ("mode", "suite_sha256", "selected_categories", "video_id", "source_sha256")
    for key in identity:
        if current.get(key) != previous.get(key):
            raise ValueError(f"cannot compare frame-suite reports with different {key}")

    def metric(report, name):
        if name in report:
            return report[name]
        if name in report.get("counts", {}):
            return report["counts"][name]
        if name in report.get("coverage", {}).get("state_counts", {}):
            return report["coverage"]["state_counts"][name]
        return None

    names = (
        "passed",
        "failed",
        "not_evaluated",
        "unknown",
        "live",
        "spectator",
        "menu",
        "wall_sec",
        "fps",
    )
    result = []
    for name in names:
        now, old = metric(current, name), metric(previous, name)
        delta = (
            now - old if isinstance(now, (int, float)) and isinstance(old, (int, float)) else None
        )
        percent = (delta / old * 100) if delta is not None and old != 0 else None
        result.append(
            {
                "metric": name,
                "current": now,
                "previous": old,
                "delta": delta,
                "percent_change": percent,
            }
        )
    return result

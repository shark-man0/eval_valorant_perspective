"""Private bounded replay, admission and explicit UNKNOWN evaluation."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

from .adapters import hud_packet, map_packet, owner_ui, round_readers
from .evidence import digest, freeze_native_sample, is_sha, source_scope
from .game import DevelopmentGameTimeline, map_context
from .learning import compare_temporal_learning


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_private(path: Path, value: Any) -> None:
    if any((parent / ".git").exists() for parent in path.resolve().parents):
        raise ValueError("Private timeline output must remain outside Git checkouts")
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with os.fdopen(
        os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w", encoding="utf-8"
    ) as stream:
        json.dump(value, stream, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
        stream.write("\n")


class SourcePolicy:
    """Exact allowlist from existing accepted DEVELOPMENT; never open source media."""

    def __init__(self, policy: dict[str, Any]) -> None:
        manifest_path, allocation_path = Path(policy["manifest"]), Path(policy["allocation"])
        if (
            file_sha(manifest_path) != policy["manifest_sha256"]
            or file_sha(allocation_path) != policy["allocation_sha256"]
        ):
            raise ValueError("Frozen registry/allocation changed")
        manifest = read_json(manifest_path)
        self.allowed = {
            r["source_sha256"]: r
            for r in manifest["records"]
            if r["source_sha256"] in policy["allowed_source_sha256s"]
        }
        if (
            set(self.allowed) != set(policy["allowed_source_sha256s"])
            or not self.allowed
            or not all(is_sha(s) for s in self.allowed)
        ):
            raise ValueError("Explicit existing source allowlist required")
        for record in self.allowed.values():
            if (
                record["status"] != "accepted"
                or record["split"] != "DEVELOPMENT"
                or record["exposure"] != "DEVELOPMENT"
            ):
                raise ValueError("Protected/unaccepted source is forbidden")
        if set(self.allowed) & set(policy.get("protected_source_sha256s", [])):
            raise ValueError("Protected source cannot be allowlisted")
        self.manifest_sha = policy["manifest_sha256"]
        self.allocation_sha = policy["allocation_sha256"]

    def admit(self, sample: dict[str, Any], frame: dict[str, Any] | None = None) -> None:
        source = self.allowed.get(sample["source_sha256"])
        if source is None or source["video_id"] != sample["source_id"]:
            raise ValueError("Sample outside frozen DEVELOPMENT allowlist")
        if frame:
            receipt = frame["source_acceptance"]
            if (
                frame["leakage_group_id"] != source["physical_match_id"]
                or frame["source_sha256"] != sample["source_sha256"]
                or frame["split"] != "DEVELOPMENT_TRAIN"
                or receipt["accepted"] is not True
                or receipt["manifest_sha256"] != self.manifest_sha
                or receipt["allocation_sha256"] != self.allocation_sha
            ):
                raise ValueError("Source/exposure/physical-match admission mismatch")


def compare_reviewed(result: dict[str, Any], reviews: list[dict[str, Any]]) -> dict[str, Any]:
    """Only exact explicit reviewed labels enter denominators; UNKNOWN stays outside."""
    frames = {r["sample"]["sample_sha256"]: r for r in result["frames"]}
    counts: Counter[str] = Counter()
    for review in reviews:
        if review.get("origin") != "human_exact_frame" or not is_sha(review.get("review_sha256")):
            raise ValueError("Independent exact-frame human review required")
        label, domain = review["value"], review["domain"]
        if domain not in {"round", "life", "camera"}:
            raise ValueError("Known review domain required")
        frame = frames.get(review["sample_sha256"])
        if label == "UNKNOWN" or frame is None:
            counts["excluded_unknown_or_unexposed"] += 1
            continue
        actual = frame[domain]["value"]
        counts["reviewed"] += 1
        counts[
            "correct" if actual == label else "abstained" if actual == "UNKNOWN" else "incorrect"
        ] += 1
    return {
        **dict(counts),
        "unreviewed_not_negative": True,
        "population_accuracy": None,
        "strict_qualification": "NOT_EVALUATED",
    }


def summary(result: dict[str, Any]) -> dict[str, Any]:
    seconds, frames = result["seconds"], result["frames"]
    return {
        "native_frames": len(frames),
        "physical_native_points": len(
            {
                (
                    f["sample"]["source_sha256"],
                    f["sample"]["native_pts_tick"],
                    f["sample"]["native_time_base"],
                    f["sample"]["native_pixel_sha256"],
                )
                for f in frames
            }
        ),
        "acquisition_second_addresses": len(result["acquisition_seconds"]),
        "observation_records": len(result["observations"]),
        "native_scopes": len({source_scope(f["sample"]) for f in frames}),
        "seconds": len(seconds),
        "missing_second_bins": sum(not s["observation_present"] for s in seconds),
        "unknown_second_bins": {
            d: sum(s[d]["value"] == "UNKNOWN" for s in seconds) for d in ("round", "life", "camera")
        },
        "unknown_sample_points": {
            d: sum(f[d]["value"] == "UNKNOWN" for f in frames) for d in ("round", "life", "camera")
        },
        "transition_candidates": dict(Counter(t["kind"] for t in result["transitions"])),
        "round_candidate_group_counts": dict(
            Counter(g["source_and_kind"][1] for g in result["round_candidate_groups"])
        ),
        "current_map_candidate_frames": sum(
            bool(f["map"]["current_self_position_candidates"]) for f in frames
        ),
        "duration_semantics": "second bins, not fully observed duration or negative exposure",
        "correct_round_start": None,
        "false_round_start": None,
        "correct_round_end": None,
        "false_round_end": None,
        "internal_boundary_time_error": None,
        "self_attribution_accuracy": None,
        "position_zone_accuracy": None,
        "previous_correct_lost": None,
        "qualified_facts": 0,
        "qualified_events": 0,
        "practical_evaluation": "DEVELOPMENT_ONLY",
        "strict_qualification": "NOT_EVALUATED",
    }


def peak_rss_mib() -> float | None:
    try:
        import resource
    except ImportError:
        return None
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return float(value / (1024**2 if sys.platform == "darwin" else 1024))


def replay(
    *,
    policy_path: Path,
    hud_path: Path | None = None,
    map_path: Path | None = None,
    hud_supplement: Path | None = None,
) -> dict[str, Any]:
    policy = SourcePolicy(read_json(policy_path))
    engine = DevelopmentGameTimeline()
    started = time.perf_counter()
    inputs: dict[str, str] = {}
    supplier_hints = []
    hud_inputs = [
        (name, path)
        for name, path in (("hud", hud_path), ("hud_supplement", hud_supplement))
        if path is not None
    ]
    for name, path in hud_inputs:
        inputs[name] = file_sha(path)
        hud = read_json(path)
        if hud["version"] == "hud_supplier_export_v1":
            for packet in hud["packets"]:
                row = hud_packet(packet)
                policy.admit(row["sample"], packet["frame_contract"])
                engine.add(row)
            supplier_hints.extend(hud["boundary_hints"])
        elif hud["version"] == "hud_supplier_replay_input_v1":
            for item in hud["owner_frames"]:
                row = owner_ui(item)
                policy.admit(row["sample"], item["frame_contract"])
                engine.add(row)
            for item in hud["round_frames"]:
                row = round_readers(item)
                policy.admit(row["sample"], item["frame_contract"])
                engine.add(row)
            supplier_hints.extend(hud["boundary_hints"])
        else:
            raise ValueError("Unsupported HUD input")
    if map_path:
        inputs["map"] = file_sha(map_path)
        data = read_json(map_path)
        packets = data.get("map_observations")
        if packets is None:
            packets = [item["observation"] for item in data["rows"]]
        for packet in packets:
            row = map_packet(packet)
            policy.admit(row["sample"])
            engine.add(row)
    if hud_inputs:
        del hud
    if map_path:
        del data
    result = engine.rebuild()
    # Preserve supplier brackets separately: never silently use them as GT/engine success.
    result["supplier_boundary_hints"] = supplier_hints
    fingerprint = digest({p.name: file_sha(p) for p in Path(__file__).parent.glob("*.py")})
    map_sample_ids = {
        r["sample"]["sample_sha256"]
        for r in result["observations"]
        if r["raw"].get("schema") == "map_consumer_provisional_v1"
    }
    result["map_consumer_contexts"] = {
        frame["sample"]["sample_sha256"]: map_context(
            frame, producer_fingerprint=fingerprint, revision=str(result["revision"])
        )
        for frame in result["frames"]
        if frame["sample"]["sample_sha256"] in map_sample_ids
    }
    result["summary"] = summary(result)
    result["reproduction"] = {
        "input_sha256s": inputs,
        "policy_sha256": file_sha(policy_path),
        "code_sha256s": {p.name: file_sha(p) for p in Path(__file__).parent.glob("*.py")},
        "elapsed_sec": time.perf_counter() - started,
        "peak_RSS_MiB": peak_rss_mib(),
        "new_video_decodes": 0,
        "new_human_reviews": 0,
        "protected_media_accesses": 0,
        "source_bytes_revalidated": False,
        "raw_reader_rerun": False,
        "scope": "frozen archived native observations; not full decoder/recognizer E2E",
    }
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--hud", type=Path)
    parser.add_argument("--hud-supplement", type=Path)
    parser.add_argument("--map", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--map-plan", type=Path)
    parser.add_argument("--map-plan-output", type=Path)
    parser.add_argument("--learning-split", type=Path)
    args = parser.parse_args()
    if not args.hud and not args.map and not args.hud_supplement:
        parser.error("at least one frozen supplier input is required")
    if bool(args.map_plan) != bool(args.map_plan_output):
        parser.error("--map-plan and --map-plan-output must be supplied together")
    result = replay(
        policy_path=args.policy,
        hud_path=args.hud,
        map_path=args.map,
        hud_supplement=args.hud_supplement,
    )
    if args.learning_split:
        split = read_json(args.learning_split)
        policy = SourcePolicy(read_json(args.policy))
        result["learning_study"] = compare_temporal_learning(
            result,
            physical_matches={
                sha: record["physical_match_id"] for sha, record in policy.allowed.items()
            },
            train_groups=set(split["train_physical_matches"]),
            compare_groups=set(split["compare_physical_matches"]),
        )
    if args.map_plan:
        plan = read_json(args.map_plan)
        for row in plan["rows"]:
            frozen = freeze_native_sample(row["sample"])
            if frozen != row["sample"]:
                raise ValueError("Map plan requires a complete exact-native sample")
            key = frozen["sample_sha256"]
            context = result["map_consumer_contexts"].get(key)
            if context is None:
                raise ValueError("Map plan sample has no common exact-native state")
            row["context"] = context
        write_private(args.map_plan_output, plan)
    write_private(args.output, result)
    print(
        json.dumps(
            {"summary": result["summary"], "reproduction": result["reproduction"]},
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()

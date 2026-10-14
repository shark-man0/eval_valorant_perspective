"""Read-only source/fixture validation, distinct from Analyzer qualification.

Staging validation does not authorize formal registration or certify unreviewed
continuity/ownership. Original v3 Schema/compiler/evaluator remain authoritative.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import re
import subprocess
from fractions import Fraction
from pathlib import Path

import cv2
from jsonschema import Draft202012Validator


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def finite(value: object) -> bool:
    return type(value) in (int, float) and math.isfinite(value)


def native_policy_schema_hash(pack: Path, repository: Path) -> str:
    """Keep policy v1's dictionary contract despite unrelated additive Schema updates."""
    native_path = pack / "schemas/round_package_schema_v2.json"
    actual = digest(native_path)
    original = "7d7687ceb9c814858c878391b7b5858125bb5069a27570d8111209c51750ded5"
    current = digest(repository / "schemas/round_package_schema_v2.json")
    definition = load(native_path)["$defs"]["snapshot_source_confidence"]
    shape_hash = hashlib.sha256(json.dumps(
        definition, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    if (actual not in {original, current} or shape_hash !=
            "376e2b2946142c42deff7caba5e672c0368d6afb2b05c32415af60b167623fa1"):
        raise ValueError("unauthorized confidence policy or changed native dictionary Schema")
    return actual


def validate(pack: Path, canonical: Path) -> dict:
    pack = pack.resolve()
    manifest = load(pack / "MANIFEST.json")
    checksums = manifest["files"]
    for name, expected in checksums.items():
        path = (pack / name).resolve()
        if not path.is_relative_to(pack) or digest(path) != expected:
            raise ValueError("fixture file integrity failed")
    actual = {p.relative_to(pack).as_posix() for p in pack.rglob("*")
              if p.is_file() and "__pycache__" not in p.parts and p.name != "MANIFEST.json"}
    if actual != set(checksums):
        raise ValueError("fixture inventory changed")
    for name in ("tests/build_assertions.py",
                 "schemas/e2e_ground_truth_schema_v3.json",
                 "schemas/negative_assertions_schema_v3.json",
                 "schemas/e2e_inputs_schema_v3.json", "schemas/e2e_output_trace_schema_v1.json",
                 "ground_truth/evaluation_policy_v3.json",
                 "contracts/event_attribute_vocab_v1.json"):
        if digest(pack / name) != digest(canonical / name):
            raise ValueError("canonical framework changed")
    timeline = load(pack / "ground_truth/timeline_ground_truth_v3.json")
    policy = manifest.get("confidence_policy")
    if policy is None:
        if digest(pack / "tests/reference_evaluator.py") != digest(
                canonical / "tests/reference_evaluator.py"):
            raise ValueError("canonical evaluator changed without versioned policy")
    else:
        from scripts.e2e.match002_confidence_evaluator_v1 import POLICY_VERSION

        repository = Path(__file__).resolve().parents[2]
        expected = {
            "version": POLICY_VERSION, "fixture_id": "match_002",
            "base_evaluator_sha256": digest(canonical / "tests/reference_evaluator.py"),
            "native_schema_sha256": native_policy_schema_hash(pack, repository),
            "approval_reference": "call_4761db3ce4aa458a9a7f2fee43c9fda7:0"}
        if (timeline["fixture_id"] != "match_002" or policy != expected
                or digest(pack / "tests/reference_evaluator_v3_base.py") != expected[
                    "base_evaluator_sha256"]
                or digest(pack / "schemas/round_package_schema_v2.json") != expected[
                    "native_schema_sha256"]
                or digest(pack / "tests/reference_evaluator.py") != digest(
                    repository / "scripts/e2e/match002_confidence_evaluator_v1.py")):
            raise ValueError("unauthorized confidence policy or changed evaluator/schema")
    negatives = load(pack / "ground_truth/negative_assertions_v3.json")
    inputs = load(pack / "inputs/e2e_inputs_v3.json")
    profile = load(pack / "ground_truth/source_video_profile_v3.json")
    sidecar = load(pack / "ground_truth/frame_pts_sidecar_v3.json")
    for value, schema in ((timeline, "e2e_ground_truth_schema_v3.json"),
                          (negatives, "negative_assertions_schema_v3.json"),
                          (inputs, "e2e_inputs_schema_v3.json")):
        Draft202012Validator(load(pack / "schemas" / schema)).validate(value)
    if (manifest["source_sha256"] != profile["sha256"]
            or inputs["source_video"]["sha256"] != profile["sha256"]
            or inputs["source_video"]["filename"] != profile["source_filename"]):
        raise ValueError("source identity disagreement")
    duration, video = profile["duration_sec"], profile["video_stream"]
    if not finite(duration) or duration <= 0 or not finite(video["fps"]) or video["fps"] <= 0:
        raise ValueError("finite source duration/FPS required")
    if (any(type(video[k]) is not int or video[k] <= 0 for k in ("width", "height"))
            or Fraction(video["time_base"]) <= 0):
        raise ValueError("explicit source geometry/timebase required")
    entries = {row["evidence_path"]: row for row in sidecar["entries"]}
    images = {p.relative_to(pack).as_posix()
              for p in (pack / "assets/reference_frames").glob("*.jpg")}
    if (not images or images != set(entries) or len(entries) != len(sidecar["entries"])
            or manifest["reference_frame_count"] != len(images)
            or sidecar["frame_count_indexed"] != len(entries)):
        raise ValueError("exact image/PTS inventory required")
    for name, row in entries.items():
        frame = cv2.imread(str(pack / name))
        if frame is None or frame.shape[:2] != (video["height"], video["width"]):
            raise ValueError("source image dimensions disagree")
        requested, decoded, delta = (row[key] for key in (
            "requested_sec", "decoded_frame_pts_sec", "delta_sec"))
        if (any(not finite(t) for t in (requested, decoded, delta))
                or not 0 <= requested <= duration or not 0 <= decoded <= duration
                or abs(decoded - requested - delta) > 1e-6 or abs(delta) > 1 / video["fps"] + 1e-6
                or type(row["packet_pts_ticks"]) is not int or row["packet_pts_ticks"] < 0
                or Fraction(row["time_base"]) != Fraction(video["time_base"])
                or abs(float(row["packet_pts_ticks"] * Fraction(row["time_base"])) - decoded)
                > 1e-6):
            raise ValueError("explicit packet PTS binding invalid")
        match = re.search(r"_(\d+\.\d+)s\.jpg$", name)
        if match is None or abs(float(match[1]) - requested) > 1e-6:
            raise ValueError("evidence filename requested PTS mismatch")
    maximum_delta = max(abs(row["delta_sec"]) for row in entries.values())
    if (not finite(sidecar["max_abs_delta_sec"])
            or abs(sidecar["max_abs_delta_sec"] - maximum_delta) > 1e-6):
        raise ValueError("PTS summary differs from entries")
    ids, round_ids, numbers = set(), set(), set()
    for row in timeline["rounds"]:
        rid, number = row["round_id"], row["match_round_number_from_score"]
        if rid in round_ids or number in numbers:
            raise ValueError("duplicate Round identity/number")
        round_ids.add(rid)
        numbers.add(number)
        for group in ("point_events", "state_intervals", "ownership_intervals", "snapshots",
                      "visual_observations"):
            for annotation in row.get(group, []):
                if annotation["id"] in ids or any(p not in images for p in annotation["evidence"]):
                    raise ValueError("duplicate annotation or unbound evidence")
                ids.add(annotation["id"])
                if group == "point_events":
                    a = annotation["evidence_bracket"]["last_absent_sec"]
                    b = annotation["evidence_bracket"]["first_present_sec"]
                    if not 0 <= a <= b <= duration:
                        raise ValueError("invalid point bracket")
                    if any(not a - 1e-6 <= entries[p]["decoded_frame_pts_sec"] <= b + 1e-6
                           for p in annotation["evidence"]):
                        raise ValueError("point evidence outside approved witness bracket")
                    for jump in timeline["known_discontinuities"]:
                        if a < jump["last_pre_jump_sec"] and b > jump["first_post_jump_sec"]:
                            raise ValueError("point bracket bridges source discontinuity")
                elif group in {"state_intervals", "ownership_intervals"}:
                    a, b = annotation["core_interval"]
                    c, d = annotation["outer_interval"]
                    if not 0 <= c <= a < b <= d <= duration:
                        raise ValueError("invalid core/outer interval")
                elif not 0 <= annotation["time_sec"] <= duration:
                    raise ValueError("annotation outside source")
    for segment in timeline["continuous_segments"]:
        a, b = segment["interval"]
        if not 0 <= a < b <= duration:
            raise ValueError("invalid reviewed continuity interval")
        for discontinuity in timeline["known_discontinuities"]:
            if a < discontinuity["last_pre_jump_sec"] and b > discontinuity["first_post_jump_sec"]:
                raise ValueError("continuous segment bridges source discontinuity")
    negative_ids = [row["id"] for row in negatives["assertions"]]
    if len(set(negative_ids)) != len(negative_ids) or any(
        not 0 <= row["window"][0] <= row["window"][1] <= duration
        for row in negatives["assertions"]
    ):
        raise ValueError("invalid negative identities/windows")
    contract = load(pack / "contracts/event_source_contract_v1.json")
    actors = load(pack / "schemas/round_package_schema_v2.json")["$defs"]["event"][
        "properties"]["actor"]["enum"]
    for kind in ("round_start", "round_end"):
        if contract["events"][kind]["allowed_actors"] != ["system"]:
            raise ValueError("existing lifecycle actor contract changed")
        for actor in set(actors) - {"system"}:
            if not any(row["window"] == [0, duration]
                       and row.get("must_not_emit_matching") == {"type": kind, "actor": actor}
                       for row in negatives["assertions"]):
                raise ValueError("missing global lifecycle actor safety assertion")
    spec = importlib.util.spec_from_file_location("validated_fixture_compiler",
                                                pack / "tests/build_assertions.py")
    assert spec is not None and spec.loader is not None
    compiler = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(compiler)
    if compiler.build() != load(pack / "tests/generated/e2e_assertions_v3.json"):
        raise ValueError("generated assertions drifted")
    return {"rounds": len(round_ids), "images": len(images),
            "negative_assertions": len(negative_ids), "formal_pack_completed": False,
            "production_qualification": "not_evaluated"}


def validate_source(pack: Path, video_path: Path, ffprobe: str = "ffprobe") -> None:
    profile = load(pack / "ground_truth/source_video_profile_v3.json")
    before = digest(video_path)
    if before != profile["sha256"]:
        raise ValueError("physical source SHA mismatch")
    result = subprocess.run([ffprobe, "-v", "error", "-show_streams", "-show_format", "-of", "json",
                             str(video_path)], capture_output=True, text=True, encoding="utf-8", check=True)
    metadata = json.loads(result.stdout)
    videos = [s for s in metadata["streams"] if s["codec_type"] == "video"]
    if len(videos) != 1:
        raise ValueError("one physical video stream required")
    stream = videos[0]
    audios = [s for s in metadata["streams"] if s["codec_type"] == "audio"]
    if (abs(float(metadata["format"]["duration"]) - profile["duration_sec"]) > .002
            or (stream["width"], stream["height"]) != (
                profile["video_stream"]["width"], profile["video_stream"]["height"])
            or float(Fraction(stream["avg_frame_rate"])) != profile["video_stream"]["fps"]
            or len(audios) != profile["audio_streams"]["count"]):
        raise ValueError("physical source transport metadata mismatch")
    recorded = profile["video_stream"]
    if (stream["codec_name"] != recorded["codec"]
            or Fraction(stream["time_base"]) != Fraction(recorded["time_base"])
            or abs(float(stream["start_time"]) - recorded["start_time_sec"]) > .002):
        raise ValueError("physical video stream identity mismatch")
    for actual, expected in zip(audios, profile["audio_streams"]["streams"], strict=True):
        if any(actual.get(key) != expected.get(key)
               for key in ("index", "codec_name", "channels", "sample_rate", "channel_layout")):
            raise ValueError("physical audio transport identity mismatch")
    result = subprocess.run([ffprobe, "-v", "error", "-select_streams", "v:0", "-show_packets",
                             "-show_entries", "packet=pts", "-of", "json", str(video_path)],
                            capture_output=True, text=True, encoding="utf-8", check=True)
    ticks = sorted(p["pts"] for p in json.loads(result.stdout)["packets"])
    if (not ticks or len(set(ticks)) != len(ticks)
            or any(type(tick) is not int or tick < 0 for tick in ticks)):
        raise ValueError("unique explicit physical packet ticks required")
    for row in load(pack / "ground_truth/frame_pts_sidecar_v3.json")["entries"]:
        index = row["presentation_index"]
        if (type(index) is not int or not 0 <= index < len(ticks)
                or ticks[index] != row["packet_pts_ticks"]
                or Fraction(row["time_base"]) != Fraction(stream["time_base"])):
            raise ValueError("physical packet identity mismatch")
    if digest(video_path) != before:
        raise ValueError("physical source changed during validation")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", type=Path, required=True)
    parser.add_argument("--canonical-pack", type=Path, required=True)
    parser.add_argument("--source-video", type=Path)
    parser.add_argument("--ffprobe", default="ffprobe")
    args = parser.parse_args()
    report = validate(args.pack, args.canonical_pack)
    if args.source_video:
        validate_source(args.pack, args.source_video, args.ffprobe)
        report["physical_source_verified"] = True
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()

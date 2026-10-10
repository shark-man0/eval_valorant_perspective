"""Measure a frozen native scene-chain cohort without creating qualification.

A fresh cohort remains unreviewed: its initial crop identities are hypothetical
until independent full-context review. No timer/phase/GT enters the tracker.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import time
from fractions import Fraction
from pathlib import Path

import cv2

from scripts.diagnostics.diagnose_native_global_lifecycle import extract_window, probe_json
from scripts.diagnostics.scene_correspondence import SCALED_BACKGROUND_BOXES, _prepare, sha256
from scripts.diagnostics.scene_world_chain import ReviewedWorldChain

SHARED_SCENE_DOMAIN_CODE = Path("src/valorant_ai_coach/hud/scene_domains.py")
SHARED_SCENE_TRACKING_CODE = Path("src/valorant_ai_coach/hud/scene_tracking.py")
SHARED_SCENE_EPISODE_CODE = Path("src/valorant_ai_coach/hud/scene_episode.py")
SHARED_SCENE_REFERENCE_CODE = Path("src/valorant_ai_coach/hud/scene_references.py")
SHARED_SCENE_MATCHING_CODE = Path("src/valorant_ai_coach/hud/scene_reference_matching.py")


def verify_shared_scene_code(bindings):
    if bindings.get(str(SHARED_SCENE_DOMAIN_CODE)) != sha256(SHARED_SCENE_DOMAIN_CODE):
        raise ValueError("shared scene engine code must be frozen before decode")


def verify_shared_tracking_code(bindings):
    verify_shared_scene_code(bindings)
    if bindings.get(str(SHARED_SCENE_TRACKING_CODE)) != sha256(SHARED_SCENE_TRACKING_CODE):
        raise ValueError("shared scene tracking code must be frozen before decode")
    if bindings.get(str(SHARED_SCENE_EPISODE_CODE)) != sha256(SHARED_SCENE_EPISODE_CODE):
        raise ValueError("shared scene episode code must be frozen before decode")
    for code in (SHARED_SCENE_REFERENCE_CODE, SHARED_SCENE_MATCHING_CODE):
        if bindings.get(str(code)) != sha256(code):
            raise ValueError("shared scene acquisition code must be frozen before decode")


def verify_observer_profile(freeze, bindings):
    """Optional image-derived acquisition, with all assets pinned pre-decode."""
    profile = freeze.get("observer_profile")
    if "observer_options" in freeze:
        options = freeze["observer_options"]
        if (
            profile is None
            or not isinstance(options, dict)
            or set(options) != {"deferred_initialization"}
            or type(options["deferred_initialization"]) is not bool
        ):
            raise ValueError("explicit frozen observer deferred-initialization boolean required")
    if profile is None:
        return None
    if not isinstance(profile, str) or not profile:
        raise ValueError("explicit observer profile path required")
    verify_shared_tracking_code(bindings)
    if any(
        key in freeze for key in ("reviewed_seed_boxes_640x360", "tracker_options", "audit_options")
    ):
        raise ValueError("observer configuration comes only from the frozen observer/profile")
    path = Path(profile)
    if bindings.get(str(path)) != sha256(path):
        raise ValueError("observer profile must be frozen before decode")
    for name in (
        "observed_scene_chain.py",
        "scene_domain_bootstrap.py",
        "scene_world_bootstrap.py",
        "scene_reference_support.py",
        "scene_world_chain.py",
        "scene_correspondence.py",
        "scene_patch_search.py",
        "scene_domain_ambiguity.py",
        "scene_joint_domains.py",
    ):
        code = Path("scripts/diagnostics") / name
        if bindings.get(str(code)) != sha256(code):
            raise ValueError("observer dependency code must be frozen before decode")
    data = json.loads(path.read_bytes())
    for entry in data["references"]:
        asset = path.parent / entry["asset"]
        # Accept the declaration's portable relative spelling, not a resolved
        # machine-specific path. The loader separately validates confinement.
        if bindings.get(str(asset)) != sha256(asset):
            raise ValueError("observer reference assets must be frozen before decode")
    from scripts.diagnostics.scene_domain_bootstrap import WorldDomainBootstrap

    WorldDomainBootstrap(path)  # Validate review scope/asset pixels before decode.
    if "excluded_native_pixel_sha256" not in freeze:
        raise ValueError("observer native-pixel exposure inventory required")
    return path


def verify_bindings(bindings):
    if not bindings:
        raise ValueError("nonempty frozen file bindings required")
    for path, expected in bindings.items():
        if sha256(Path(path)) != expected:
            raise ValueError(f"frozen input changed: {path}")


def verify_ticks(ticks):
    if len(ticks) < 2 or any(b - a != 256 for a, b in zip(ticks[:-1], ticks[1:], strict=True)):
        raise ValueError("complete contiguous native 60fps coverage required")


def verify_joint_options(freeze, bindings):
    options = freeze.get("audit_options")
    if options is None:
        return False
    if options != {"joint_domains": True} or options["joint_domains"] is not True:
        raise ValueError("one frozen optional joint-domain audit required")
    verify_shared_scene_code(bindings)
    for name in ("scene_domain_ambiguity.py", "scene_joint_domains.py"):
        path = Path("scripts/diagnostics") / name
        if bindings.get(str(path)) != sha256(path):
            raise ValueError("joint audit code must be frozen before decode")
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reservation", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists() or args.output.exists():
        parser.error("new cohort directory and output required; never restart a cohort")
    started = time.perf_counter()
    freeze = json.loads(args.reservation.read_bytes())
    bindings = dict(freeze["file_sha256"])
    bindings[str(args.reservation)] = sha256(args.reservation)
    verify_bindings(bindings)
    verify_shared_tracking_code(bindings)
    joint_enabled = verify_joint_options(freeze, bindings)
    observer_profile = verify_observer_profile(freeze, bindings)
    runner = str(Path(__file__).relative_to(Path.cwd()))
    if bindings.get(runner) != sha256(Path(__file__)):
        raise ValueError("runner must be pinned before extraction")
    video = Path(freeze["source_video"])
    if bindings.get(str(video)) != freeze["source_video_sha256"]:
        raise ValueError("video must be pinned explicitly")
    if observer_profile is None:
        if freeze["reviewed_seed_boxes_640x360"] != [list(b) for b in SCALED_BACKGROUND_BOXES]:
            raise ValueError("frozen source footprints differ")
        if freeze["tracker_options"] != {
            "support_mode": "adjacent_dense_world",
            "dense_footprint": "full_valid",
            "seed_membership": "symmetric_final",
        }:
            raise ValueError("one frozen tracker configuration required")
    ffmpeg, ffprobe = shutil.which("ffmpeg"), shutil.which("ffprobe")
    if ffmpeg is None or ffprobe is None:
        raise ValueError("FFmpeg and ffprobe required")
    metadata = probe_json(
        ffprobe,
        video,
        [
            "-show_streams",
            "-show_format",
            "-show_entries",
            "stream=time_base,r_frame_rate,width,height:format=duration",
        ],
    )
    stream = metadata["streams"][0]
    if (
        stream["width"],
        stream["height"],
        Fraction(stream["r_frame_rate"]),
        Fraction(stream["time_base"]),
    ) != (1920, 1080, 60, Fraction(1, 15360)):
        raise ValueError("frozen native video contract differs")
    excluded = set(freeze["excluded_png_sha256"])
    excluded_pixels = set(freeze.get("excluded_native_pixel_sha256", []))
    args.output_dir.mkdir(parents=True)
    (args.output_dir / "predecode-bindings.json").write_text(
        json.dumps({"file_sha256": bindings, "decoded": False}, indent=2) + "\n"
    )
    windows = []
    for index, (start, end) in enumerate(freeze["windows_sec"]):
        if not 0 <= start < end <= float(metadata["format"]["duration"]):
            raise ValueError("invalid frozen interval")
        directory = args.output_dir / f"window-{index:03}"
        paths, ticks = extract_window(
            ffmpeg, ffprobe, video, directory, start, end, Fraction(1, 15360)
        )
        verify_ticks(ticks)
        rows, chain, previous_gray = [], None, None
        observer = None
        if observer_profile is not None:
            from scripts.diagnostics.observed_scene_chain import ObservedSceneChain

            observer = ObservedSceneChain(
                observer_profile, native_step_ticks=256, **freeze.get("observer_options", {})
            )
        for path, tick in zip(paths, ticks, strict=True):
            frame_hash = sha256(path)
            bindings[str(path)] = frame_hash
            source_image = cv2.imread(str(path))
            if source_image is None:
                raise ValueError("source image unreadable")
            gray = _prepare(source_image)
            pixel_hash = hashlib.sha256(source_image.tobytes()).hexdigest()
            joint = None
            if observer is not None:
                result = observer.observe(
                    source_image,
                    tick,
                    source_epoch=f"{freeze['source_video_sha256']}:window-{index:03}",
                )
            elif chain is None:
                chain = ReviewedWorldChain(
                    gray, SCALED_BACKGROUND_BOXES, **freeze["tracker_options"]
                )
                result = {"reason": "hypothetical_unreviewed_seed", "descriptive_supported": False}
            else:
                if joint_enabled:
                    from scripts.diagnostics.scene_domain_ambiguity import domain_displacement_audit
                    from scripts.diagnostics.scene_joint_domains import joint_domain_audit

                    models = []
                    result = chain.advance(gray, dense_model_sink=models)
                    if models:
                        measurements = []
                        domain_displacement_audit(
                            previous_gray,
                            gray,
                            SCALED_BACKGROUND_BOXES,
                            models[0]["model"],
                            offset_sink=measurements,
                        )
                        joint = joint_domain_audit(
                            SCALED_BACKGROUND_BOXES, models[0]["model"], measurements
                        )
                else:
                    result = chain.advance(gray)
            row = {
                "source_pts_ticks": tick,
                "time_base": "1/15360",
                "pts_sec": tick / 15360,
                "local_path": str(path),
                "frame_sha256": frame_hash,
                "source_pixel_sha256": pixel_hash,
                "known_png_overlap": frame_hash in excluded,
                "image_result": result,
            }
            if joint_enabled and observer is None:
                row["joint_domain_audit"] = joint
            if joint_enabled or observer is not None:
                row["known_native_pixel_overlap"] = pixel_hash in excluded_pixels
            rows.append(row)
            previous_gray = gray
        windows.append(
            {
                "window_sec": [start, end],
                "native_frames": len(rows),
                "adjacent_links": len(rows) - 1,
                "supported_links_descriptive": sum(
                    r["image_result"].get(
                        "descriptive_scene_link"
                        if observer is not None
                        else "descriptive_supported",
                        False,
                    )
                    for r in rows
                ),
                "known_png_overlaps": sum(r["known_png_overlap"] for r in rows),
                "review_status": "unreviewed",
                "runtime_proof_authorized": False,
                "rows": rows,
            }
        )
        if observer is not None:
            windows[-1]["initialization_reason"] = rows[0]["image_result"]["reason"]
            windows[-1]["known_native_pixel_overlaps"] = sum(
                r["known_native_pixel_overlap"] for r in rows
            )
            if "observer_options" in freeze:
                windows[-1]["pending_initialization_frames"] = sum(
                    r["image_result"]["reason"] == "image_supported_initialization_pending"
                    for r in rows
                )
                windows[-1]["observed_seed_pts_ticks"] = [
                    r["source_pts_ticks"]
                    for r in rows
                    if r["image_result"]["reason"] == "image_supported_observed_seed"
                ]
    verify_bindings(bindings)
    report = {
        "scope": (
            "Frozen native cohort; image-derived observed acquisition, "
            "unreviewed, not qualification"
            if observer_profile is not None
            else "Frozen native cohort; hypothetical seed, unreviewed, not qualification"
        ),
        "source_video_sha256": freeze["source_video_sha256"],
        "windows": windows,
        "file_sha256": bindings,
        "qualification_created": False,
        "new_runtime_events": 0,
        "canonical_current": None,
        "wall_clock_seconds": time.perf_counter() - started,
    }
    if "observer_options" in freeze:
        report["observer_options"] = freeze["observer_options"]
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(
        json.dumps(
            {
                "windows": [
                    {
                        k: w[k]
                        for k in (
                            "window_sec",
                            "native_frames",
                            "supported_links_descriptive",
                            "known_png_overlaps",
                        )
                    }
                    for w in windows
                ],
                "wall_clock_seconds": report["wall_clock_seconds"],
            }
        )
    )


if __name__ == "__main__":
    main()

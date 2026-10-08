#!/usr/bin/env python3
"""Build portable fixed-frame suites from frozen review and validation evidence.

Expected labels are copied only from validation-pack annotations or reviewed
pixel-label artifacts. The runner should consume only ``pts_sec``; expected
fields are evaluator-side data.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VIDEO_SHA = "71d58558559d6f578433ce9f234bf176f76fd5a86657dbfe3eba1e7d36136b06"
PACK = "ValorantData/valorant_e2e_validation_pack_v3/ground_truth"
EVIDENCE = "outputs/recognition-investigation"
PTS_PROBE = "outputs/pts-probe-pi.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: str):
    return json.loads((ROOT / path).read_text())


def ref(path: str, description: str) -> dict:
    return {"path": path, "sha256": sha(ROOT / path), "description": description}


def anchor_candidates() -> list[dict]:
    """Validation point evidence, without inferring primary state from filenames."""
    gt = load(f"{PACK}/timeline_ground_truth_v3.json")
    sidecar = load(f"{PACK}/frame_pts_sidecar_v3.json")
    sync = load(f"{PACK}/sync_anchors_v3.json")
    pts = {x["evidence_path"]: x["decoded_frame_pts_sec"] for x in sidecar["entries"]}
    sync_by_evidence = {x["evidence"]: x for x in sync["anchors"]}
    timeline_path = f"{PACK}/timeline_ground_truth_v3.json"
    sidecar_path = f"{PACK}/frame_pts_sidecar_v3.json"
    sync_path = f"{PACK}/sync_anchors_v3.json"
    out = []
    for rnd in gt["rounds"]:
        for event in rnd.get("point_events", []):
            for evidence in event.get("evidence", []):
                if evidence not in pts:
                    continue
                path = f"ValorantData/valorant_e2e_validation_pack_v3/{evidence}"
                label = Path(evidence).stem
                cats = ["regression_protection"]
                if event.get("type") in {"round_start", "round_end"} or "discontinuity" in label:
                    cats.append("round_boundary")
                if "buy_menu" in label:
                    cats.append("buy_menu")
                if "spectator" in label:
                    cats.append("spectator")
                if "combat_report" in label:
                    cats.append("combat_report")
                sources = [
                    ref(path, "Validation-pack reference image"),
                    ref(
                        sidecar_path,
                        "Frozen sidecar mapping reference image to exact container PTS",
                    ),
                    ref(timeline_path, "Frozen timeline context for this evidence witness"),
                ]
                sync_row = sync_by_evidence.get(evidence)
                expected_numeric = None
                if sync_row:
                    cats.append("timer_score")
                    expected_numeric = {
                        "timer": sync_row["game_timer_display"],
                        "score_player": sync_row["score_player"],
                        "score_enemy": sync_row["score_enemy"],
                    }
                    sources.append(
                        ref(
                            sync_path, "Frozen visible timer and score labels for this evidence PTS"
                        )
                    )
                out.append(
                    {
                        "pts_sec": pts[evidence],
                        "categories": sorted(set(cats)),
                        **({"expected_numeric": expected_numeric} if expected_numeric else {}),
                        "provenance": sources,
                        "note": (
                            "Frame is an evidence witness; do not infer surrounding "
                            "interval semantics."
                        ),
                    }
                )
    # Relevant frozen sync anchors not necessarily referenced by point events.
    for a in sync["anchors"]:
        evidence = a["evidence"]
        path = f"ValorantData/valorant_e2e_validation_pack_v3/{evidence}"
        if evidence not in pts or any(x["pts_sec"] == pts[evidence] for x in out):
            continue
        cats = ["timer_score", "regression_protection"]
        out.append(
            {
                "pts_sec": pts[evidence],
                "categories": cats,
                "expected_numeric": {
                    "timer": a["game_timer_display"],
                    "score_player": a["score_player"],
                    "score_enemy": a["score_enemy"],
                },
                "provenance": [
                    ref(path, "Validation-pack reference image"),
                    ref(
                        sidecar_path,
                        "Frozen sidecar mapping reference image to exact container PTS",
                    ),
                    ref(sync_path, "Frozen visible timer and score labels for this evidence PTS"),
                    ref(timeline_path, "Frozen timeline context for this evidence witness"),
                ],
                "note": "Evidence point only; not a continuous interval assertion.",
            }
        )
    return out


def reviewed_candidates() -> list[dict]:
    result = []
    camera_diag_path = f"{EVIDENCE}/native11-spectator-positive-hud-gate-diagnostics.json"
    camera_diag = load(camera_diag_path)
    external_pts = {
        round(x["time_sec"], 6)
        for x in camera_diag["observations"]
        if x.get("external_camera_transition")
    }
    sources = [
        ("native11-live-semantic-review/manifest.json", "live", "live_first_person"),
        ("native11-spectator-semantic-review/manifest.json", "spectator", "spectator_first_person"),
        ("native11-menu-semantic-review/manifest.json", "buy_menu", "buy_menu_open"),
    ]
    for filename, category, state in sources:
        p = f"{EVIDENCE}/{filename}"
        data = load(p)
        rows = data.get("observations", [])
        if category == "spectator":
            rows = [row for row in rows if round(row["time_sec"], 6) not in external_pts]
        # A small fixed spread gives temporal breadth without claiming coverage.
        for i in sorted(set([0, len(rows) // 2, len(rows) - 1])) if rows else []:
            row = rows[i]
            result.append(
                {
                    "pts_sec": row["time_sec"],
                    "categories": [category],
                    "expected_state": state,
                    "decoded_pixel_sha256": row["decoded_pixel_sha256"],
                    "provenance": [
                        ref(
                            p,
                            "Frozen native11 reviewed semantic cohort; exact PTS and "
                            "pixel identity",
                        )
                    ],
                    "note": (
                        "Previously reviewed observation; cohort is diagnostic, "
                        "not a global accuracy sample."
                    ),
                }
            )
    # Frozen HP values are numeric labels; select different values if available.
    # Reuse index records the blind pixel transcription and exact PTS/hash.
    p = f"{EVIDENCE}/production12-reviewed-novel-semantic-reuse-index.json"
    idx = load(p)
    hps = [
        x for x in idx["observations"] if x.get("blind_label", {}).get("expected_hp") is not None
    ]
    for row in (hps[0], hps[len(hps) // 2], hps[-1]) if hps else []:
        result.append(
            {
                "pts_sec": row["time_sec"],
                "categories": ["live", "hp_numeric"],
                "expected_state": "live_first_person",
                "expected_numeric": {"hp": row["blind_label"]["expected_hp"]},
                "decoded_pixel_sha256": row["decoded_pixel_sha256"],
                "provenance": [
                    ref(p, "Frozen blind pixel label and same-PTS decoded-pixel reuse index")
                ],
                "note": "HP label is for this owned frame only; no global numeric recall claim.",
            }
        )
    # Unknown taxonomy is frozen visual inspection, not state ground truth.
    p = f"{EVIDENCE}/native11-unknown-blind-review-v2/manifest.json"
    manifest = load(p)
    labels_path = f"{EVIDENCE}/native11-unknown-blind-review-v2/blind-scene-labels.json"
    labels = load(labels_path)["observations"]
    obs = manifest["observations"]
    for i in (0, 8, 20, 40, 63):
        row, label = obs[i], labels[i]
        cats = ["unknown"]
        if label.get("combat_report_visible"):
            cats.append("combat_report")
        if label.get("hp_display_visibility") == "visible":
            cats.append("hp_numeric")
        if label.get("spectator_panel_visual_status") == "present":
            cats.append("spectator")
        result.append(
            {
                "pts_sec": row["time_sec"],
                "categories": cats,
                "decoded_pixel_sha256": row["decoded_pixel_sha256"],
                "provenance": [
                    ref(p, "Fixed diagnostic unknown-scene frame selection"),
                    ref(labels_path, "Frozen blind scene/display visibility label"),
                ],
                "note": (
                    "Diagnostic scene/display label only; not a player-state or "
                    "recording-player ownership assertion."
                ),
            }
        )
    # Confirmed OCR error representatives are protected as known false positives.
    p = f"{EVIDENCE}/native07-timer-jump-review/semantic-review.json"
    data = load(p)
    wrong = [x for x in data.get("observations", []) if not x.get("correct")]
    for row in wrong[:2]:
        seconds = int(row["actual_seconds"])
        timer = f"{seconds // 60}:{seconds % 60:02d}"
        result.append(
            {
                "pts_sec": row["time_sec"],
                "categories": ["timer_score", "known_false_positive"],
                "expected_numeric": {"timer": timer},
                "decoded_pixel_sha256": row["decoded_pixel_sha256"],
                "provenance": [
                    ref(p, "Frozen blind timer OCR review confirming incorrect candidate reading")
                ],
                "note": "Frozen pixel transcription at a confirmed OCR digit-substitution failure.",
            }
        )
    # Two visually reviewed external-camera transitions guard against a
    # spectator-first-person false positive. Their subtype has no exact primary
    # state enum in this application, so these remain category-only controls.
    p = camera_diag_path
    diag = camera_diag
    sem_path = f"{EVIDENCE}/native11-spectator-semantic-review/manifest.json"
    for row in diag["observations"]:
        if not row.get("external_camera_transition"):
            continue
        result.append(
            {
                "pts_sec": row["time_sec"],
                "categories": ["known_false_positive"],
                "decoded_pixel_sha256": row["decoded_pixel_sha256"],
                "provenance": [
                    ref(
                        p,
                        "Reviewed diagnostic identifying external-camera transition "
                        "and pixel identity",
                    ),
                    ref(
                        sem_path,
                        "Frozen spectator visual-semantic cohort and exact PTS/pixel identity",
                    ),
                ],
                "note": (
                    "External-camera subtype reviewed; category-only because no matching "
                    "application primary-state enum exists."
                ),
            }
        )
    return result


def unique_frames(rows: list[dict]) -> list[dict]:
    by_pts = {}
    for row in rows:
        key = round(row["pts_sec"], 6)
        if key not in by_pts:
            by_pts[key] = row
        else:
            prior = by_pts[key]
            prior["categories"] = sorted(set(prior["categories"] + row["categories"]))
            prior["provenance"] += [x for x in row["provenance"] if x not in prior["provenance"]]
            for k in ("expected_state", "expected_numeric", "decoded_pixel_sha256"):
                if k in row and k not in prior:
                    prior[k] = row[k]
                elif k in row and k in prior and prior[k] != row[k]:
                    raise ValueError(f"conflicting reviewed facts at PTS {key}: {k}")
    return [by_pts[k] for k in sorted(by_pts)]


def build() -> tuple[dict, dict]:
    curated = unique_frames(anchor_candidates() + reviewed_candidates())
    # Bound targeted suite while retaining category witnesses across phases.
    targeted = curated[:]
    if len(targeted) > 50:
        targeted = targeted[:50]
    # Deterministic temporal representatives from targeted evidence only.
    pool = sorted(targeted, key=lambda x: x["pts_sec"])
    sampled = (
        [pool[round(i * (len(pool) - 1) / 29)] for i in range(30)] if len(pool) >= 30 else pool
    )
    probe = load(PTS_PROBE)
    actual_pts = {round(float(x["best_effort_timestamp_time"]), 6) for x in probe["frames"]}
    for frame in curated:
        if round(frame["pts_sec"], 6) not in actual_pts:
            raise ValueError(f"suite PTS is not an exact decoded source PTS: {frame['pts_sec']}")

    def suite(sid, mode, frames):
        return {
            "schema_version": 1,
            "suite_id": sid,
            "mode": mode,
            "video_id": "match_001",
            "source_sha256": VIDEO_SHA,
            "calibration_prefix": [0.036003, 0.102669, 0.169336],
            "frames": frames,
            "suite_note": (
                "Fixed deterministic evidence subset; not exhaustive event or "
                "full-video accuracy coverage."
            ),
        }

    return suite("match_001_targeted", "targeted", targeted), suite(
        "match_001_sampled", "sampled", sampled
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true", help="write the two suite manifests")
    args = parser.parse_args()
    targeted, sampled = build()
    if args.write:
        out = ROOT / "datasets/e2e_suites/match_001"
        out.mkdir(parents=True, exist_ok=True)
        for name, data in (("targeted.json", targeted), ("sampled.json", sampled)):
            (out / name).write_text(json.dumps(data, indent=2) + "\n")
    else:
        print(
            json.dumps(
                {
                    "targeted_frames": len(targeted["frames"]),
                    "sampled_frames": len(sampled["frames"]),
                    "targeted_categories": sorted(
                        {c for f in targeted["frames"] for c in f["categories"]}
                    ),
                    "sampled_categories": sorted(
                        {c for f in sampled["frames"] for c in f["categories"]}
                    ),
                },
                indent=2,
            )
        )


if __name__ == "__main__":
    main()

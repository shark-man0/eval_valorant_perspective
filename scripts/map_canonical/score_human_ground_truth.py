"""Score development Map candidates against an independent human ground truth.

The human labels come from the offline labeling page of the ground-truth package: for each
minimap frame, the centre of the recorder's own icon in minimap pixels (or "not visible" /
"cannot tell") and which site the recorder is in. The page never shows a prediction. The
answer key, kept apart from the page, holds the candidate for each frame and the event
windows the frames were sampled from.

Errors are measured in minimap pixels against the candidate's own minimap pixel and turned
into metres with the frame's Map scale, so the Map registration is not part of the
position error. Frames a human could not decide are reported, never counted as correct.
"""

from __future__ import annotations

import argparse
import json
import math
import re
from collections import Counter
from pathlib import Path
from typing import Any

SAME_MARKER_M = 2.5  # the hold radius; a click farther away is a different place
HOLD_RADIUS_M = 2.5
CHANGE_MIN_M = 5.0


def _site_of(zone_id: str | None) -> str | None:
    match = re.search(r"_([abc])_(?:site_)?plant", zone_id or "")
    return match.group(1).upper() if match else None


def _quantile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return round(ordered[min(len(ordered) - 1, int(q * len(ordered)))], 2)


def score(labels: dict[str, Any], key: dict[str, Any]) -> dict[str, Any]:
    rows = {int(row["index"]): row for row in labels["rows"]}
    frames = {int(f["id"]): f for f in key["frames"]}
    for index, row in rows.items():
        if index not in frames or row["sample_ref"] != frames[index]["sample_sha256"]:
            raise ValueError(f"label {index} does not belong to this answer key")
    human: dict[int, dict[str, Any]] = {}
    for index, frame in frames.items():
        row = rows.get(index) or {}
        click = row.get("center_roi_px") if row.get("role") == "SELF" else None
        prediction = frame.get("prediction")
        error = None
        if click and prediction and prediction.get("roi_px"):
            error = math.dist(click, prediction["roi_px"]) * frame["metres_per_roi_px"]
        human[index] = {"role": row.get("role"), "site": row.get("site_label"),
                        "click": click, "error_m": error}

    groups: dict[str, Any] = {}
    for group in ("eligible", "ineligible", "no_position"):
        members = [i for i, f in frames.items() if f["group"] == group]
        roles = Counter(human[i]["role"] or "unlabeled" for i in members)
        errors = [human[i]["error_m"] for i in members if human[i]["error_m"] is not None]
        decided = [i for i in members if human[i]["role"] in ("SELF", "NOT_VISIBLE")]
        entry: dict[str, Any] = {"frames": len(members), "human_roles": dict(roles)}
        if group == "no_position":
            entry["missed_self_visible"] = roles.get("SELF", 0)
            entry["correct_abstention"] = roles.get("NOT_VISIBLE", 0)
        else:
            same = sum(1 for i in decided if human[i]["error_m"] is not None
                       and human[i]["error_m"] <= SAME_MARKER_M)
            entry.update({
                "decided": len(decided), "same_place": same,
                "precision": round(same / len(decided), 4) if decided else None,
                "error_m_p50": _quantile(errors, 0.5), "error_m_p95": _quantile(errors, 0.95),
                "share_within_1_25_m": (round(sum(e <= 1.25 for e in errors) / len(errors), 4)
                                        if errors else None),
            })
        groups[group] = entry

    zone = Counter()
    for i, frame in frames.items():
        prediction = frame.get("prediction") or {}
        if frame["group"] != "eligible" or human[i]["site"] in (None, "UNKNOWN"):
            continue
        site = _site_of(prediction.get("zone_id"))
        if prediction.get("zone_status") == "inside" and site:
            zone["plant_zone_same_site" if human[i]["site"] == site
                 else "plant_zone_other_answer"] += 1
        else:
            zone[f"{prediction.get('zone_status')}_human_{human[i]['site'].lower()}"] += 1

    windows = []
    for window in key["windows"]:
        members = sorted((f["sec"], i) for i, f in frames.items()
                         if f.get("window") == window["window"])
        claim = window["claim"]
        result: dict[str, Any] = {"window": window["window"], "group": window["group"]}

        def click_at(sec: int, _members: list = members) -> tuple[float, float] | None:
            found = [human[i]["click"] for s, i in _members if s == sec]
            return found[0] if found else None

        def site_at(sec: int, _members: list = members) -> str | None:
            found = [human[i]["site"] for s, i in _members if s == sec]
            return found[0] if found else None

        scale = frames[members[0][1]]["metres_per_roi_px"] if members else 0.0
        if window["group"] == "hold":
            points = [click_at(s) for s in range(claim["start_sec"], claim["end_sec"] + 1)]
            seen = [p for p in points if p]
            spread = (max(math.dist(p, seen[0]) for p in seen) * scale) if seen else None
            result.update({"human_max_distance_from_first_m": round(spread, 2)
                           if spread is not None else None,
                           "confirmed": None if spread is None else spread <= HOLD_RADIUS_M})
        elif window["group"] == "change":
            a, b = click_at(claim["start_sec"]), click_at(claim["end_sec"])
            moved = math.dist(a, b) * scale if a and b else None
            result.update({"claimed_m": claim["displacement_m"],
                           "human_m": round(moved, 2) if moved is not None else None,
                           "confirmed": None if moved is None else moved >= CHANGE_MIN_M})
        else:
            before, after = site_at(claim["before_sec"]), site_at(claim["after_sec"])
            result.update({"human_before": before, "human_after": after,
                           "entry_from_outside_site": None if None in (before, after)
                           or "UNKNOWN" in (before, after)
                           else before == "OUTSIDE" and after in ("A", "B", "C")})
        windows.append(result)
    by_group: dict[str, Counter] = {}
    for result in windows:
        verdict = result.get("confirmed", result.get("entry_from_outside_site"))
        by_group.setdefault(result["group"], Counter())[str(verdict)] += 1
    return {
        "schema": "development_map_human_ground_truth_score_v1", "formal_outputs": 0,
        "package_id": labels.get("package_id"), "reviewer": "HUMAN",
        "labeled_frames": sum(1 for h in human.values() if h["role"]),
        "positions": groups, "zone_vs_human_site": dict(zone),
        "windows": windows, "window_verdicts": {k: dict(v) for k, v in by_group.items()},
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--labels", type=Path, required=True)
    parser.add_argument("--key", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = score(json.loads(args.labels.read_text(encoding="utf-8")),
                   json.loads(args.key.read_text(encoding="utf-8")))
    args.output.write_text(json.dumps(result, indent=1, ensure_ascii=False) + "\n",
                           encoding="utf-8")


if __name__ == "__main__":
    main()

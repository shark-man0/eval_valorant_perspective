"""Convert independently approved source cores to unchanged v3 assertions.

No GT is used by a production recognizer. An Omen correction must not become
Astra subtype GT. Review core endpoints are not inferred phase-transition edges.
"""
from __future__ import annotations

import argparse
import json
import math
import shutil
from pathlib import Path

from jsonschema import Draft202012Validator

from scripts.diagnostics.prepare_boundary_review import valid_id
from scripts.e2e.run_dataset_case import sha256_file
from scripts.e2e.runtime import CaseError
from valorant_ai_coach.hud.calibrate_temporal import _check_output_privacy

MECHANICS = ["shot", "movement_state", "preaim_started", "peek", "info_peek",
             "position_change", "position_hold", "engagement_start"]


def fragments(approval: dict, evidence: dict) -> tuple[list[dict], dict, list[dict]]:
    if (approval.get("kind") != "independently_approved_source_state_intervals"
            or approval.get("approved_ground_truth") is not True
            or approval.get("production_input") is not False
            or approval.get("review_provenance", {}).get("reviewer") != "human user in current chat"
            or not approval["review_provenance"].get("approval_quote")
            or evidence.get("kind") != "source_overview_not_gt"
            or evidence.get("source_hash_verified_after_extraction") is not True
            or evidence.get("recognizer_outputs_consulted") is not False
            or approval["source_video_sha256"] != evidence["source_video_sha256"]):
        raise ValueError("independent scoped source-state approval required")
    tasks = {row["review_item_id"]: row for row in evidence["review_tasks"]}
    seen, state_rows, negatives, bindings = set(), [], [], []
    for row in approval["items"]:
        try:
            identifier = valid_id(row["review_item_id"])
        except CaseError as exc:
            raise ValueError("invalid source review identifier") from exc
        core = row["core_interval"]
        if (identifier in seen or identifier not in tasks
                or len(core) != 2 or any(type(t) not in (int, float) or not math.isfinite(t)
                                       for t in core) or not 0 <= core[0] < core[1]
                or core != tasks[identifier]["review_window_sec"]):
            raise ValueError("explicit unchanged reviewed core interval required")
        seen.add(identifier)
        selected = [f for f in evidence["frames"] if core[0] <= f["source_frame_pts"] < core[1]]
        if not selected:
            raise ValueError("review core has no bound source evidence")
        times = [f["source_frame_pts"] for f in selected]
        if (len(set(times)) != len(times)
                or any(type(t) not in (int, float) or not math.isfinite(t) for t in times)):
            raise ValueError("distinct finite source frame PTS required")
        assets = []
        for frame in selected:
            name = f"assets/reference_frames/{identifier}_{frame['source_frame_pts']:.6f}s.jpg"
            assets.append(name)
            bindings.append({"evidence_path": name, "source_image": frame["image"],
                             "sha256": frame["evidence_frame_sha256"],
                             "source_frame_pts": frame["source_frame_pts"],
                             "requested_sec": frame["requested_sec"]})
        observation = row["observation"]
        if observation in {"buy_phase_banner", "remote_control_view", "spectator_first_person"}:
            state_rows.append({"round_id": row["round_id"], "state_interval": {
                "id": f"GT-{identifier}", "kind": "state_interval",
                "state_class": "flag" if observation == "buy_phase_banner" else "primary_state",
                "state": observation, "subtype": None,
                "core_interval": list(core), "outer_interval": list(core),
                "edge_policy": "Reviewed interior only; onset/offset and outside are unannotated",
                "min_core_coverage": .8 if observation == "buy_phase_banner" else .9,
                "exhaustive": False, "evidence": assets}})
        elif observation not in {"capture_paused", "match_result_overlay"}:
            raise ValueError("unsupported reviewed observation")

        def negative(suffix: str, *, _identifier: str = identifier, _core: list = core,
                     _observation: str = observation, **fields: object) -> None:
            negatives.append({"id": f"NEG-{_identifier}-{suffix}", "window": list(_core),
                              "reason": f"Independent source core: {_observation}; {suffix}",
                              **fields})

        if observation == "buy_phase_banner":
            negative("no-round-start", must_not_emit_matching={
                "type": "round_start", "actor": "system"})
            continue  # Purchase alone does not assert player ownership or a menu.
        negative("no-owned-mechanics", must_not_emit_player_event_types=list(MECHANICS))
        negative("not-live", must_not_state_match={"state": "live_first_person"})
        negative("not-self-snapshot", must_not_match_snapshot_subset={"view_owner": "self"})
        if observation == "remote_control_view" and row.get("rejected_subtype"):
            # subtype=None on the positive permits supported generic other/unknown.
            # The human correction independently rejects the mislabeled Astra case.
            negative("corrected-subtype", must_not_state_match={
                "state": "remote_control_view", "subtype": row["rejected_subtype"]})
        if observation in {"capture_paused", "match_result_overlay"}:
            negative("no-round-start", must_not_emit_matching={
                "type": "round_start", "actor": "system"})
        if observation == "capture_paused":
            negative("no-unobserved-round-end", must_not_emit_matching={
                "type": "round_end", "actor": "system"})
            negative("no-temporal-join", must_not_span_temporal_features=[
                f"{kind}.duration_sec" for kind in MECHANICS + ["status_effect", "hold_angle"]])
    if seen != set(tasks):
        raise ValueError("every reviewed task needs explicit approval or separate staging")
    return state_rows, {"version": "3.0", "assertions": negatives}, bindings


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("approval", "evidence", "canonical-pack", "output"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    _check_output_privacy(output)
    if output.exists():
        raise FileExistsError("use a new private state-fragment directory")
    paths = [args.approval, args.evidence,
             args.canonical_pack / "schemas/e2e_ground_truth_schema_v3.json",
             args.canonical_pack / "schemas/negative_assertions_schema_v3.json"]
    hashes = {p: sha256_file(p) for p in paths}
    def load(path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8"))
    approval, evidence = load(args.approval), load(args.evidence)
    if (hashes[args.evidence] != approval["review_evidence_sha256"]
            or evidence["schedule"]["plan_sha256"] != approval["review_plan_sha256"]):
        raise ValueError("approved review evidence/plan hash mismatch")
    states, negatives, bindings = fragments(approval, evidence)
    schema = load(paths[2])
    validator = Draft202012Validator({"$ref": "#/$defs/state_interval", "$defs": schema["$defs"]})
    for row in states:
        validator.validate(row["state_interval"])
    Draft202012Validator(load(paths[3])).validate(negatives)
    root = args.evidence.parent.resolve()
    for binding in bindings:
        image = (root / binding["source_image"]).resolve()
        if not image.is_relative_to(root) or sha256_file(image) != binding["sha256"]:
            raise ValueError("changed or escaped source evidence")
    output.mkdir(parents=True)
    for binding in bindings:
        destination = output / binding["evidence_path"]
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(root / binding["source_image"], destination)
        if sha256_file(destination) != binding["sha256"]:
            raise ValueError("source asset copy changed")
    if any(sha256_file(p) != digest for p, digest in hashes.items()):
        raise ValueError("inputs changed during preparation")
    if any(sha256_file(root / b["source_image"]) != b["sha256"] for b in bindings):
        raise ValueError("source images changed during copying")
    report = {"kind": "private_v3_source_state_fragments_not_complete_pack",
              "source_video_sha256": approval["source_video_sha256"],
              "states": states, "negatives": negatives, "evidence_bindings": bindings,
              "inputs": {p.name: digest for p, digest in hashes.items()},
              "production_input": False, "formal_pack_completed": False}
    (output / "state_fragments.json").write_text(
        json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(f"Prepared {len(states)} positive state cores, {len(negatives['assertions'])} negatives; "
          "no registration or subtype invention")


if __name__ == "__main__":
    main()

"""Freeze scoped human approvals in a private ledger, not a Validation Pack.

No Analyzer, GT-to-recognizer input, new approvals, inferred evidence brackets,
score-derived game-round numbers, source continuity or manifest registration.
"""
from __future__ import annotations

import argparse
import copy
import json
import math
from pathlib import Path
from urllib.parse import unquote, urlparse

from scripts.e2e.run_dataset_case import sha256_file
from valorant_ai_coach.hud.calibrate_temporal import _check_output_privacy

KINDS = {"round_start": "round_start", "round_end": "round_end",
         "purchase_display_to_active_timer": "round_start",
         "result_display_animation_onset": "round_end"}


def assemble(paths: list[Path], expected_round_count: int) -> dict:
    boundaries, contexts, inputs, seen = [], [], [], set()
    identity = None
    frozen = {}
    for path in paths:
        digest = sha256_file(path)
        frozen[path] = digest
        record = json.loads(path.read_text(encoding="utf-8"))
        provenance = record.get("review_provenance", {})
        if (record.get("approved_ground_truth") is not True
                or record.get("production_input") is not False
                or provenance.get("reviewer") != "human user in current chat"
                or not isinstance(provenance.get("scope"), str) or not provenance["scope"].strip()):
            raise ValueError("explicit scoped human approval required")
        current = (record["video_id"], record["source_video_sha256"])
        if identity is not None and identity != current:
            raise ValueError("approval source identity mismatch")
        identity = current
        inputs.append({"file": path.name, "sha256": digest})
        batch = None
        if "review_batch" in record:
            ref = record["review_batch"]
            batch_path = (path.parent / ref["file"]).resolve()
            if (not batch_path.is_relative_to(path.parent.resolve())
                    or sha256_file(batch_path) != ref["sha256"]):
                raise ValueError("approval batch binding failed")
            frozen[batch_path] = ref["sha256"]
            batch = json.loads(batch_path.read_text(encoding="utf-8"))
            if ((batch["video_id"], batch["source_video_sha256"]) != identity
                    or batch.get("production_input") is not False
                    or batch.get("recognizer_outputs_consulted") is not False):
                raise ValueError("approved batch is not independent source evidence")
        items = record.get("items", [record])
        if "approved_batch_item_indices" in record:
            indices = record["approved_batch_item_indices"]
            if batch is None or any(type(i) is not int or not 0 <= i < len(batch["items"])
                                    for i in indices) or len(set(indices)) != len(indices):
                raise ValueError("invalid approved batch indices")
            items = [batch["items"][i] for i in indices]
        for item in items:
            item = copy.deepcopy(item)
            quote = provenance.get("approval_quote", item.get("approval_quote"))
            if not isinstance(quote, str) or not quote.strip():
                raise ValueError("explicit human approval quote required for each item")
            if "batch_item_index" in item:
                index = item["batch_item_index"]
                if batch is None or type(index) is not int or not 0 <= index < len(batch["items"]):
                    raise ValueError("invalid approved batch index")
                source_item = batch["items"][index]
                if source_item["round_id"] != item["round_id"]:
                    raise ValueError("approved item round mismatch")
                item["source_review_item"] = copy.deepcopy(source_item)
            evidence_item = item.get("source_review_item", item)
            if batch is not None:
                for point in evidence_item.get("evidence", []):
                    uri = urlparse(point["image_uri"])
                    image = Path(unquote(uri.path)).resolve()
                    if (uri.scheme != "file" or uri.netloc
                            or not image.is_relative_to(path.parent.resolve())
                            or sha256_file(image) != point["evidence_frame_sha256"]):
                        raise ValueError("approved source image integrity failed")
            kind = KINDS.get(item.get("event_type", item.get("evidence_type")))
            time = item.get("event_time_sec")
            if time is None and batch is not None:
                time = item.get("candidate_time_sec")
            row = {"approval_sha256": digest, "review_provenance": copy.deepcopy(provenance),
                   "approved_record": item}
            row["review_provenance"]["approval_quote"] = quote
            if kind is None:
                contexts.append(row)
                continue
            if (type(time) not in (int, float) or not math.isfinite(time) or time < 0):
                raise ValueError("approved boundary needs a finite explicit time")
            key = (item["round_id"], kind)
            if key in seen:
                raise ValueError("duplicate or conflicting boundary approval")
            seen.add(key)
            boundaries.append({**row, "round_id": key[0], "boundary_kind": kind,
                               "approved_time_sec": time})
    rounds = {row["round_id"] for row in boundaries}
    if (type(expected_round_count) is not int or expected_round_count <= 0
            or len(rounds) != expected_round_count):
        raise ValueError("approved round coverage mismatch")
    for rid in rounds:
        pair = {row["boundary_kind"]: row["approved_time_sec"]
                for row in boundaries if row["round_id"] == rid}
        if set(pair) != {"round_start", "round_end"} or pair["round_start"] >= pair["round_end"]:
            raise ValueError("each reviewed round needs an ordered approved start/end pair")
    if any(sha256_file(path) != digest for path, digest in frozen.items()):
        raise ValueError("approval inputs changed during assembly")
    boundaries.sort(key=lambda row: row["approved_time_sec"])
    return {"kind": "private_approved_boundary_ledger_not_validation_pack",
            "video_id": identity[0], "source_video_sha256": identity[1], "inputs": inputs,
            "boundaries": boundaries, "context_observations": contexts,
            "production_input": False, "formal_pack_completed": False,
            "continuity_approval_inferred": False, "player_identity_approval_inferred": False,
            "new_evidence_brackets_inferred": False,
            "game_round_numbers_from_score_inferred": False}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--approval", type=Path, action="append", required=True)
    parser.add_argument("--expected-round-count", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    _check_output_privacy(output)
    if output.exists():
        raise FileExistsError("use a new private ledger path")
    report = assemble(args.approval, args.expected_round_count)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(f'Frozen {len(report["boundaries"])} approved markers; no pack/manifest registered')


if __name__ == "__main__":
    main()

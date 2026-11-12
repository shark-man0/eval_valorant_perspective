"""Reuse pinned HUD UI observations on a new native acquisition of the same Source.

Run by absolute path with PYTHONPATH selecting the pinned HUD supplier checkout.
This derives only an acquisition allowlist extension from a source-wide existing
human roster binding. It preserves original Profile/threshold/reference bytes.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
import subprocess
from copy import deepcopy
from pathlib import Path


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ("supplier", "acquisition", "policy", "profile", "round-input", "output"):
        p.add_argument("--" + name, type=Path, required=True)
    p.add_argument("--supplier-head", required=True)
    args = p.parse_args()
    head = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=args.supplier, text=True, encoding="utf-8"
    ).strip()
    if head != args.supplier_head or args.output.exists():
        p.error("Pinned supplier and new private output required")
    if any((path / ".git").exists() for path in args.output.resolve().parents):
        p.error("Private output must remain outside Git")
    policy, acquisition, data, profile = map(
        load, (args.policy, args.acquisition, args.round_input, args.profile)
    )
    if acquisition["policy_sha256"] != sha(args.policy):
        p.error("Acquisition admission policy mismatch")
    sample = acquisition["frames"][0]["sample"]
    binding = profile["development_recorder_view"]["binding"]
    source = next(
        r
        for r in load(policy["manifest"])["records"]
        if r["source_sha256"] == sample["source_sha256"]
    )
    if (
        sample["source_sha256"] not in policy["allowed_source_sha256s"]
        or sample["source_sha256"] in policy.get("protected_source_sha256s", [])
        or source["status"] != "accepted"
        or source["split"] != "DEVELOPMENT"
        or source["exposure"] != "DEVELOPMENT"
        or sha(policy["manifest"]) != policy["manifest_sha256"]
        or sha(policy["allocation"]) != policy["allocation_sha256"]
        or binding["source_id"] != sample["source_id"]
        or binding["source_sha256"] != sample["source_sha256"]
        or binding["physical_match_id"] != source["physical_match_id"]
        or binding["review_kind"] != "human_source_roster"
    ):
        p.error("Same accepted Source and existing source-wide recorder roster review required")
    old = deepcopy(binding["acquisition_ids"])
    epoch = sample["native_epoch"]
    binding["acquisition_ids"] = sorted(set(old + [epoch]))
    module = importlib.import_module("valorant_ai_coach.visual.development_owner_observations")
    if not Path(module.__file__).resolve().is_relative_to(args.supplier.resolve()):
        p.error("PYTHONPATH must select pinned HUD supplier")
    cv = importlib.import_module("cv2")
    cv.setNumThreads(1)
    reader = module.DevelopmentOwnerUI(profile)
    rows = []
    for entry, row in zip(acquisition["frames"], data["round_frames"], strict=True):
        sample = entry["sample"]
        if (
            sample["source_sha256"] != source["source_sha256"]
            or sample["native_epoch"] != epoch
            or sha(entry["path"]) != sample["acquired_frame_sha256"]
            or row["frame_contract"]["frame_sha256"] != sample["acquired_frame_sha256"]
        ):
            p.error("Exact source/acquisition/Round observation identity required")
        ui = reader.inspect(cv.imread(entry["path"]), sample)
        rows.append(
            {
                "frame_contract": row["frame_contract"],
                "source_id": sample["source_id"],
                "ui": ui,
                "profile": profile,
            }
        )
    data["owner_frames"] = rows
    data["owner_provenance"] = {
        "supplier_head": head,
        "parent_profile_sha256": sha(args.profile),
        "old_acquisition_ids": old,
        "new_epoch": epoch,
        "ui_fingerprint": reader.fingerprint,
        "reason": "Same accepted Source/physical match; source-wide existing human roster binding",
        "changes": "private derived acquisition allowlist only",
        "new_human_labels": 0,
        "threshold_changes": 0,
        "reference_pixel_changes": 0,
        "acquisition_sha256": sha(args.acquisition),
        "reader_cli_sha256": sha(__file__),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with os.fdopen(
        os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w", encoding="utf-8"
    ) as stream:
        json.dump(data, stream, allow_nan=False)
    print(json.dumps({"owner_observations": len(rows), "formal_outputs": 0}))


if __name__ == "__main__":
    main()

"""Admit sealed measured HUD location labels, without a second state machine.

The external image reader supplies words, boxes and runtime fingerprints. This
adapter does not run OCR, read human answers, infer life/camera, or resolve a
geometric Zone. Only temporal.game may associate a label with recorder state.
"""

from __future__ import annotations

import argparse
import hashlib
from copy import deepcopy
from pathlib import Path
from typing import Any

from .evidence import digest, freeze_native_sample, is_sha
from .game import observation
from .zone_contract import MEASUREMENT_SCHEMA, validate_measurement, validate_profile

BATCH_VERSION = "development_hud_zone_measurements_v1"
VERSION = "development_hud_zone_observations_v1"


def normalize_zone_batch(batch: dict[str, Any]) -> list[dict[str, Any]]:
    body = {k: v for k, v in batch.items() if k != "batch_sha256"}
    profile, producer, records = batch.get("profile"), batch.get("producer"), batch.get("records")
    if (
        batch.get("version") != BATCH_VERSION
        or batch.get("batch_sha256") != digest(body)
        or batch.get("qualification") != "development_only"
        or batch.get("ownership") != "UNKNOWN"
        or batch.get("formal_outputs") != 0
        or batch.get("labels_or_reviews_used") is not False
        or not isinstance(profile, dict)
        or not isinstance(producer, dict)
        or not isinstance(records, list)
        or not 1 <= len(records) <= 20_000
    ):
        raise ValueError("Sealed bounded unqualified measurement batch required")
    validate_profile(profile)
    if (
        not is_sha(producer.get("implementation_sha256"))
        or producer.get("profile_sha256") != digest(profile)
        or producer.get("model_sha256") != profile["model_sha256"]
        or producer.get("binary_sha256") != profile["binary_sha256"]
        or producer.get("language") != "jpn"
    ):
        raise ValueError("Measured implementation/profile/model/binary fingerprints required")
    implementation = {
        name: hashlib.sha256((Path(__file__).parent / name).read_bytes()).hexdigest()
        for name in ("zone_observations.py", "zone_contract.py")
    }
    fingerprint = digest(
        {"version": VERSION, "implementation": implementation, "upstream": producer}
    )
    rows, seen = [], set()
    for record in records:
        validate_measurement(record, profile)
        sample = freeze_native_sample(record["sample"])
        if sample["sample_sha256"] in seen:
            raise ValueError("One measured record per exact native sample required")
        seen.add(sample["sample_sha256"])
        rows.append(
            observation(
                sample=sample,
                producer=fingerprint,
                signals=[],
                raw={
                    "schema": MEASUREMENT_SCHEMA,
                    "profile": deepcopy(profile),
                    "measurement": deepcopy(record),
                    "upstream_producer": deepcopy(producer),
                    "producer_fingerprint": fingerprint,
                    "qualification": "development_only",
                    "ownership": "UNKNOWN",
                    "formal_outputs": 0,
                },
                context={"stream_kind": "hud_zone", "profile_fingerprint": digest(profile)},
                continuity={"decode_ok": True, "semantic": "UNKNOWN"},
            )
        )
    return rows


def main() -> None:
    from .replay import SourcePolicy, file_sha, read_json, write_private

    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("policy", "measurements", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    policy = SourcePolicy(read_json(args.policy))
    original = file_sha(args.measurements)
    data = read_json(args.measurements)
    for record in data.get("records", []):
        policy.admit(freeze_native_sample(record["sample"]))
    rows = normalize_zone_batch(data)
    if file_sha(args.measurements) != original:
        raise ValueError("Measurement batch changed during admission")
    write_private(
        args.output,
        {
            "version": VERSION,
            "observations": rows,
            "input_sha256": original,
            "policy_sha256": file_sha(args.policy),
            "new_video_decodes": 0,
            "human_labels_read": 0,
            "formal_outputs": 0,
        },
    )


if __name__ == "__main__":
    main()

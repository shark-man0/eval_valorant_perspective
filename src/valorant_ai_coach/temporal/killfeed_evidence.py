"""Development victim-column OCR observations, never qualified death events.

Two current-pixel renderings must read the exact Source-bound recorder alias.
The output is an elimination-display hypothesis. Normal death versus downing,
current actor identity and event timing are not established by OCR alone.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import math
import re
import subprocess
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from .adapters import owner_ui
from .evidence import digest
from .game import observation
from .replay import SourcePolicy, file_sha, read_json, write_private

VERSION = "development_killfeed_victim_observations_v1"


def matching_alias_words(tsv: str, alias: str) -> list[dict[str, Any]]:
    """Exact words only; neither a substring nor confidence-free text suffices."""
    matches: list[dict[str, Any]] = []
    if not re.fullmatch(r"[A-Za-z0-9_]{1,32}", alias):
        return matches
    for row in csv.DictReader(io.StringIO(tsv), delimiter="\t"):
        try:
            confidence = float(row["conf"]) / 100
            box = [int(row[k]) for k in ("left", "top", "width", "height")]
        except (KeyError, ValueError, TypeError):
            continue
        if (
            row.get("level") == "5"
            and row.get("text", "").casefold() == alias.casefold()
            and math.isfinite(confidence)
            and 0.90 <= confidence <= 1
            and min(box[:2]) >= 0
            and min(box[2:]) > 0
        ):
            matches.append({"text": row["text"], "confidence": confidence, "bbox": box})
    return matches


def observe_slot(
    crop: np.ndarray, alias: str, *, executable: Path, tessdata: Path
) -> dict[str, Any]:
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    white = 255 - cv2.inRange(crop, (170, 170, 170), (255, 255, 255))
    views = []
    for mode, pixels in (("gray", gray), ("bright_strokes", white)):
        enlarged = cv2.resize(pixels, None, fx=4, fy=4, interpolation=cv2.INTER_CUBIC)
        image = cv2.copyMakeBorder(
            enlarged,
            20,
            20,
            20,
            20,
            cv2.BORDER_CONSTANT,
            value=255 if mode == "bright_strokes" else int(np.median(enlarged)),
        )
        encoded, png = cv2.imencode(".png", image)
        if not encoded:
            raise ValueError("OCR crop could not be encoded")
        result = subprocess.run(
            [
                str(executable),
                "stdin",
                "stdout",
                "--tessdata-dir",
                str(tessdata),
                "--psm",
                "7",
                "-l",
                "eng",
                "tsv",
            ],
            input=png.tobytes(),
            capture_output=True,
            timeout=10,
            check=True,
        )
        if len(result.stdout) > 1_000_000:
            raise ValueError("Bounded OCR output required")
        tsv = result.stdout.decode("utf-8")
        views.append({"mode": mode, "raw_tsv": tsv, "matches": matching_alias_words(tsv, alias)})
    supported = all(view["matches"] for view in views)
    return {
        "status": "supported" if supported else "UNKNOWN",
        "claim": "recorder_alias_in_killfeed_victim_slot",
        "renderings": views,
        "normal_kill_confirmed": False,
        "death_kind": "UNKNOWN",
        "qualification": "development_only",
        "formal_outputs": 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in (
        "policy",
        "owner-input",
        "acquisition",
        "images",
        "profile",
        "tesseract",
        "tessdata",
        "output",
    ):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    policy = SourcePolicy(read_json(args.policy))
    data, spec = read_json(args.owner_input), read_json(args.profile)
    acquisition = read_json(args.acquisition)
    images = {}
    for entry in acquisition["frames"]:
        policy.admit(entry["sample"])
        images[entry["sample"]["sample_sha256"]] = entry
    cv2.setNumThreads(1)
    traineddata = args.tessdata / "eng.traineddata"
    fingerprints = {
        "code": file_sha(Path(__file__)),
        "profile": file_sha(args.profile),
        "owner_input": file_sha(args.owner_input),
        "acquisition": file_sha(args.acquisition),
        "executable": file_sha(args.tesseract),
        "traineddata": file_sha(traineddata),
        "opencv": cv2.__version__,
        "numpy": np.__version__,
    }
    version = subprocess.run(
        [str(args.tesseract), "--version"], capture_output=True, check=True, timeout=10
    ).stdout.decode("utf-8")
    producer = digest({"version": VERSION, **fingerprints})
    if spec.get("slot_kind") != "killfeed_victim_name" or not spec.get("victim_rois_px"):
        raise ValueError("Explicit development victim-column geometry required")
    rois = spec["victim_rois_px"]
    if not isinstance(rois, list) or not 1 <= len(rois) <= 6:
        raise ValueError("Bounded victim-column ROIs required")
    records = []
    for item in data["owner_frames"]:
        parent = owner_ui(item)
        sample, frame = parent["sample"], item["frame_contract"]
        policy.admit(sample, frame)
        binding = item["profile"].get("development_recorder_view", {}).get("binding", {})
        if (
            binding.get("review_kind") != "human_source_roster"
            or binding != spec.get("source_binding")
            or binding.get("source_id") != sample["source_id"]
            or binding.get("source_sha256") != sample["source_sha256"]
            or binding.get("physical_match_id") != frame["leakage_group_id"]
            or sample["native_epoch"] not in binding.get("acquisition_ids", [])
            or spec.get("frame_size_px") != sample["frame_size_px"]
        ):
            raise ValueError("Exact Source-bound recorder roster and frame geometry required")
        # The file name is resolved from the frozen native frame contract, not a
        # near-time image from another acquisition.
        slots = []
        if item["ui"].get("spectator_ui") is True:
            entry = images.get(sample["sample_sha256"])
            if entry is None or entry["sample"] != sample:
                raise ValueError("One exact acquired image required")
            image_path = args.images / Path(entry["path"]).name
            if (
                not image_path.resolve().is_relative_to(args.images.resolve())
                or file_sha(image_path) != sample["acquired_frame_sha256"]
            ):
                raise ValueError("Bound acquired image bytes required")
            image = cv2.imread(str(image_path))
            if image is None or [image.shape[1], image.shape[0]] != sample["frame_size_px"]:
                raise ValueError("Native image dimensions differ")
            if hashlib.sha256(image.tobytes()).hexdigest() != sample["native_pixel_sha256"]:
                raise ValueError("Native pixels differ")
            for roi in rois:
                if (
                    not isinstance(roi, list)
                    or len(roi) != 4
                    or any(type(n) is not int for n in roi)
                ):
                    raise ValueError("Integer native victim ROI required")
                left, top, right, bottom = roi
                if not (
                    0 <= left < right <= image.shape[1]
                    and 0 <= top < bottom <= image.shape[0]
                    and right - left <= 512
                    and bottom - top <= 128
                ):
                    raise ValueError("Victim ROI outside current native pixels")
                result = observe_slot(
                    image[top:bottom, left:right],
                    binding["recorder_alias"],
                    executable=args.tesseract,
                    tessdata=args.tessdata,
                )
                slots.append({"roi_px": roi, **result})
        signals = (
            ["recorder_elimination_display"]
            if any(slot["status"] == "supported" for slot in slots)
            else []
        )
        row = observation(
            sample=sample,
            producer=producer,
            signals=signals,
            raw={
                "schema": VERSION,
                "slots": slots,
                "normal_kill_confirmed": False,
                "not_attempted_without_spectator": not slots,
                "formal_outputs": 0,
            },
            context={"stream_kind": "hud_killfeed", "profile_fingerprint": fingerprints["profile"]},
        )
        records.append({"observation": row, "frame_contract": frame})
    if (
        file_sha(args.owner_input) != fingerprints["owner_input"]
        or file_sha(args.profile) != fingerprints["profile"]
        or file_sha(args.acquisition) != fingerprints["acquisition"]
        or file_sha(args.tesseract) != fingerprints["executable"]
        or file_sha(traineddata) != fingerprints["traineddata"]
    ):
        raise ValueError("OCR input or implementation changed")
    write_private(
        args.output,
        {
            "version": VERSION,
            "records": records,
            "fingerprints": fingerprints,
            "tesseract_version": version,
            "new_human_labels": 0,
            "formal_outputs": 0,
        },
    )


if __name__ == "__main__":
    main()

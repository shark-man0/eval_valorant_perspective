"""Build the private spike-header template from DEVELOPMENT crop archives.

Riot publishes no stand-alone image of the spike header in the weapon
inventory, so the template is the average of confident matches in our own
DEVELOPMENT recordings, seeded by one sample a person has checked by eye. The
result is private (it is derived from game footage): it goes to the private
cache next to the official reference images and is never committed.

    PYTHONPATH=src python3 scripts/knowledge/build_spike_template.py \
        --seed fm1_1:335 --cache ~/valorant_knowledge_cache CROPS/*.zip

Only the emblem and the right edge of the box are kept, so the template does not
depend on the client language or key bindings.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np

from valorant_ai_coach.knowledge.spike_carrier import (
    ARCHIVE_SCALE,
    MANIFEST_NAME,
    NEGATIVE_NAME,
    SEARCH_WINDOW,
    TEMPLATE_NAME,
)
from valorant_ai_coach.knowledge.template_lineage import train_sources
from valorant_ai_coach.learning.archives import CropArchive
from valorant_ai_coach.recordings.catalog import RecordingCatalog

# Emblem + right border inside the archive-scale inventory crop (x0, y0, x1, y1).
SEED_BOX = (64, 0, 104, 26)
REFINE_MIN_SCORE = 0.9
# Windows that half-match the spike emblem are, on the TRAIN matches, the
# round-countdown hourglass panel; their average is the negative template.
NEGATIVE_RANGE = (0.6, 0.7)


def gray(crop: np.ndarray) -> np.ndarray:
    return crop if crop.ndim == 2 else cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)


def best_match(crop: np.ndarray, template: np.ndarray) -> tuple[float, int, int]:
    x0, y0, x1, y1 = SEARCH_WINDOW
    window = gray(crop)[y0:y1, x0:x1].astype(np.float32)
    result = cv2.matchTemplate(window, template, cv2.TM_CCOEFF_NORMED)
    _, score, _, loc = cv2.minMaxLoc(result)
    return float(score), int(loc[0]) + x0, int(loc[1]) + y0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", required=True, help="VIDEO_ID:SECONDS of a checked spike header")
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--rounds", type=int, default=2)
    parser.add_argument("--registry", type=Path, required=True,
                        help="continual-learning dataset_registry.json; only TRAIN is accepted")
    parser.add_argument("--catalog", type=Path, required=True,
                        help="recording catalog root (journal.jsonl); learning split must be TRAIN")
    parser.add_argument("--video-hashes", type=Path,
                        help="video_id -> file_name, size_bytes, sha256 of the original recording")
    parser.add_argument("archives", type=Path, nargs="+")
    args = parser.parse_args()
    hashes = (json.loads(args.video_hashes.read_text(encoding="utf-8"))
              if args.video_hashes else None)
    _, lineage = train_sources(args.registry, args.archives,
                               catalog=RecordingCatalog(args.catalog), video_hashes=hashes)
    seed_video, seed_sec = args.seed.split(":")
    archives = {path.stem: path for path in args.archives}
    seed_archive = CropArchive(archives[seed_video])
    seed_crop = seed_archive.crop("weapon_inventory", float(seed_sec))
    seed_archive.close()
    if seed_crop is None:
        raise SystemExit(f"no weapon_inventory crop at {args.seed}")
    x0, y0, x1, y1 = SEED_BOX
    template = gray(seed_crop)[y0:y1, x0:x1].astype(np.float32)
    height, width = template.shape
    used = 0
    for _ in range(args.rounds):
        stack = []
        for path in sorted(archives.values()):
            crops = CropArchive(path)
            for sample in crops.iter_samples(("weapon_inventory",)):
                crop = sample.crops["weapon_inventory"]
                score, x, y = best_match(crop, template)
                if score >= REFINE_MIN_SCORE:
                    patch = gray(crop)[y:y + height, x:x + width]
                    if patch.shape == template.shape:
                        stack.append(patch.astype(np.float32))
            crops.close()
        if not stack:
            raise SystemExit("seed matched nothing; check the seed sample")
        template = np.mean(stack, axis=0).astype(np.float32)
        used = len(stack)
    negatives = []
    for path in sorted(archives.values()):
        crops = CropArchive(path)
        for sample in crops.iter_samples(("weapon_inventory",)):
            crop = sample.crops["weapon_inventory"]
            score, x, y = best_match(crop, template)
            if NEGATIVE_RANGE[0] <= score < NEGATIVE_RANGE[1]:
                patch = gray(crop)[y:y + height, x:x + width]
                if patch.shape == template.shape:
                    negatives.append(patch.astype(np.float32))
        crops.close()
    if not negatives:
        raise SystemExit("no look-alike windows for the negative template")
    negative = np.mean(negatives, axis=0)
    out = args.cache / "hud_templates"
    out.mkdir(parents=True, exist_ok=True)
    ok, encoded = cv2.imencode(".png", np.clip(template, 0, 255).astype(np.uint8))
    if not ok:
        raise SystemExit("PNG encoding failed")
    data = encoded.tobytes()
    (out / TEMPLATE_NAME).write_bytes(data)
    ok, encoded_negative = cv2.imencode(".png", np.clip(negative, 0, 255).astype(np.uint8))
    if not ok:
        raise SystemExit("PNG encoding failed")
    negative_data = encoded_negative.tobytes()
    (out / NEGATIVE_NAME).write_bytes(negative_data)
    manifest = {
        "name": TEMPLATE_NAME,
        "sha256": hashlib.sha256(data).hexdigest(),
        "scale": ARCHIVE_SCALE,
        "seed": args.seed,
        "averaged_samples": used,
        "negative_sha256": hashlib.sha256(negative_data).hexdigest(),
        "negative_samples": len(negatives),
        "archives": len(archives),
        "lineage": lineage,
        "origin": "DEVELOPMENT recordings (private; derived from game footage)",
    }
    (out / MANIFEST_NAME).write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    print(json.dumps({k: manifest[k] for k in ("sha256", "averaged_samples", "archives")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

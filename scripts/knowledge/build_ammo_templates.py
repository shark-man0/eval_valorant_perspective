"""Build the private magazine-digit templates from TRAIN crop archives.

Same procedure as ``build_score_templates.py``: development-time labels from
the Tesseract CLI (a crop is used only when Tesseract returns exactly one digit
per segmented glyph), per-digit medians, TRAIN-only sources enforced against
the dataset registry, lineage in the manifest. The app never calls Tesseract.

    PYTHONPATH=src python3 scripts/knowledge/build_ammo_templates.py \
        --cache CACHE --registry dataset_registry.json --video-hashes HASHES CROPS/*.zip
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

import cv2
import numpy as np

from valorant_ai_coach.knowledge.ammo_reader import (
    GLYPH_SIZE,
    MANIFEST_NAME,
    TEMPLATE_NAME,
    magazine_glyphs,
    normalise,
)
from valorant_ai_coach.knowledge.template_lineage import train_sources
from valorant_ai_coach.learning.archives import CropArchive


def tesseract_digits(gray_window: np.ndarray, workdir: Path) -> str:
    big = 255 - cv2.resize(gray_window, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
    path = workdir / "w.png"
    cv2.imwrite(str(path), big)
    result = subprocess.run(
        ["tesseract", str(path), "-", "--psm", "7", "-c", "tessedit_char_whitelist=0123456789"],
        capture_output=True, text=True, encoding="utf-8", check=False)
    return result.stdout.strip()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--stride", type=int, default=3, help="use every Nth sample")
    parser.add_argument("--registry", type=Path, required=True,
                        help="continual-learning dataset_registry.json; only TRAIN is accepted")
    parser.add_argument("--video-hashes", type=Path)
    parser.add_argument("archives", type=Path, nargs="+")
    args = parser.parse_args()
    if shutil.which("tesseract") is None:
        raise SystemExit("tesseract CLI not found (development-time dependency)")
    hashes = (json.loads(args.video_hashes.read_text(encoding="utf-8"))
              if args.video_hashes else None)
    _, lineage = train_sources(args.registry, args.archives, video_hashes=hashes)
    stacks: dict[int, list[np.ndarray]] = {d: [] for d in range(10)}
    crops_seen = labelled = 0
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        for path in sorted(args.archives):
            archive = CropArchive(path)
            for index, sample in enumerate(archive.iter_samples(("ammo",))):
                if index % args.stride or "ammo" not in sample.crops:
                    continue
                gray, boxes = magazine_glyphs(sample.crops["ammo"])
                if not 1 <= len(boxes) <= 2:
                    continue
                crops_seen += 1
                text = tesseract_digits(gray, work)
                if len(text) != len(boxes) or not text.isdigit():
                    continue
                labelled += 1
                for char, box in zip(text, boxes, strict=True):
                    stacks[int(char)].append(normalise(gray, box))
            archive.close()
    missing = [d for d, stack in stacks.items() if len(stack) < 5]
    if missing:
        raise SystemExit(f"too few labelled glyphs for digits {missing}")
    digits = np.stack([np.median(np.stack(stacks[d]), axis=0)
                       for d in range(10)]).astype(np.float32)
    assert digits.shape == (10, GLYPH_SIZE[1], GLYPH_SIZE[0])
    out = args.cache / "hud_templates"
    out.mkdir(parents=True, exist_ok=True)
    buffer = io.BytesIO()
    np.savez(buffer, digits=digits)
    data = buffer.getvalue()
    (out / TEMPLATE_NAME).write_bytes(data)
    manifest = {
        "name": TEMPLATE_NAME,
        "sha256": hashlib.sha256(data).hexdigest(),
        "labelled_crops": labelled,
        "segmented_crops": crops_seen,
        "glyphs_per_digit": {str(d): len(stacks[d]) for d in range(10)},
        "archives": len(args.archives),
        "stride": args.stride,
        "lineage": lineage,
        "origin": ("DEVELOPMENT recordings, labelled by Tesseract "
                   "(private; derived from game footage)"),
    }
    (out / MANIFEST_NAME).write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    print(json.dumps(manifest["glyphs_per_digit"]), labelled, crops_seen)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

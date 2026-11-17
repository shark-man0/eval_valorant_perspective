"""Build the private score-digit templates from DEVELOPMENT crop archives.

Development-time only: glyphs are labelled with the Tesseract CLI (whitelist
0-9, a window is used only when Tesseract returns exactly one digit per
segmented glyph), and the labelled glyphs are averaged per digit. The app never
calls Tesseract; it uses the averaged templates. The templates are derived from
game footage, so they go to the private cache and are never committed.

    PYTHONPATH=src python3 scripts/knowledge/build_score_templates.py \
        --cache ~/valorant_knowledge_cache --stride 6 CROPS/*.zip
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import shutil
import subprocess
import tempfile
from collections import Counter
from pathlib import Path

import cv2
import numpy as np

from valorant_ai_coach.knowledge.score_reader import (
    GLYPH_SIZE,
    MANIFEST_NAME,
    SCORE_WINDOWS,
    TEMPLATE_NAME,
    glyph_boxes,
    normalise_glyph,
)
from valorant_ai_coach.learning.archives import CropArchive


def tesseract_digits(window: np.ndarray, workdir: Path) -> str:
    gray = cv2.cvtColor(window, cv2.COLOR_BGR2GRAY)
    big = 255 - cv2.resize(gray, None, fx=6, fy=6, interpolation=cv2.INTER_CUBIC)
    path = workdir / "w.png"
    cv2.imwrite(str(path), big)
    result = subprocess.run(
        ["tesseract", str(path), "-", "--psm", "7", "-c", "tessedit_char_whitelist=0123456789"],
        capture_output=True, text=True, encoding="utf-8", check=False)
    return result.stdout.strip()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--stride", type=int, default=6, help="use every Nth sample")
    parser.add_argument("archives", type=Path, nargs="+")
    args = parser.parse_args()
    if shutil.which("tesseract") is None:
        raise SystemExit("tesseract CLI not found (development-time dependency)")
    stacks: dict[int, list[np.ndarray]] = {d: [] for d in range(10)}
    windows = labelled = 0
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        for path in sorted(args.archives):
            crops = CropArchive(path)
            for index, sample in enumerate(crops.iter_samples(("top_bar",))):
                if index % args.stride:
                    continue
                bar = sample.crops["top_bar"]
                for x0, y0, x1, y1 in SCORE_WINDOWS.values():
                    window = bar[y0:y1, x0:x1]
                    gray, boxes = glyph_boxes(window)
                    if not 1 <= len(boxes) <= 2:
                        continue
                    windows += 1
                    text = tesseract_digits(window, work)
                    if len(text) != len(boxes) or not text.isdigit():
                        continue
                    labelled += 1
                    for char, box in zip(text, boxes, strict=True):
                        stacks[int(char)].append(normalise_glyph(gray, box))
            crops.close()
    missing = [d for d, stack in stacks.items() if len(stack) < 5]
    if missing:
        raise SystemExit(f"too few labelled glyphs for digits {missing}")
    # Median rejects the minority of mislabelled glyphs.
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
        "labelled_windows": labelled,
        "segmented_windows": windows,
        "glyphs_per_digit": {str(d): len(stacks[d]) for d in range(10)},
        "archives": len(args.archives),
        "stride": args.stride,
        "origin": ("DEVELOPMENT recordings, labelled by Tesseract "
                   "(private; derived from game footage)"),
    }
    (out / MANIFEST_NAME).write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    print(json.dumps(manifest["glyphs_per_digit"]), labelled, windows,
          Counter(len(s) > 0 for s in stacks.values()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

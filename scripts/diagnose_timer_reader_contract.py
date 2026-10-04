"""Synthetic-only audit of the existing digit-template timer contract.

This module is diagnostic-only. Temporary glyph assets are removed after the
actual runtime reader is exercised; output contains no recording/frame data.
"""

from __future__ import annotations

import argparse
import hashlib
import inspect
import json
from pathlib import Path
from tempfile import TemporaryDirectory

import cv2
import numpy as np

from valorant_ai_coach.hud.readers import ReaderResult
from valorant_ai_coach.hud.templates import HudTemplateProfile, SegmentedDigitsReader


class NoOcr:
    def read(self, image: np.ndarray, roi: np.ndarray) -> ReaderResult[str]:
        return ReaderResult(None, 0.0, ("diagnostic_no_ocr",))


def _glyph(character: str) -> np.ndarray:
    image = np.zeros((60, 120, 3), dtype=np.uint8)
    cv2.putText(image, character, (10, 44), cv2.FONT_HERSHEY_SIMPLEX,
                1, (255, 255, 255), 2, cv2.LINE_AA)
    gray = cv2.resize(cv2.cvtColor(image, cv2.COLOR_BGR2GRAY), None,
                      fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    _, mask = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    count, _, stats, _ = cv2.connectedComponentsWithStats(mask)
    components = [s for s in stats[1:count] if s[3] >= 26 and s[4] >= 4]
    if len(components) != 1:
        raise ValueError("synthetic digit must have one complete component")
    x, y, width, height, _ = map(int, components[0])
    return mask[y:y + height, x:x + width]


def _render(separator: str, *, dot: bool = False, clip: int = 0) -> np.ndarray:
    image = np.zeros((60, 260, 3), dtype=np.uint8)
    layout = [("1", 8), ("1", 72), ("4", 114)]
    layout += [(character, 40 + index * 13) for index, character in enumerate(separator)]
    for character, x in layout:
        cv2.putText(image, character, (x, 44), cv2.FONT_HERSHEY_SIMPLEX,
                    1, (255, 255, 255), 2, cv2.LINE_AA)
    if dot:
        cv2.circle(image, (169, 42), 2, (255, 255, 255), -1)
    return image[:, clip:].copy()


def audit() -> dict[str, object]:
    cases = []
    with TemporaryDirectory(prefix="timer_contract_") as directory:
        root = Path(directory)
        profile_path = root / "profile.json"
        profile_path.write_text('{"schema_version":"1.0"}', encoding="utf-8")
        for digit in "0123456789":
            if not cv2.imwrite(str(root / f"{digit}.png"), _glyph(digit)):
                raise OSError("failed to write temporary glyph")
        profile = HudTemplateProfile.load(profile_path)
        for name, separator, alphabet, dot, clip in (
            ("complete_timer", ":", "0123456789", False, 0),
            ("missing_separator", "", "0123456789", False, 0),
            ("duplicate_separator", "::", "0123456789", False, 0),
            ("extra_dot", ":", "0123456789", True, 0),
            ("partial_alphabet", ":", "14", False, 0),
            ("clipped_ink_at_roi_edge", ":", "0123456789", False, 14),
        ):
            reader = SegmentedDigitsReader(
                profile,
                {"format": "timer_mmss", "glyph_threshold": 0.90,
                 "templates": {digit: f"{digit}.png" for digit in alphabet}},
                fallback=NoOcr(),
            )
            image = _render(separator, dot=dot, clip=clip)
            result = reader.read(image, image)
            cases.append({"case": name, "value": result.value,
                          "confidence": result.confidence,
                          "alphabet_size": len(alphabet)})
    return {
        "scope": "synthetic contract characterization; not video accuracy or production input",
        "threshold": 0.90,
        "reader_source_sha256": hashlib.sha256(
            inspect.getsource(SegmentedDigitsReader).encode("utf-8")
        ).hexdigest(),
        "cases": cases,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.write_text(json.dumps(audit(), indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

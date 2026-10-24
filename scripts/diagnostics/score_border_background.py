"""Offline row background alternatives; never installed by production.

Estimate bright scene support from the four outer columns on each side. Unlike
opening, this does not estimate background from the digit's interior strokes.
Keep original intensities only where both sides support foreground contrast.
The original native-border method is also an explicit rejected-read recovery
alternative. No class preference, expected label, timestamp or temporal filling.
"""
from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any, cast

import cv2
import numpy as np

from scripts.e2e.run_dataset_case import sha256_file
from valorant_ai_coach.hud.readers import ReaderResult
from valorant_ai_coach.hud.score_glyphs import StrictScoreGlyphReader
from valorant_ai_coach.hud.templates import HudTemplateProfile, SubregionReader
from valorant_ai_coach.hud.timer_glyphs import ImageU8


def separate_background(gray: ImageU8) -> ImageU8:
    """Fixed native-pixel support, not a promise that borders are background."""
    left = np.median(gray[:, :4], axis=1)
    right = np.median(gray[:, -4:], axis=1)
    background = np.maximum(left, right)[:, None]
    return np.where(gray.astype(np.float32) - background >= 12, gray, 0).astype(np.uint8)


class BorderBackgroundScoreReader:
    def __init__(self, reader: StrictScoreGlyphReader) -> None:
        if (reader.foreground_preprocessing != 'white200_v1'
                or reader.comparison_preprocessing != 'gaussian3x3_v1'):
            raise ValueError('frozen white200/Gaussian score reader required')
        self.reader = reader

    def read(self, image: ImageU8, roi: ImageU8) -> ReaderResult[str]:
        if (not isinstance(roi, np.ndarray) or roi.dtype != np.uint8 or not roi.size
                or roi.ndim not in (2, 3) or min(roi.shape[:2]) < 8
                or roi.ndim == 3 and roi.shape[2] != 3):
            return ReaderResult(None, 0.0, ('diagnostic_score_invalid_border_support',))
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY) if roi.ndim == 3 else roi
        return self.reader.read(image, separate_background(cast(ImageU8, gray)))


class RejectedScoreBackgroundReader:
    """Explicit offline recovery after rejection; never choose a higher score.

    The caller retains the configured SubregionReader around this reader. Both
    stages share all ten digit assets and the original threshold/margin. Moving
    the fixed background separation before enlargement is the only alternative.
    A blank/occluded glyph is still unread, never filled from adjacent frames.
    """

    def __init__(self, reader: StrictScoreGlyphReader) -> None:
        if (reader.foreground_preprocessing != 'white200_rowcontrast_v1'
                or reader.comparison_preprocessing != 'gaussian3x3_v1'
                or reader.THRESHOLD != .90 or reader.CLASS_MARGIN != .04):
            raise ValueError('configured rowcontrast/Gaussian Score baseline required')
        self.reader = reader
        self.alternative = BorderBackgroundScoreReader(StrictScoreGlyphReader(
            reader.templates, comparison_preprocessing='gaussian3x3_v1',
            foreground_preprocessing='white200_v1',
        ))

    def read(self, image: ImageU8, roi: ImageU8) -> ReaderResult[str]:
        value = self.reader.read(image, roi)
        if value.value is not None:
            return value
        recovered = self.alternative.read(image, roi)
        return ReaderResult(recovered.value, recovered.confidence,
                            (*recovered.sources, 'offline_rejected_native_score_background_v1'))


def score_readers(
    path: Path, *, foreground: str | None = None, background_fallback: bool = False,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Preflight existing readers; any alternate mode must be explicit and bound.

    An unsupported historical experiment name never silently aliases a supported
    one. The parent bytes, templates, confidence and class margin stay unchanged.
    """
    if type(background_fallback) is not bool:
        raise ValueError('explicit boolean Score background option required')
    profile_bytes = path.read_bytes()
    parent_sha256 = hashlib.sha256(profile_bytes).hexdigest()
    raw = json.loads(profile_bytes)
    candidate = deepcopy(raw)
    roles = ("ally_score", "enemy_score")
    assets = {}
    for role in roles:
        spec = candidate.get("readers", {}).get(role, {})
        if spec.get("kind") != "strict_score_glyphs":
            raise ValueError("explicit strict Score reader required")
        if foreground is not None:
            spec["foreground_preprocessing"] = foreground
    profile = HudTemplateProfile(path, candidate)
    all_readers = profile.build_readers()
    selected: dict[str, Any] = {}
    for role in roles:
        reader = all_readers.get(role)
        inner = reader.reader if isinstance(reader, SubregionReader) else reader
        if not isinstance(inner, StrictScoreGlyphReader):
            raise ValueError("Score reader unavailable: " + "; ".join(profile.reader_diagnostics))
        if background_fallback:
            alternative = RejectedScoreBackgroundReader(inner)
            selected[role] = (SubregionReader(alternative, reader.bounds)
                              if isinstance(reader, SubregionReader) else alternative)
        else:
            selected[role] = reader
        for name in candidate["readers"][role]["templates"].values():
            asset = profile.resolve_asset(name)
            assets[str(asset)] = sha256_file(asset)
    if sha256_file(path) != parent_sha256:
        raise ValueError("parent profile changed during reader preflight")
    binding: dict[str, Any] = {"parent_profile_sha256": parent_sha256,
                      "explicit_foreground": foreground, "asset_sha256": assets,
                      "production_changed": False, "formal_events": []}
    if background_fallback:
        binding['rejected_native_background'] = True
    return selected, binding

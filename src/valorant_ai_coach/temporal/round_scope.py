"""Pixel-only reuse of the already submitted offline Round component gates.

This authorizes only development Round measurements. It cannot authorize full
HUD geometry, recorder identity, ownership, or a Production event.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Any, cast

import cv2
import numpy as np
from numpy.typing import NDArray

from scripts.diagnostics.diagnose_result_text import accepted_result, load_method, text_region
from scripts.diagnostics.hud_scope_structure import outline_mask, top_scope
from valorant_ai_coach.hud.layout import HudLayout
from valorant_ai_coach.hud.templates import HudTemplateProfile, TesseractTextReader

from .replay import file_sha, read_json


class PixelRoundScope:
    def __init__(self, bank_path: Path, method_path: Path) -> None:
        bank = read_json(bank_path)
        self.references: list[tuple[NDArray[np.uint8], NDArray[np.uint8]]] = []
        assets = {}
        for item in bank["references"]["top_match_bar"]:
            profile = HudTemplateProfile(
                bank_path.parent / "structural_references/unused.json", item["profile"]
            )
            spec = item["profile"]["anchors"]["top_match_bar"]
            images = []
            for name in ("template", "mask"):
                path = profile.resolve_asset(spec[name])
                assets[str(path)] = file_sha(path)
                image = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
                if image is None:
                    raise ValueError("Existing Round structure asset unavailable")
                images.append(cast(NDArray[np.uint8], image))
            self.references.append((images[0], outline_mask(images[0], images[1])))
        if not self.references:
            raise ValueError("Nonempty frozen Round reference bank required")
        self.method = load_method(method_path)
        self.text = TesseractTextReader(language=self.method["language"], psm=self.method["psm"])
        runtime: dict[str, Any] = {"binary_sha256": None, "language_models": {}}
        if self.text.executable is not None:
            runtime["binary_sha256"] = file_sha(Path(self.text.executable))
            query = subprocess.run(
                [self.text.executable, "--list-langs"], capture_output=True, check=True, timeout=5
            )
            header = query.stdout.decode("utf-8", errors="strict").splitlines()[0]
            match = re.search(r'"([^"]+)"', header)
            if match is None:
                raise ValueError("Cannot freeze effective OCR model directory")
            models = Path(match.group(1))
            runtime["language_models"] = {
                lang: file_sha(models / f"{lang}.traineddata")
                for lang in self.method["language"].split("+")
            }
        diagnostic = Path(__file__).parents[3] / "scripts/diagnostics"
        self.bindings = {
            "bank": file_sha(bank_path),
            "method": file_sha(method_path),
            "assets": assets,
            "OCR_runtime": runtime,
            "diagnostic_code": {
                n: file_sha(diagnostic / n)
                for n in (
                    "hud_scope_structure.py",
                    "geometry_edge_similarity.py",
                    "diagnose_hud_transfer.py",
                    "diagnose_result_text.py",
                    "result_title_region.py",
                )
            },
        }

    def measure(self, image: NDArray[np.uint8], layout: HudLayout) -> dict[str, Any]:
        size = (image.shape[1], image.shape[0])
        scopes = []
        if size == layout.reference_resolution:
            left, top, right, bottom = layout.normalized_roi("top_match_bar").pixel_bounds(*size)
            scopes = [
                top_scope(template, mask, image[top:bottom, left:right])
                for template, mask in self.references
            ]
        supported = any(s["status"] == "TOP_STRUCTURE_SUPPORTED" for s in scopes)
        crop, region = text_region(image, layout, self.method)
        value = self.text.read(image, crop) if crop is not None else None
        return {
            "top_structure_supported": supported,
            "scopes": scopes,
            "result": {
                "value": None if value is None else accepted_result(value.value, value.confidence),
                "raw_text": None if value is None else value.value,
                "confidence": 0.0 if value is None else value.confidence,
                "region": region,
            },
            "global_geometry_authorized": False,
            "ownership_authorized": False,
            "qualified": False,
        }

"""Bounded offline Score proposals. Raw rankings are never accepted events.

Keep all ten digit competitors and segmentation alternatives past early Reader
rejection. Never change the production Reader or infer an unobserved digit.
"""

from __future__ import annotations

from itertools import product
from typing import Any, cast

import cv2
import numpy as np

from scripts.diagnostics.score_border_background import separate_background
from valorant_ai_coach.hud.score_glyphs import StrictScoreGlyphReader
from valorant_ai_coach.hud.timer_glyphs import ImageU8

METHODS = ("rowcontrast", "native_border", "white", "local_tophat")


def _mask(gray: ImageU8, method: str) -> ImageU8:
    if method == "native_border":
        gray = separate_background(gray)
    big = cv2.resize(gray, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    mask = np.where(big > 200, 255, 0).astype(np.uint8)
    if method == "rowcontrast":
        background = np.maximum(np.median(big[:, :8], axis=1), np.median(big[:, -8:], axis=1))[
            :, None
        ]
        mask = np.where(big.astype(np.float32) - background >= 12, mask, 0).astype(np.uint8)
    elif method == "local_tophat":
        # Fixed relative support, no coordinates or preferred digit class.
        k = max(3, round(min(big.shape) / 5) | 1)
        contrast = cv2.morphologyEx(
            big, cv2.MORPH_TOPHAT, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))
        )
        mask = np.where((big > 200) & (contrast >= 12), 255, 0).astype(np.uint8)
    return mask


def _edge_similarity(first: ImageU8, second: ImageU8) -> float:
    a = cv2.Canny(first, 40, 100).astype(np.float32)
    b = cv2.Canny(second, 40, 100).astype(np.float32)
    # One-pixel tolerance has a descriptive raw similarity, never a probability.
    aa = cv2.dilate(a, np.ones((3, 3), np.uint8))
    bb = cv2.dilate(b, np.ones((3, 3), np.uint8))
    return float(((a * (bb > 0)).sum() + (b * (aa > 0)).sum()) / max(1.0, float(a.sum() + b.sum())))


def generate_score_hypotheses(
    roi: ImageU8,
    reader: StrictScoreGlyphReader,
    *,
    max_candidates: int = 20,
    methods: tuple[str, ...] = METHODS,
) -> dict[str, Any]:
    """Budget: four masks, <=8 components/mask, <=16 segmentations, <=20 texts.

    Component selection retains suspicious border/small/extra components as
    flags. Partial component subsets may propose text, but cannot pass safety.
    All digit rankings are retained even if the strict Reader would stop early.
    """
    if (
        type(max_candidates) is not int
        or not 1 <= max_candidates <= 20
        or not isinstance(roi, np.ndarray)
        or roi.dtype != np.uint8
        or roi.ndim not in (2, 3)
        or roi.size == 0
        or roi.ndim == 3
        and roi.shape[2] != 3
        or min(roi.shape[:2]) < 8
        or roi.shape[0] * roi.shape[1] > 262144
        or not isinstance(methods, tuple)
        or not methods
        or any(method not in METHODS for method in methods)
        or len(set(methods)) != len(methods)
    ):
        raise ValueError("invalid_or_unbounded_score_proposal")
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY) if roi.ndim == 3 else roi
    by_text: dict[str, dict[str, Any]] = {}
    masks: list[dict[str, Any]] = []
    for method in methods:
        mask = _mask(cast(ImageU8, gray), method)
        n, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
        border = bool(
            np.any(mask[0]) or np.any(mask[-1]) or np.any(mask[:, 0]) or np.any(mask[:, -1])
        )
        components = sorted(
            [
                (int(x), int(y), int(w), int(h), int(area), i)
                for i, (x, y, w, h, area) in enumerate(stats[1:n], 1)
                if area > 0
            ],
            key=lambda c: c[0],
        )
        entry: dict[str, Any] = {
            "method": method,
            "border_foreground": border,
            "component_count": len(components),
            "components": [],
            "reason": None,
        }
        masks.append(entry)
        if not 1 <= len(components) <= 8:
            entry["reason"] = "empty_or_component_budget"
            continue
        glyphs: list[list[dict[str, Any]]] = []
        for x, y, w, h, area, idx in components:
            isolated = np.where(labels[y : y + h, x : x + w] == idx, 255, 0).astype(np.uint8)
            glyph = reader._comparison_image(reader._normalize_known_white(isolated))
            ranked: list[dict[str, Any]] = []
            for digit in sorted(reader.comparison_templates):
                refs = reader.comparison_templates[digit]
                raw = max(
                    float(cv2.matchTemplate(glyph, ref, cv2.TM_CCOEFF_NORMED)[0, 0]) for ref in refs
                )
                edge = max(_edge_similarity(glyph, ref) for ref in refs)
                if not np.isfinite(raw) or not np.isfinite(edge):
                    raise ValueError("nonfinite_proposal_similarity")
                ranked.append({"digit": digit, "ncc": raw, "edge": edge})
            ranked.sort(key=lambda z: (-z["ncc"], z["digit"]))
            entry["components"].append({"box_2x": [x, y, w, h], "area": area, "digits": ranked})
            glyphs.append(ranked)
        # Single component and adjacent pairs: no missing-character completion.
        segments: list[tuple[int, ...]] = [(i,) for i in range(len(components))]
        segments += [(i, i + 1) for i in range(len(components) - 1)]
        for segment in segments[:16]:
            complete = len(segment) == len(components)
            selected = [components[i] for i in segment]
            layout = True
            if len(selected) == 2:
                (x, y, w, h, _, _), (xx, yy, _, hh, _, _) = selected
                layout = (
                    min(h, hh) >= 0.8 * max(h, hh)
                    and abs(y - yy) <= 0.15 * max(h, hh)
                    and 0 < xx - (x + w) <= max(h, hh)
                )
            combos = []
            for digits in product(*(glyphs[i] for i in segment)):
                text = "".join(d["digit"] for d in digits)
                if len(text) == 2 and text[0] == "0":
                    continue
                score = sum(d["ncc"] for d in digits) / len(digits)
                edge = sum(d["edge"] for d in digits) / len(digits)
                gaps = [
                    d["ncc"] - max(v["ncc"] for v in glyphs[i] if v["digit"] != d["digit"])
                    for i, d in zip(segment, digits, strict=True)
                ]
                combos.append(
                    {
                        "text": text,
                        "ncc": score,
                        "edge": edge,
                        "min_ncc": min(d["ncc"] for d in digits),
                        "min_gap": min(gaps),
                        "complete_components": complete,
                        "layout_supported": layout,
                        "border_foreground": border,
                        "method": method,
                        "segment": list(segment),
                        "glyph_boxes_2x": [list(c[:4]) for c in selected],
                        "unassigned_foreground_fraction": 1
                        - sum(c[4] for c in selected) / max(1, int(np.count_nonzero(mask))),
                    }
                )
            combos.sort(key=lambda z: (-z["ncc"], z["text"]))
            for proposal in combos[:5]:
                text = proposal["text"]
                if text not in by_text:
                    by_text[text] = {"text": text, "routes": []}
                by_text[text]["routes"].append(proposal)
    candidates = []
    for value in by_text.values():
        routes = sorted(value["routes"], key=lambda r: (-r["ncc"], r["method"]))
        value.update(
            ncc=routes[0]["ncc"],
            edge=max(r["edge"] for r in routes),
            routes=routes,
            accepted=False,
            state="UNCONFIRMED_HYPOTHESIS",
        )
        candidates.append(value)
    candidates.sort(key=lambda z: (-z["ncc"], z["text"]))
    return {
        "kind": "offline_score_multihypothesis_v1",
        "candidates": candidates[:max_candidates],
        "masks": masks,
        "unique_before_cap": len(candidates),
        "input_shape": list(roi.shape),
        "formal_events": [],
        "production_qualified": False,
    }


def rank_score_hypotheses(
    report: dict[str, Any], *, method: str = "ncc", learned_scores: dict[str, float] | None = None
) -> list[dict[str, Any]]:
    """Rank the same bounded candidate set; never add fabricated class strings."""
    if method not in {"ncc", "edge", "coverage_ncc", "learned"}:
        raise ValueError("unsupported_proposal_ranking")
    values = report["candidates"]
    if method == "learned":
        if learned_scores is None or any(not np.isfinite(v) for v in learned_scores.values()):
            raise ValueError("invalid_learned_ranking")
        values = [v for v in values if v["text"] in learned_scores]

    def key(value: dict[str, Any]) -> tuple[float, str]:
        if method == "coverage_ncc":
            # Explicit descriptive intervention: penalize discarded foreground
            # in the *same route*, without invented digits or label-fit weights.
            score = max(r["ncc"] - r["unassigned_foreground_fraction"] for r in value["routes"])
            return -float(score), str(value["text"])
        score = (
            learned_scores[value["text"]]
            if method == "learned" and learned_scores is not None
            else value[method]
        )
        return -float(score), str(value["text"])

    return sorted(values, key=key)


def selective_score(
    reader_value: str | None,
    proposals: list[dict[str, Any]],
    *,
    source_valid: bool,
    geometry_valid: bool,
) -> dict[str, Any]:
    """Preserve accepted baseline text; recover only separately supported routes.

    No threshold relaxation. Two extraction paths are correlated diagnostic
    support, not independent semantic GT. Callers must measure false recovery.
    """
    if source_valid is not True:
        raise ValueError("unverified_proposal_source")
    reasons = []
    if geometry_valid is not True:
        value = None
        reasons.append("geometry_unknown")
    elif reader_value is not None:
        if (
            not isinstance(reader_value, str)
            or not reader_value.isdecimal()
            or not 0 <= int(reader_value) <= 99
            or str(int(reader_value)) != reader_value
        ):
            raise ValueError("invalid_baseline_score")
        value = reader_value
        reasons.append("baseline_preserved")
    else:
        supported: dict[str, set[str]] = {}
        for proposal in proposals:
            for route in proposal["routes"]:
                if (
                    route["min_ncc"] >= 0.90
                    and route["min_gap"] >= 0.04
                    and route["complete_components"] is True
                    and route["layout_supported"] is True
                    and route["border_foreground"] is False
                    and route["unassigned_foreground_fraction"] <= 1e-12
                ):
                    supported.setdefault(proposal["text"], set()).add(route["method"])
        texts = [text for text, methods in supported.items() if len(methods) >= 2]
        value = texts[0] if len(texts) == 1 else None
        reasons.append(
            "cross_mask_supported" if value is not None else "insufficient_or_ambiguous_support"
        )
    return {
        "value": value,
        "state": "UNKNOWN" if value is None else "DEVELOPMENT_ONLY",
        "reasons": reasons,
        "semantic_correctness_verified": False,
        "formal_events": [],
    }

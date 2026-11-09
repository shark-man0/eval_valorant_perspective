"""Image-only viewed-agent signatures; shared engine owns identity and state.

Ability glyphs exclude charge bars, keybinds and ultimate counters. Matching a
recorder signature is a compatibility cue, never proof of recorder ownership.
Reference assets and their provenance are explicit private configuration.
"""

from __future__ import annotations

import hashlib
import importlib
from copy import deepcopy
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from numpy.typing import NDArray

from .evidence import digest, source_scope
from .replay import file_sha, read_json

VERSION = "development_composite_view_pixels_v1"
ABILITY_CENTERS = (0.411, 0.470, 0.529, 0.588)
PORTRAIT_ROI = (0.014, 0.735, 0.057, 0.812)


class AgentCatalogMatcher:
    """Explicit versioned public-reference pixels; no media-derived templates."""

    def __init__(self, index_path: Path) -> None:
        index = read_json(index_path)
        root = index_path.parent.resolve()
        self.references = []
        hashes = {}
        for agent in index["characters"]:
            masks = []
            for slot in ("Grenade", "Ability1", "Ability2", "Ultimate"):
                if slot not in agent["abilities"]:
                    break
                path = (root / agent["abilities"][slot]["image"]).resolve()
                if root not in path.parents:
                    raise ValueError("Reference outside explicit catalog")
                image = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
                if image is None or image.ndim != 3 or image.shape[2] != 4:
                    raise ValueError("RGBA ability reference required")
                mask = image[:, :, 3]
                ys, xs = np.where(mask > 50)
                if not len(xs):
                    raise ValueError("Empty ability reference")
                masks.append(mask[ys.min() : ys.max() + 1, xs.min() : xs.max() + 1])
                hashes[str(path.relative_to(root))] = file_sha(path)
            if len(masks) != 4:
                continue
            portrait_path = (root / agent["portrait_small"]).resolve()
            if root not in portrait_path.parents:
                raise ValueError("Reference outside explicit catalog")
            portrait = cv2.imread(str(portrait_path), cv2.IMREAD_GRAYSCALE)
            if portrait is None:
                raise ValueError("Readable portrait reference required")
            hashes[str(portrait_path.relative_to(root))] = file_sha(portrait_path)
            self.references.append((agent["name"], masks, portrait))
        if not self.references:
            raise ValueError("Nonempty explicit agent references required")
        self.bindings = {
            "catalog_version": index["catalog_version"],
            "index_sha256": file_sha(index_path),
            "asset_sha256s": hashes,
            "source_url": index["source_url"],
        }

    def measure(self, image: NDArray[np.uint8], measurement: dict[str, Any]) -> None:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        scale = image.shape[1] / 1920
        abilities: dict[str, dict[str, Any]] = {}
        portraits: dict[str, float] = {}
        for name, masks, portrait in self.references:
            scores = []
            for slot, mask in zip(measurement["ability_signature"], masks, strict=True):
                x1, y1, x2, y2 = slot["roi_pixel_bounds"]
                crop = gray[y1:y2, x1:x2]
                score = 0.0
                for dimension in (22, 26, 30, 34, 38, 42):
                    ratio = dimension * scale / max(mask.shape)
                    target = cv2.resize(
                        mask,
                        (
                            max(2, round(mask.shape[1] * ratio)),
                            max(2, round(mask.shape[0] * ratio)),
                        ),
                        interpolation=cv2.INTER_AREA,
                    )
                    if all(a <= b for a, b in zip(target.shape, crop.shape, strict=True)):
                        score = max(
                            score,
                            float(cv2.matchTemplate(crop, target, cv2.TM_CCOEFF_NORMED).max()),
                        )
                scores.append(round(score, 4))
            value = sum(sorted(scores, reverse=True)[:3]) / 3
            if name not in abilities or value > abilities[name]["score"]:
                abilities[name] = {
                    "agent": name,
                    "score": round(value, 4),
                    "slot_scores": scores,
                    "basis": "ordered_ability_glyphs",
                }
            x1, y1, x2, y2 = measurement["portrait_candidate"]["roi_pixel_bounds"]
            crop = gray[y1:y2, x1:x2]
            for dimension in (60, 65, 70, 75, 80):
                size = max(2, round(dimension * scale))
                if size <= min(crop.shape):
                    target = cv2.resize(portrait, (size, size))
                    portraits[name] = max(
                        portraits.get(name, 0),
                        float(cv2.matchTemplate(crop, target, cv2.TM_CCOEFF_NORMED).max()),
                    )
        ranked = sorted(abilities.values(), key=lambda c: (-c["score"], c["agent"]))
        margin = ranked[0]["score"] - ranked[1]["score"] if len(ranked) > 1 else 0
        accepted = ranked[0]["score"] >= 0.65 and margin >= 0.08
        for candidate in ranked[:3]:
            candidate.update(
                status="CANDIDATE",
                ownership="UNKNOWN",
                qualified=False,
                score_scope="template_similarity_not_probability",
            )
        measurement["viewed_agent_candidates"] = ranked[:3]
        measurement["viewed_agent_selection"] = ranked[0]["agent"] if accepted else "UNKNOWN"
        measurement["viewed_agent_selection_reason"] = (
            "three_glyph_appearance_margin" if accepted else "weak_or_ambiguous_templates"
        )
        measurement["portrait_candidate"]["agent_candidates"] = [
            {"agent": n, "score": round(s, 4), "ownership": "UNKNOWN", "qualified": False}
            for n, s in sorted(portraits.items(), key=lambda item: (-item[1], item[0]))[:3]
        ]
        measurement["reference_catalog"] = {
            "version": self.bindings["catalog_version"],
            "index_sha256": self.bindings["index_sha256"],
        }


def _feature(crop: NDArray[np.uint8]) -> dict[str, Any]:
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 35, 90)
    vector = cv2.resize(edges, (12, 12), interpolation=cv2.INTER_AREA)
    support = int(np.count_nonzero(edges))
    return {
        "descriptor": vector.reshape(-1).tolist() if support >= 12 else None,
        "edge_pixels": support,
        "roi_pixel_sha256": hashlib.sha256(crop.tobytes()).hexdigest(),
        "status": "CANDIDATE" if support >= 12 else "UNKNOWN",
    }


def measure_view(image: NDArray[np.uint8], ui: dict[str, Any]) -> dict[str, Any]:
    """Observe current HUD glyphs without Source, time, previous state or labels."""
    if image.dtype != np.uint8 or image.ndim != 3 or image.shape[2] != 3:
        raise ValueError("Native BGR image required")
    height, width = image.shape[:2]
    if min(height, width) < 64:
        raise ValueError("Readable native image geometry required")
    abilities = []
    for index, center in enumerate(ABILITY_CENTERS):
        box = [
            round((center - 0.020) * width),
            round(0.909 * height),
            round((center + 0.020) * width),
            round(0.950 * height),
        ]
        x1, y1, x2, y2 = box
        abilities.append({"slot": index, "roi_pixel_bounds": box, **_feature(image[y1:y2, x1:x2])})
    x1, y1, x2, y2 = [
        round(v * (width if i % 2 == 0 else height)) for i, v in enumerate(PORTRAIT_ROI)
    ]
    portrait = {
        "roi_pixel_bounds": [x1, y1, x2, y2],
        **_feature(image[y1:y2, x1:x2]),
        "subject": "viewed_actor_candidate_not_recorder",
    }
    # Reuse the existing measured UI fields. These are the same UI evidence,
    # not extra votes merely because this supplier transports them again.
    report = ui.get("combat_report_visible")
    spectator = ui.get("spectator_panel_present")
    return {
        "schema": VERSION,
        "ability_signature": abilities,
        "portrait_candidate": portrait,
        "viewed_agent_candidates": [],
        "report_or_log_visibility": {
            "combat_report": "VISIBLE" if report is True else "NOT_DETECTED",
            "killfeed": "NOT_ANALYSED",
            "chat_or_broadcast": "NOT_ANALYSED",
            "visibility_scope": "current_display_not_new_death",
        },
        "screen_mode": "SPECTATOR_CANDIDATE" if spectator is True else "UNKNOWN",
        "dependency_groups": {
            "abilities": "ability_glyph_pixels",
            "portrait": "lower_left_viewed_portrait",
            "report": "existing_combat_report_ui",
            "spectator": "existing_spectator_ui",
        },
        "variable_counters_excluded": True,
        "ownership": "UNKNOWN",
        "formal_outputs": 0,
    }


def signature_similarity(left: list[dict[str, Any]], right: list[dict[str, Any]]) -> list[float]:
    scores = []
    for a, b in zip(left, right, strict=True):
        av, bv = a.get("descriptor"), b.get("descriptor")
        if not (isinstance(av, list) and isinstance(bv, list) and len(av) == len(bv) == 144):
            continue
        x, y = np.array(av, dtype=float), np.array(bv, dtype=float)
        x -= x.mean()
        y -= y.mean()
        norm = float(np.linalg.norm(x) * np.linalg.norm(y))
        if norm > 0:
            scores.append(round(float(x @ y / norm), 4))
    return scores


def attach_composite_views(states: list[dict[str, Any]], observations: dict[str, Any]) -> None:
    """Called by DevelopmentGameTimeline, not an independent state machine.

    Anchors require a current SELF/ALIVE estimate plus explicit current owner
    evidence. No first-frame assumption; no anchoring from carried state. Neither
    portrait nor a matching agent can alone change life/camera or Map ownership.
    """
    anchors: dict[tuple[str, ...], dict[str, Any]] = {}
    prior_reports: dict[tuple[str, ...], str] = {}
    for frame in states:
        rows = [observations[i] for i in frame["observation_ids"]]
        scope = source_scope(frame["sample"])
        if any(
            any(
                r["continuity"].get(k) is True
                for k in ("content_break_confirmed", "source_discontinuity", "discontinuity")
            )
            for r in rows
        ):
            anchors.pop(scope, None)
            prior_reports.pop(scope, None)
        cues = [r for r in rows if r["raw"].get("schema") == VERSION]
        if not cues:
            continue
        # Conflicting suppliers stay unresolved; never average duplicate cues.
        if len(cues) != 1:
            frame["viewed_identity"] = {
                "status": "UNKNOWN",
                "reason": "conflicting_visual_suppliers",
            }
            continue
        row = cues[0]
        raw = row["raw"]
        owner = [r for r in rows if "owner_hud" in r["signals"]]
        blocked = any(
            set(r["signals"]) & {"spectator", "remote", "death", "downed", "revival"} for r in rows
        )
        supported = sum(a.get("descriptor") is not None for a in raw["ability_signature"]) >= 3
        current_self = (
            frame["camera"]["value"] == "SELF"
            and frame["life"]["value"] == "ALIVE"
            and bool(owner)
            and not blocked
            and supported
            and frame["camera"]["origin"] == "observation_projection"
        )
        if scope not in anchors and current_self:
            anchors[scope] = {
                "ability_signature": deepcopy(raw["ability_signature"]),
                "evidence_ids": [row["observation_id"], *[r["observation_id"] for r in owner]],
                "sample": deepcopy(frame["sample"]),
                "agent_candidates": deepcopy(raw["viewed_agent_candidates"]),
                "qualified": False,
                "identity_status": "recorder_candidate_from_current_SELF_HUD",
            }
        anchor = anchors.get(scope)
        scores = (
            signature_similarity(anchor["ability_signature"], raw["ability_signature"])
            if anchor
            else []
        )
        match = len(scores) >= 3 and sum(s >= 0.75 for s in scores) >= 3
        mismatch = len(scores) >= 3 and sum(s < 0.35 for s in scores) >= 3
        frame["viewed_identity"] = {
            "recording_player_anchor": deepcopy(anchor),
            "viewed_agent_candidates": deepcopy(raw["viewed_agent_candidates"]),
            "portrait_candidate": deepcopy(raw["portrait_candidate"]),
            "ability_slot_similarity": scores,
            "agent_signature_relation": "COMPATIBLE"
            if match
            else "DIFFERENT"
            if mismatch
            else "UNKNOWN",
            "current_view_candidate": frame["camera"]["value"],
            "recorder_life_candidate": frame["life"]["value"],
            "report_or_log_visibility": deepcopy(raw["report_or_log_visibility"]),
            "evidence_ids": [row["observation_id"]],
            "same_agent_is_not_identity": True,
            "state_changed": False,
            "ownership": "UNKNOWN",
            "qualified": False,
            "reason": "current_visual_compatibility_only" if anchor else "no_current_SELF_anchor",
        }
        report = raw["report_or_log_visibility"]["combat_report"]
        previous = prior_reports.get(scope)
        frame["viewed_identity"]["report_display_change"] = (
            "PERSISTING"
            if report == previous == "VISIBLE"
            else "VISIBLE_ONSET_CANDIDATE"
            if report == "VISIBLE" and previous is not None
            else "FIRST_OBSERVATION"
            if previous is None
            else "NOT_DETECTED"
        )
        prior_reports[scope] = report


class CompositeViewObserver:
    """Opt-in supplier wrapper: all former measurements remain unchanged."""

    def __init__(self, config_path: Path) -> None:
        cfg = read_json(config_path)
        if set(cfg) - {
            "parent_observer",
            "parent_config",
            "agent_catalog",
            "visibility_tessdata",
        } or not {
            "parent_observer",
            "parent_config",
        } <= set(cfg):
            raise ValueError("Explicit parent observer/config required")
        module, name = cfg["parent_observer"].split(":", 1)
        self.parent = getattr(importlib.import_module(module), name)(Path(cfg["parent_config"]))
        self.matcher = (
            AgentCatalogMatcher(Path(cfg["agent_catalog"])) if "agent_catalog" in cfg else None
        )
        self.visibility = None
        if "visibility_tessdata" in cfg:
            from .hud_visibility import HUDVisibilityReader

            self.visibility = HUDVisibilityReader(Path(cfg["visibility_tessdata"]))
        self.view_fingerprint = digest(
            {
                "version": VERSION,
                "code": file_sha(Path(__file__)),
                "centers": ABILITY_CENTERS,
                "portrait": PORTRAIT_ROI,
                "references": self.matcher.bindings if self.matcher else None,
                "visibility": self.visibility.bindings if self.visibility else None,
            }
        )
        self.bindings = {
            "schema": VERSION,
            "parent": self.parent.bindings,
            "parent_fingerprint": self.parent.fingerprint,
            "config_sha256": file_sha(config_path),
            "baseline_producer_fingerprints": self.parent.bindings.get(
                "baseline_producer_fingerprints", [self.parent.fingerprint]
            ),
            "supplier_producer_fingerprints": [
                *self.parent.bindings.get(
                    "supplier_producer_fingerprints", [self.parent.fingerprint]
                ),
                self.view_fingerprint,
            ],
        }
        self.fingerprint = digest(self.bindings)

    def inspect(self, image: NDArray[np.uint8]) -> dict[str, Any]:
        result: dict[str, Any] = deepcopy(self.parent.inspect(image))
        suppliers = result.get("supplier_observations")
        if suppliers is None:
            suppliers = [
                {k: deepcopy(result[k]) for k in ("signals", "raw", "context", "map_candidates")}
            ]
            suppliers[0]["producer_fingerprint"] = self.parent.fingerprint
        ui: dict[str, Any] = next(
            (r["raw"]["ui"] for r in suppliers if isinstance(r["raw"].get("ui"), dict)), {}
        )
        raw = measure_view(image, ui)
        if self.matcher:
            self.matcher.measure(image, raw)
        if self.visibility:
            raw["hud_visibility"] = self.visibility.inspect(image, ui)
        suppliers.append(
            {
                "producer_fingerprint": self.view_fingerprint,
                "signals": [],
                "context": {"stream_kind": "hud_composite_view"},
                "map_candidates": [],
                "raw": raw,
            }
        )
        result["supplier_observations"] = suppliers
        return result

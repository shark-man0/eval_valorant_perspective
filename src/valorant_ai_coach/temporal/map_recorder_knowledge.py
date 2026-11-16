"""Opt-in matching of viewed HUD and Map portraits by game Knowledge Agent UUID."""

from __future__ import annotations

import hashlib
import math
from collections.abc import Sequence
from dataclasses import dataclass
from fractions import Fraction
from importlib import import_module
from pathlib import Path
from typing import Any, cast

import cv2
import numpy as np
from numpy.typing import NDArray

from .evidence import digest, freeze_native_sample, native_time, source_scope
from .map_marker_geometry import MarkerGeometry, measure_marker_geometry, same_marker
from .map_recorder_camera import measure_recorder_view
from .map_recorder_path import ReferenceCallouts
from .map_rim_ranking import measure_warm_rims, rank_rim_candidates
from .map_shape_ranking import rank_marker_context
from .replay import read_json
from .visual_state import selected_agent

_AXIS = np.arange(11) - 5
_DISC = np.hypot(_AXIS[:, None], _AXIS[None, :]) <= 5


def _vector(patch: NDArray[np.uint8]) -> NDArray[np.float32] | None:
    values = patch[_DISC].astype(np.float32)
    values -= values.mean(axis=0)
    norm = float(np.linalg.norm(values))
    return (values / norm).ravel() if norm else None


@dataclass(frozen=True)
class _Match:
    marker: MarkerGeometry
    uuid: str
    sample: dict[str, Any]
    round_token: str | None
    camera_fingerprint: str
    count: int


class KnowledgeRecorderMap:
    """Use independent pixel measurements inside the existing Camera/Life guard."""

    def __init__(
        self, *, hud: Any, catalog: Any,
        portraits: Sequence[tuple[str, NDArray[np.uint8]]], provenance: dict[str, Any],
        map_references: Sequence[tuple[str, str, Path, str]] = (),
    ) -> None:
        self._hud = hud
        self._catalog = catalog
        self.provenance = provenance
        self.map_references = tuple(map_references)
        groups: dict[str, list[NDArray[np.float32]]] = {}
        for agent_id, portrait in portraits:
            bgr = portrait[:, :, :3]
            shapes = [bgr]
            if portrait.shape[2] == 4:
                y, x = np.nonzero(portrait[:, :, 3] > 100)
                if len(x):
                    shapes.append(bgr[y.min():y.max()+1, x.min():x.max()+1])
            for shape in shapes:
                for size in (11, 13, 15, 17, 19):
                    resized = cv2.resize(shape, (size, size), interpolation=cv2.INTER_AREA)
                    half = (size - 11) // 2
                    offsets = (-2, 0, 2) if half >= 2 else (0,)
                    for y0 in offsets:
                        for x0 in offsets:
                            x1, y1 = half + x0, half + y0
                            vector = _vector(cast(NDArray[np.uint8], resized[y1:y1+11, x1:x1+11]))
                            if vector is not None:
                                groups.setdefault(agent_id, []).append(vector)
        if set(groups) != set(hud.agent_uuids) or len(groups) < 2:
            raise ValueError("Complete competing portrait UUIDs are required")
        self._uuids = tuple(sorted(groups))
        self._starts = np.cumsum([0, *(len(groups[uid]) for uid in self._uuids[:-1])])
        self._portraits = np.stack([v for uid in self._uuids for v in groups[uid]])
        self._previous: _Match | None = None

    @classmethod
    def load(cls, asset_cache: Path, map_catalog: Path) -> KnowledgeRecorderMap:
        # PR #153 is an opt-in dependency. The ordinary Map exporter remains
        # available in a checkout that does not contain the Knowledge package.
        try:
            knowledge = import_module("valorant_ai_coach.knowledge")
        except ModuleNotFoundError as exc:
            if exc.name != "valorant_ai_coach.knowledge":
                raise
            raise ValueError("Map knowledge mode requires the external game knowledge API") from exc
        loader = import_module("valorant_ai_coach.knowledge.assets")
        hud_module = import_module("valorant_ai_coach.knowledge.hud_abilities")
        catalog = knowledge.load_game_knowledge()
        assets = loader.ReferenceAssets.load(asset_cache)
        portraits = []
        for agent in catalog.agents:
            for variant in ("displayicon", "killfeedportrait"):
                portraits.append((agent.uuid, assets.image(f"agent:{agent.uuid}:{variant}")))
        root = map_catalog.parent.resolve()
        hashes = {}
        for row in read_json(map_catalog).get("characters", []):
            agent = catalog.agent(row["name"])
            if agent is None or "minimap_portrait" not in row:
                continue
            path = (root / row["minimap_portrait"]).resolve()
            if not path.is_relative_to(root) or agent.uuid in hashes:
                raise ValueError("Unique in-catalog Map portrait per Agent UUID required")
            data = path.read_bytes()
            portrait = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_UNCHANGED)
            if portrait is None or portrait.ndim != 3 or portrait.shape[2] not in (3, 4):
                raise ValueError("Readable color minimap portrait required")
            hashes[agent.uuid] = hashlib.sha256(data).hexdigest()
            portraits.append((agent.uuid, portrait))
        map_references = []
        for game_map in catalog.maps:
            asset_id = f"map:{game_map.uuid}:displayicon"
            if assets.has(asset_id):
                record = assets.records[asset_id]
                map_references.append((game_map.name, game_map.uuid, record.path, record.sha256))
        return cls(
            hud=hud_module.AbilityHudReader(catalog, assets), catalog=catalog, portraits=portraits,
            provenance={"knowledge_asset_digest": assets.content_digest,
                        "minimap_portrait_sha256": hashes},
            map_references=map_references,
        )

    @staticmethod
    def callouts(asset_cache: Path, map_catalog: Path) -> list[ReferenceCallouts]:
        """Bind optional Knowledge labels to the identical registered displayicon."""
        knowledge = import_module("valorant_ai_coach.knowledge")
        loader = import_module("valorant_ai_coach.knowledge.assets")
        catalog = knowledge.load_game_knowledge()
        assets = loader.ReferenceAssets.load(asset_cache)
        root = map_catalog.parent.resolve()
        paths = {entry["id"]: (root / entry["reference"]).resolve()
                 for entry in read_json(map_catalog)["maps"]}
        callouts = []
        for game_map in catalog.maps:
            asset_id = f"map:{game_map.uuid}:displayicon"
            if not game_map.callouts or not assets.has(asset_id):
                continue
            asset = assets.records[asset_id]
            path = paths.get(game_map.uuid)
            if path is not None and path.is_file() and (
                not path.is_relative_to(root)
                or hashlib.sha256(path.read_bytes()).hexdigest() != asset.sha256
            ):
                continue
            sha = asset.sha256
            image = assets.image(asset_id)
            width, height = image.shape[1], image.shape[0]
            anchors = []
            for anchor in game_map.callouts:
                x, y = anchor.minimap_xy
                if 0 <= x < 1 and 0 <= y < 1 and image[int(y * height), int(x * width), 3] > 0:
                    anchors.append((anchor.label, (x, y)))
            callouts.append(ReferenceCallouts(game_map.uuid, sha, (width, height), anchors))
        return callouts

    def reset(self) -> None:
        self._previous = None

    def _hud_uuid(self, image: NDArray[np.uint8]) -> str | None:
        reading = self._hud.read(self._hud.strip_from_frame(image))
        ranked = reading.ranked(2)
        if not reading.hud_present or len(ranked) != 2:
            return None
        (winner, score), (_, rival) = ranked
        if score < .68 or score - rival < .16:
            return None
        index = reading.agent_uuids.index(winner)
        # Require support from distinct ability slots. The HUD agent describes
        # the viewed avatar; it cannot establish recorder ownership.
        if sum(scores[index] >= .65 and scores[index] >= scores.max() - .01
               for scores in reading.slot_scores.values()) < 2:
            return None
        return str(winner)

    def _portrait_scores(
        self, image: NDArray[np.uint8], center: tuple[int, int],
    ) -> NDArray[np.float32] | None:
        x, y = center
        scale = image.shape[1] / 1920
        half = max(2, round(5 * scale))
        vectors = []
        for dx, dy in ((0, 0), (-1, 0), (1, 0), (0, -1), (0, 1)):
            left, top = x + dx - half, y + dy - half
            patch = image[top:top+2*half+1, left:left+2*half+1]
            if left < 0 or top < 0 or patch.shape[:2] != (2*half+1, 2*half+1):
                continue
            resized = cv2.resize(patch, (11, 11), interpolation=cv2.INTER_AREA)
            vector = _vector(cast(NDArray[np.uint8], resized))
            if vector is not None:
                vectors.append(vector)
        if not vectors:
            return None
        best = np.max(self._portraits @ np.stack(vectors).T, axis=1)
        return np.maximum.reduceat(best, self._starts)

    def _matches(
        self, image: NDArray[np.uint8], pool: list[dict[str, Any]], uuid: str,
    ) -> tuple[tuple[int, MarkerGeometry] | None, str]:
        rims = measure_warm_rims(image, pool)
        ranked = rank_rim_candidates(
            rank_marker_context(image, pool), rims, rim_weight=6, direction_weight=2,
        )
        # Geometry of all warm-shell candidates can veto or duplicate a match.
        indices = [row["candidate_index"] for row in ranked if row["rim_support"] >= .30]
        geometry = measure_marker_geometry(image, [pool[i] for i in indices])
        target = self._uuids.index(uuid)
        matches: list[tuple[int, MarkerGeometry]] = []
        rivals: list[MarkerGeometry] = []
        for index, marker in zip(indices, geometry, strict=True):
            if marker is None or marker.palette != "WARM":
                if marker is not None:
                    rivals.append(marker)
                continue
            scores = self._portrait_scores(image, marker.center)
            if scores is None:
                continue
            best = float(scores[target])
            rival = float(np.delete(scores, target).max())
            if best < .75 or best - rival < .12 or marker.support < .65:
                rivals.append(marker)
                continue
            if all(not same_marker(marker, other) for _, other in matches):
                matches.append((index, marker))
        if not matches:
            return None, "portrait_agent_unresolved"
        if len(matches) > 1:
            return None, "distinct_matching_markers"
        index, marker = matches[0]
        if any(not same_marker(marker, other) and
               math.dist(marker.center, other.center) <= marker.radius * 2 for other in rivals):
            return None, "competing_marker_or_overlap"
        return (index, marker), "matched_agent_uuid"

    def observe(
        self, image: NDArray[np.uint8], pool: list[dict[str, Any]], sample: dict[str, Any],
        frame: dict[str, Any], observations: Sequence[dict[str, Any]], baseline: dict[str, Any],
    ) -> dict[str, Any]:
        previous, self._previous = self._previous, None
        if baseline["selection_reason"] == "unmatched_native_context":
            return baseline
        sample = freeze_native_sample(sample)
        if (sample != frame.get("sample")
                or baseline.get("sample_sha256") != sample["sample_sha256"]
                or baseline.get("ordered_candidate_pool_digest") != digest(pool)
                or list(image.shape[:2][::-1]) != sample["frame_size_px"]
                or hashlib.sha256(image.tobytes()).hexdigest() != sample["native_pixel_sha256"]):
            return baseline
        if (
            frame.get("camera", {}).get("value") != "SELF"
            or frame.get("life", {}).get("value") != "ALIVE"
            or not pool
        ):
            return baseline
        camera, veto = measure_recorder_view(frame, observations)
        if veto or camera is None:
            return baseline
        mapped = frame.get("map") or {}
        supplied = (mapped.get("research_recorder_marker_v2") or {}).get(
            "ordered_candidate_pool_digest")
        if (supplied != digest(pool) if supplied is not None else mapped.get("candidates") != pool):
            return baseline
        uid = self._hud_uuid(image)
        if uid is None:
            return {**baseline, "knowledge_reason": "ability_hud_unresolved"}
        view = frame.get("viewed_identity") or {}
        anchor = view.get("recording_player_anchor")
        if view.get("agent_signature_relation") == "DIFFERENT":
            return {**baseline, "knowledge_reason": "current_view_conflicts_with_anchor"}
        names = [selected_agent(view.get("viewed_agent_candidates", []))]
        if anchor:
            origin = freeze_native_sample(anchor["sample"])
            if (source_scope(origin) == source_scope(sample)
                    and native_time(origin) < native_time(sample)):
                names.append(selected_agent(anchor.get("agent_candidates", [])))
        for name in names:
            known = self._catalog.agent(name) if name else None
            if known is not None and known.uuid != uid:
                return _conflict(baseline, "ability_hud_conflicts_with_anchor")
        chosen, reason = self._matches(image, pool, uid)
        if chosen is None:
            if (baseline["selection_status"] == "RESEARCH_SELECTED"
                    and reason in {"distinct_matching_markers", "competing_marker_or_overlap"}):
                return _conflict(baseline, reason)
            return {**baseline, "knowledge_reason": reason}
        index, marker = chosen
        round_token = frame.get("round_token")
        count = 1
        if previous is not None:
            gap = native_time(sample) - native_time(previous.sample)
            if (
                0 < gap <= Fraction(1, 4)
                and source_scope(sample) == source_scope(previous.sample)
                and previous.sample["native_pixel_sha256"] != sample["native_pixel_sha256"]
                and previous.round_token == round_token and previous.uuid == uid
                and previous.camera_fingerprint == camera
                and frame.get("continuity", {}).get("carry_allowed") is True
                and math.dist(marker.center, previous.marker.center)
                <= image.shape[1] / 1920 * (3 + 35*float(gap))
            ):
                count = previous.count + 1
        self._previous = _Match(marker, uid, sample, round_token, camera, count)
        accepted = count >= 2 or (marker.tip is not None and marker.support >= .84)
        if accepted and baseline["selection_status"] == "RESEARCH_SELECTED":
            legacy_index = baseline["research_candidate_index"]
            same_center = (
                math.dist(marker.center, baseline["support_center_frame_px"]) <= marker.radius / 2
            )
            if same_center and index != legacy_index:
                legacy_fit, = measure_marker_geometry(image, [pool[legacy_index]])
                same_center = legacy_fit is not None and same_marker(marker, legacy_fit)
            if not same_center:
                self.reset()
                return _conflict(baseline, "different_physical_markers")
        # An attached, well-fitted tip and independent HUD + portrait agreement
        # can establish an isolated development point. We still require adjacent
        # observed points to draw any path edge.
        if not accepted:
            if baseline["selection_status"] == "RESEARCH_SELECTED":
                return baseline
            return {**baseline, "knowledge_reason": "requires_tip_or_adjacent_match"}
        return {
            **baseline, "selection_status": "RESEARCH_SELECTED",
            "selection_reason": "measured_recorder_hud_and_knowledge_agent_portrait",
            "knowledge_reason": reason, "selection_method": "knowledge_agent_uuid",
            "research_candidate_index": index, "support_candidate_index": index,
            "research_marker_center_frame_px": list(marker.center),
            "support_center_frame_px": list(marker.center), "support_count": count,
            "recorder_agent_candidate": self._catalog.agent(uid).name,
            "recorder_agent_uuid_candidate": uid,
            "track_anchor": digest([camera, round_token, uid]),
        }


def _conflict(baseline: dict[str, Any], reason: str) -> dict[str, Any]:
    """Drop both candidates and their path witnesses at a contradictory observation."""
    return {
        **baseline,
        "selection_status": "ABSTAIN",
        "selection_reason": "recorder_selection_conflict",
        "knowledge_reason": reason,
        "research_candidate_index": None,
        "research_marker_center_frame_px": None,
        "recorder_agent_candidate": None,
        "support_candidate_index": None,
        "support_center_frame_px": None,
        "support_count": 0,
    }

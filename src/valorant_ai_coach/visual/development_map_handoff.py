"""Provisional Map consumer boundary, NOT the common game-state engine.

The common owner supplies exact-sample state snapshots. This module does not
infer life, camera, Round transitions or recorder identity from images. All
selected positions remain unqualified candidates, including supported SELF.
"""

from __future__ import annotations

import math
from copy import deepcopy
from fractions import Fraction
from typing import Any

import numpy as np

from .development_camera_marker_ui import UI_FINGERPRINT
from .development_map_features import OWNER_TRACK_FEATURE_FINGERPRINT
from .development_marker_attribution import freeze_native_sample
from .development_marker_features import Array, _digest
from .development_marker_temporal import DevelopmentMarkerAssociations

HANDOFF_VERSION = "map_consumer_provisional_v1"


def _sha(value: Any) -> bool:
    return (
        isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)
    )


def _sealed(record: dict[str, Any], key: str) -> bool:
    return _sha(record.get(key)) and record[key] == _digest(
        {k: v for k, v in record.items() if k != key}
    )


def make_map_observation(
    *,
    sample: dict[str, Any],
    pool: dict[str, Any],
    ui: dict[str, Any],
    appearance: dict[str, Any],
    geometry: dict[str, Any],
    reference_context_fingerprint: str,
) -> dict[str, Any]:
    """Export existing observations without consuming HUD or human marker IDs.

    Geometry is the existing proposal envelope; reference context identifies the
    immutable Source/agent reference binding, not its per-frame match scores.
    Scores retain their original meaning and are not calibrated probabilities.
    """
    size = sample.get("frame_size_px", [])
    n = pool.get("parent_count")
    if (
        len(size) != 2
        or freeze_native_sample(sample, frame_size_px=tuple(size)) != sample
        or pool.get("sample") != sample
        or not _sealed(pool, "pool_sha256")
        or pool.get("ownership") != "UNKNOWN"
        or pool.get("formal_outputs") != 0
        or type(n) is not int
        or not 0 <= n <= 128
        or not n <= len(pool.get("candidates", [])) <= 320
        or ui.get("sample_sha256") != sample["sample_sha256"]
        or ui.get("pool_sha256") != pool["pool_sha256"]
        or ui.get("feature_fingerprint") != UI_FINGERPRINT
        or ui.get("qualification") != "development_only"
        or ui.get("ownership") != "UNKNOWN"
        or ui.get("formal_outputs") != 0
        or len(ui.get("rows", [])) != n
        or appearance.get("sample_sha256") != sample["sample_sha256"]
        or appearance.get("ownership") != "UNKNOWN"
        or appearance.get("qualification") != "development_only"
        or appearance.get("formal_outputs") != 0
        or geometry.get("sample") != sample
        or geometry.get("map_id") != pool.get("map_id_candidate")
        or geometry.get("qualification") != "development_only"
        or geometry.get("formal_self_position_fact") is not None
        or not isinstance(geometry.get("geometry_version"), str)
        or not _sha(reference_context_fingerprint)
    ):
        raise ValueError("Exact native Map/UI/reference/geometry observations required")
    for i, row in enumerate(ui["rows"]):
        if row.get("candidate_index") != i or row.get("marker_observation_id") != _digest(
            {"sample": sample["sample_sha256"], "pool": pool["pool_sha256"], "index": i}
        ):
            raise ValueError("Current image-derived candidate IDs required")
        if any(
            isinstance(row.get(k), bool)
            or not isinstance(row.get(k), (float, int))
            or not math.isfinite(row[k])
            for k in ("warm_rim_arc", "radial_alignment", "score")
        ):
            raise ValueError("Finite uncalibrated UI scores required")
    consistent = appearance.get("consistent_indices", [])
    if not isinstance(consistent, list) or any(
        type(i) is not int or not 0 <= i < n for i in consistent
    ):
        raise ValueError("Current appearance candidate indices required")
    eligible = [
        r
        for r in ui["rows"]
        if r["warm_rim_arc"] >= 0.15
        and r["radial_alignment"] >= 0.55
        and r["candidate_index"] in consistent
    ]
    eligible.sort(key=lambda r: (-r["score"], r["candidate_index"]))
    unique = bool(
        eligible and (len(eligible) == 1 or eligible[0]["score"] - eligible[1]["score"] >= 0.12)
    )
    index = (
        eligible[0]["candidate_index"]
        if (unique and appearance.get("reference_source_agent_supported") is True)
        else None
    )
    record = deepcopy(
        {
            "schema": HANDOFF_VERSION,
            "sample": sample,
            "pool": pool,
            "ui": ui,
            "appearance": appearance,
            "geometry_observation": deepcopy(geometry),
            "geometry_version": geometry["geometry_version"],
            "calibration": geometry.get("calibration", {}),
            "reference_context_fingerprint": reference_context_fingerprint,
            "initial_candidate_index": index,
            "selection_semantics": "Map_UI_and_reference_agreement_not_owner_proof",
            "qualification": "development_only",
            "ownership": "UNKNOWN",
            "formal_outputs": 0,
        }
    )
    record["observation_sha256"] = _digest(record)
    return record


def validate_external_context(context: dict[str, Any], sample: dict[str, Any]) -> None:
    """Validate a provisional adapter snapshot; never assert upstream truth.

    The integration owner must map its API to these requirements. Evidence refs
    are mandatory even for human-conditioned or controlled ablations; those
    origins cannot be reported as automatic common-engine recognition.
    """
    if (
        not _sealed(context, "context_sha256")
        or context.get("schema") != HANDOFF_VERSION
        or context.get("sample_sha256") != sample["sample_sha256"]
        or context.get("origin")
        not in {"common_engine", "human_exact_frame", "controlled_ablation"}
        or not _sha(context.get("producer_fingerprint"))
        or not isinstance(context.get("revision"), str)
        or not context["revision"]
        or not isinstance(context.get("tracking_epoch"), str)
        or not context["tracking_epoch"]
        or context.get("round_state") not in {"BUY", "ACTIVE", "ENDED", "INTERMISSION", "UNKNOWN"}
        or context.get("recorder_life") not in {"ALIVE", "DEAD", "DOWNED", "UNKNOWN"}
        or context.get("camera") not in {"SELF", "SPECTATOR", "REMOTE", "UNKNOWN"}
        or context.get("recorder_correspondence") not in {"supported", "conflicting", "UNKNOWN"}
        or context.get("source_continuity") not in {"continuous", "discontinuous", "UNKNOWN"}
        or not isinstance(context.get("evidence_sha256s"), list)
        or not context["evidence_sha256s"]
        or not all(_sha(v) for v in context["evidence_sha256s"])
        or context.get("qualification") != "development_only"
        or context.get("ownership") != "UNKNOWN"
        or context.get("formal_outputs") != 0
    ):
        raise ValueError("Exact-sample external development context required")
    token = context.get("round_token")
    if token is not None and (not isinstance(token, str) or not token):
        raise ValueError("Opaque external Round token required")
    if context.get("self_view_round_token") is not None and (
        not isinstance(context["self_view_round_token"], str)
        or not context["self_view_round_token"]
    ):
        raise ValueError("Externally reconfirmed self-view Round scope required")


def _gate(context: dict[str, Any] | None) -> str | None:
    if context is None:
        return "common_state_unavailable"
    if context["camera"] in {"SPECTATOR", "REMOTE"}:
        return "external_camera_blocks_recorder_position"
    if context["recorder_life"] in {"DEAD", "DOWNED"}:
        return "external_life_blocks_current_position"
    if context["round_state"] in {"ENDED", "INTERMISSION"}:
        return "external_round_blocks_current_position"
    if not (
        context["recorder_life"] == "ALIVE"
        and context["camera"] == "SELF"
        and context["recorder_correspondence"] == "supported"
        and context["round_state"] in {"BUY", "ACTIVE"}
        and context.get("round_token") is not None
        and context.get("self_view_round_token") == context["round_token"]
        and context["source_continuity"] == "continuous"
    ):
        return "external_self_or_round_support_incomplete"
    return None


class DevelopmentMapStateConsumer:
    """Map identity memory and observed endpoints only; no game-state machine."""

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.links = DevelopmentMarkerAssociations()
        self.previous: dict[str, Any] | None = None
        self.memory: dict[str, Any] | None = None
        self.last_known: dict[str, Any] | None = None
        self.native_input_times: dict[tuple[str, str], Fraction] = {}
        self.scope: str | None = None
        self.segment = 0

    def observe(
        self,
        observation: dict[str, Any],
        features: Array,
        *,
        context: dict[str, Any] | None,
        continuity: dict[str, Any] | None,
    ) -> dict[str, Any]:
        try:
            return self._observe(observation, features, context=context, continuity=continuity)
        except Exception:
            self.reset()
            raise

    def _observe(
        self,
        observation: dict[str, Any],
        features: Array,
        *,
        context: dict[str, Any] | None,
        continuity: dict[str, Any] | None,
    ) -> dict[str, Any]:
        if not _sealed(observation, "observation_sha256"):
            raise ValueError("Sealed Map observation required")
        # Revalidate semantics, not just a caller-recomputed checksum.
        sample, pool = observation["sample"], observation["pool"]
        rebuilt = make_map_observation(
            sample=sample,
            pool=pool,
            ui=observation["ui"],
            appearance=observation["appearance"],
            geometry=observation["geometry_observation"],
            reference_context_fingerprint=observation["reference_context_fingerprint"],
        )
        if rebuilt != observation or features.shape != (pool["parent_count"], 447):
            raise ValueError("Unchanged native observation/paired Map features required")
        input_key = sample["source_sha256"], sample["native_epoch"]
        native_time = sample["native_pts_tick"] * Fraction(sample["native_time_base"])
        if (
            input_key in self.native_input_times
            and native_time <= self.native_input_times[input_key]
        ):
            raise ValueError("Strict native acquisition order required")
        self.native_input_times[input_key] = native_time
        if context is not None:
            validate_external_context(context, sample)
        blocked = _gate(context)
        scope = _digest(
            {
                "source": sample["source_sha256"],
                "epoch": sample["native_epoch"],
                "base": sample["native_time_base"],
                "shape": sample["frame_size_px"],
                "profile": pool["profile_fingerprint"],
                "roi": pool["roi_xywh"],
                "map": pool["map_id_candidate"],
                "build": pool["map_build"],
                "geometry": observation["geometry_version"],
                "reference": observation["reference_context_fingerprint"],
                "measured_reference": observation["appearance"]
                .get("reference_measurements", {})
                .get("reference_fingerprint"),
                "producer": context.get("producer_fingerprint") if context else None,
                "origin": context.get("origin") if context else None,
                "round": context.get("round_token") if context else None,
                "tracking_epoch": context.get("tracking_epoch") if context else None,
            }
        )
        if self.scope != scope or blocked:
            self.links.reset()
            self.memory, self.previous = None, None
        # Last-known never crosses Source/geometry/Round boundaries, but can
        # remain historical on an explicit death/spectator veto in this scope.
        if self.scope != scope:
            self.last_known = None
        self.scope = scope
        n = pool["parent_count"]
        parent = {**pool, "candidates": pool["candidates"][:n]}
        parent.pop("pool_sha256")
        parent["pool_sha256"] = _digest(parent)
        association = self.links.observe(
            sample,
            parent,
            features,
            appearance_fingerprint=OWNER_TRACK_FEATURE_FINGERPRINT,
            continuity=continuity,
        )
        prior = self.previous["sample"] if self.previous else None
        # Generic associations intentionally drop their previous pool when it
        # is empty. Native acquisition continuity can still retain identity
        # across that measured absence, without inventing a position or edge.
        continuous = bool(
            prior
            and not blocked
            and continuity
            and continuity.get("verified") is True
            and continuity.get("source_sha256") == sample["source_sha256"]
            and continuity.get("native_epoch") == sample["native_epoch"]
            and continuity.get("time_base") == sample["native_time_base"]
            and continuity.get("previous_sample_sha256") == prior["sample_sha256"]
            and continuity.get("current_sample_sha256") == sample["sample_sha256"]
            and _sha(continuity.get("receipt_sha256"))
            and 0
            < (sample["native_pts_tick"] - prior["native_pts_tick"])
            * Fraction(sample["native_time_base"])
            <= Fraction(3, 10)
        )
        if not continuous:
            self.memory = None
        elif self.memory is not None and (
            sample["native_pts_tick"] - self.memory["pts"]
        ) * Fraction(sample["native_time_base"]) > Fraction(3, 5):
            # The old identity stays in last_known with its original sample,
            # but cannot veto all future initializations indefinitely. Fresh
            # current evidence starts a distinct lineage, never a bridged path.
            self.memory = None
        unit = features / np.maximum(np.linalg.norm(features, axis=1, keepdims=True), 1e-12)
        eligible = {
            r["candidate_index"]
            for r in observation["ui"]["rows"]
            if r["warm_rim_arc"] >= 0.15 and r["radial_alignment"] >= 0.55
        }
        index, origin = None, blocked or "marker_unobserved_or_unbound"
        if continuous and self.memory is not None:
            candidates = [
                v["current_index"]
                for v in association["links"]
                if v["previous_index"] == self.memory["index"] and v["current_index"] in eligible
            ]
            if self.previous is not None and self.previous["observed"] and len(candidates) == 1:
                index, origin = candidates[0], "temporal_endpoint_link"
            else:
                dt = (sample["native_pts_tick"] - self.memory["pts"]) * Fraction(
                    sample["native_time_base"]
                )
                candidates = [
                    i
                    for i in eligible
                    if 0 < dt <= Fraction(3, 5)
                    and float(unit[i] @ self.memory["feature"]) >= 0.90
                    and math.dist(pool["candidates"][i]["center_frame_px"], self.memory["point"])
                    <= 12
                ]
                if len(candidates) == 1:
                    index, origin = candidates[0], "unique_reappearance"
        fresh = observation["initial_candidate_index"]
        if blocked is None and fresh is not None:
            if index is not None and fresh != index:
                index, origin = None, "conflicting_current_marker_evidence"
            elif index is None and self.memory is not None:
                # A fresh highlight cannot silently switch a retained identity.
                origin = "retained_identity_requires_unique_reappearance"
            else:
                if origin != "unique_reappearance":
                    origin = (
                        "current_Map_evidence_refresh"
                        if index is not None
                        else "current_Map_evidence_initial"
                    )
                index = fresh
        current = None
        connected = bool(
            index is not None
            and continuous
            and self.previous
            and self.previous["observed"]
            and origin != "unique_reappearance"
        )
        if index is not None:
            if not connected:
                self.segment += 1
            marker = pool["candidates"][index]
            point = marker.get("geometry_only_map_position_norm")
            if point is not None and (
                len(point) != 2
                or any(
                    isinstance(v, bool)
                    or not isinstance(v, (int, float))
                    or not math.isfinite(v)
                    or not 0 <= v <= 1
                    for v in point
                )
            ):
                raise ValueError("Finite normalized candidate geometry required")
            current = {
                "marker_observation_id": observation["ui"]["rows"][index]["marker_observation_id"],
                "image_position_px": deepcopy(marker["center_frame_px"]),
                "map_position_norm": deepcopy(point)
                if observation["calibration"].get("status") == "ok"
                else None,
                "sample": deepcopy(sample),
            }
            lineage = (
                self.memory["lineage"]
                if self.memory
                else _digest({"scope": scope, "initial": current["marker_observation_id"]})
            )
            self.memory = {
                "index": index,
                "pts": sample["native_pts_tick"],
                "point": deepcopy(marker["center_frame_px"]),
                "feature": unit[index].copy(),
                "lineage": lineage,
                "marker_id": current["marker_observation_id"],
            }
            self.last_known = deepcopy(current)
        self.previous = (
            {"sample": deepcopy(sample), "observed": current is not None} if not blocked else None
        )
        return deepcopy(
            {
                "schema": HANDOFF_VERSION,
                "sample": sample,
                "observation_sha256": observation["observation_sha256"],
                "external_context": context,
                "scope_sha256": scope,
                "current_observation": current,
                "current_position_observed": current is not None,
                "last_known_observation": self.last_known,
                "last_known_is_current": current is not None,
                "marker_identity_candidate": self.memory["marker_id"] if self.memory else None,
                "identity_lineage_candidate": self.memory["lineage"] if self.memory else None,
                "selected_index": index,
                "reason": origin,
                "observed_segment_id": self.segment if current else None,
                "connected_to_previous_observation": connected,
                "connection_kind": "observed_endpoints_not_actual_path" if connected else None,
                "position_interpolated": False,
                "association": association,
                "qualification": "development_only",
                "ownership": "UNKNOWN",
                "formal_outputs": 0,
            }
        )


def aggregate_map_seconds(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Non-filling native-time bins [s,s+1); retain every detailed observation.

    Source PTS zero is the explicit origin. Empty seconds are omitted, never
    synthesized as observed positions or continuous Zone occupancy. Inputs must
    be ordered per Source/epoch. Distinct contexts/rounds remain separate rows.
    """
    bins: dict[tuple[str, str, str, int], dict[str, Any]] = {}
    last: dict[tuple[str, str], Fraction] = {}
    for record in records:
        s = record["sample"]
        if record.get("ownership") != "UNKNOWN" or record.get("formal_outputs") != 0:
            raise ValueError("Development Map outputs only")
        key = s["source_sha256"], s["native_epoch"]
        time = s["native_pts_tick"] * Fraction(s["native_time_base"])
        if key in last and time <= last[key]:
            raise ValueError("Strict native acquisition order required")
        last[key] = time
        second = time // 1
        bucket = (*key, record["scope_sha256"], second)
        row = bins.setdefault(
            bucket,
            {
                "source_sha256": key[0],
                "native_epoch": key[1],
                "scope_sha256": bucket[2],
                "second_from_source_pts_zero": second,
                "interval_sec": [second, second + 1],
                "observations": [],
                "observed_positions": [],
                "continuous_occupancy": "UNKNOWN",
                "qualification": "development_only",
                "ownership": "UNKNOWN",
                "formal_outputs": 0,
            },
        )
        row["observations"].append(deepcopy(record))
        if record["current_observation"] is not None:
            row["observed_positions"].append(deepcopy(record["current_observation"]))
    return list(bins.values())


def map_candidate_path_record(
    observation: dict[str, Any],
    result: dict[str, Any],
    *,
    frame_index: int,
    zone_resolution: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Adapt observed candidates to the existing private path analyzer/viewer.

    ZoneResolver must use the development Registry and controlled_player=False.
    Its state is reset on any missing position/segment/scope break by the caller.
    No held Zone may become observed occupancy in this adapter.
    """
    sample = observation["sample"]
    if (
        result.get("observation_sha256") != observation.get("observation_sha256")
        or result.get("sample") != sample
        or result.get("ownership") != "UNKNOWN"
        or result.get("formal_outputs") != 0
        or type(frame_index) is not int
        or frame_index < 0
    ):
        raise ValueError("Matching unqualified Map consumer output required")
    if zone_resolution is not None and (
        zone_resolution.get("qualification") != "development_only"
        or zone_resolution.get("ownership") != "UNKNOWN"
        or zone_resolution.get("formal_outputs") != 0
        or zone_resolution.get("map_id") != observation["pool"]["map_id_candidate"]
        or zone_resolution.get("geometry_version") != observation["geometry_version"]
        or zone_resolution.get("frame_index") != frame_index
        or zone_resolution.get("time_sec")
        != float(sample["native_pts_tick"] * Fraction(sample["native_time_base"]))
    ):
        raise ValueError("Same-frame development Zone resolution required")
    point = result["current_observation"]
    zone = deepcopy(zone_resolution)
    if point is None or (zone is not None and zone.get("held_from_previous") is not False):
        zone = None
    return {
        "source_id": sample["source_id"],
        "acquisition_id": sample["acquisition_id"],
        "context_sha256": result["scope_sha256"],
        "time_sec": float(sample["native_pts_tick"] * Fraction(sample["native_time_base"])),
        "frame_index": frame_index,
        "map_id": observation["pool"]["map_id_candidate"],
        "geometry_version": observation["geometry_version"],
        "map_position_norm": point["map_position_norm"] if point else None,
        "map_segment": result["observed_segment_id"],
        "calibration": deepcopy(observation["calibration"]),
        "zone_resolution": zone or {},
        "appearance": {"reason": result["reason"]},
        "time_evidence": "native_PTS",
        "native_sample": deepcopy(sample),
        "external_context": deepcopy(result["external_context"]),
        "ownership": {"identity": "UNKNOWN", "view_eligible": point is not None},
        "formal_self_position_fact": None,
        "qualification": "development_only",
        "position_subject": "unqualified_recorder_association_candidate",
        "view_state_qualified": False,
    }

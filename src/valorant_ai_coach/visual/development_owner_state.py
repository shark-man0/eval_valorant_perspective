"""Independent recorder life, camera, marker identity and current measurements.

PR107's cue validation and legacy hypothesis are reused, not treated as truth.
Spectator-only death stays a hypothesis. Missing positions suspend a binding;
they neither invent a location nor prove a different person. All outputs remain
unqualified, separate from Production ownership, facts and events.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, replace
from fractions import Fraction
from typing import Literal

from .development_self_timeline import DevelopmentSelfTimeline, SelfFrameCues

Life = Literal["unknown", "alive", "dead", "downed"]
View = Literal["unknown", "self", "first_person_candidate", "spectator", "remote"]


@dataclass(frozen=True)
class MarkerObservation:
    marker_id: str
    image_position_px: tuple[float, float]
    map_position_norm: tuple[float, float] | None = None
    zone_id: str | None = None


@dataclass(frozen=True)
class OwnerObservation:
    cue: SelfFrameCues
    # These are positive reader-supported observations, not UI absences.
    life_evidence: Literal[
        "none", "owner_alive", "owner_death", "owner_downed", "owner_revival", "owner_round_reentry"
    ] = "none"
    other_death_observed: bool = False
    # Agent/HUD agreement can support a first-person association hypothesis,
    # but does not identify the current account or recorder life.
    first_person_candidate: bool = False
    life_evidence_sha256: str | None = None
    life_subject: Literal["none", "recorder", "visible_subject", "other_player"] = "none"
    binding_marker_id: str | None = None
    binding_origin: Literal["none", "automatic_ui", "human_diagnostic"] = "none"
    # Caller provides a current image-reader evidence receipt for automatic UI.
    binding_evidence_sha256: str | None = None
    markers: tuple[MarkerObservation, ...] = ()
    # Stable source/Profile/geometry/round interpretation scope, not a track ID.
    context_fingerprint: str = ""
    associations: tuple[tuple[str, str], ...] = ()
    ambiguous_reappearance: bool = False


class DevelopmentOwnerTimeline:
    """A retained identity is not a measurement of its current position."""

    def __init__(self) -> None:
        self._legacy = DevelopmentSelfTimeline()
        self.reset()

    def reset(self) -> None:
        self._previous: OwnerObservation | None = None
        self._life: Life = "unknown"
        self._view: View = "unknown"
        self._marker: str | None = None
        self._binding_origin = "none"
        self._binding_receipt: str | None = None
        self._suspended = False
        self._legacy = DevelopmentSelfTimeline()

    def observe(self, observation: OwnerObservation) -> dict[str, object]:
        try:
            return self._observe(observation)
        except Exception:
            self.reset()
            raise

    def _observe(self, o: OwnerObservation) -> dict[str, object]:
        c = o.cue
        if (
            len(o.context_fingerprint) != 64
            or any(x not in "0123456789abcdef" for x in o.context_fingerprint)
            or o.binding_origin not in {"none", "automatic_ui", "human_diagnostic"}
            or o.life_evidence
            not in {
                "none",
                "owner_alive",
                "owner_death",
                "owner_downed",
                "owner_revival",
                "owner_round_reentry",
            }
        ):
            raise ValueError("Current source/geometry context and evidence kind required")
        if o.binding_marker_id is not None and (
            not o.binding_marker_id
            or o.binding_origin == "none"
            or not isinstance(o.binding_evidence_sha256, str)
            or len(o.binding_evidence_sha256) != 64
            or any(x not in "0123456789abcdef" for x in o.binding_evidence_sha256)
        ):
            raise ValueError("Explicit marker UI evidence receipt required")
        if o.life_evidence != "none" and (
            o.life_subject != "recorder"
            or not isinstance(o.life_evidence_sha256, str)
            or len(o.life_evidence_sha256) != 64
            or any(x not in "0123456789abcdef" for x in o.life_evidence_sha256)
        ):
            raise ValueError("Recorder-subject direct life evidence receipt required")
        ids = [m.marker_id for m in o.markers]
        if len(ids) != len(set(ids)) or len(ids) > 320:
            raise ValueError("Unique bounded current-frame marker observations required")
        for m in o.markers:
            if (
                not m.marker_id
                or len(m.image_position_px) != 2
                or any(not math.isfinite(x) or x < 0 for x in m.image_position_px)
                or (
                    m.map_position_norm is not None
                    and (
                        len(m.map_position_norm) != 2
                        or any(not math.isfinite(x) or not 0 <= x <= 1 for x in m.map_position_norm)
                    )
                )
                or (m.zone_id is not None and m.map_position_norm is None)
            ):
                raise ValueError(
                    "Finite current marker measurement and map/zone dependency required"
                )
        prior = self._previous
        continuous = bool(
            prior is not None
            and c.continuous_from_previous
            and c.source_sha256 == prior.cue.source_sha256
            and c.source_epoch == prior.cue.source_epoch
            and c.time_base == prior.cue.time_base
            and o.context_fingerprint == prior.context_fingerprint
            and Fraction(0) < (c.pts_ticks - prior.cue.pts_ticks) * c.time_base <= Fraction(3, 10)
        )
        if not continuous:
            self._life, self._view = "unknown", "unknown"
            self._marker, self._binding_receipt, self._binding_origin = None, None, "none"
            self._suspended = False
        old_view = self._view
        legacy = self._legacy.observe(c)
        modes = sum((c.own_view_ui, c.spectator_ui, c.remote_view_ui, o.first_person_candidate))
        self._view = (
            "unknown"
            if modes != 1
            else "self"
            if c.own_view_ui
            else "spectator"
            if c.spectator_ui
            else "remote"
            if c.remote_view_ui
            else "first_person_candidate"
        )
        # Absence of a camera observation is not a positive return to self view.
        camera_transition = bool(
            continuous and modes == 1 and old_view == "self" and c.spectator_ui
        )
        life_hypothesis = "dead" if c.spectator_ui or camera_transition else "unknown"
        reason = "no_direct_life_evidence"
        if modes > 1:
            self._life, reason = "unknown", "conflicting_camera_evidence"
        elif o.life_evidence == "owner_death":
            self._life, reason = "dead", "direct_owner_death_observation"
        elif o.life_evidence == "owner_downed":
            self._life, reason = "downed", "direct_owner_downed_observation"
        elif o.life_evidence in {"owner_revival", "owner_round_reentry"}:
            supported = o.life_evidence == "owner_round_reentry" or self._life in {"dead", "downed"}
            self._life = "alive" if supported and self._view == "self" else "unknown"
            reason = o.life_evidence if supported else "unanchored_revival"
        elif o.life_evidence == "owner_alive":
            self._life = (
                "alive"
                if self._view == "self" and self._life not in {"dead", "downed"}
                else "unknown"
            )
            reason = "owner_alive_evidence" if self._life == "alive" else "missing_return_edge"
        elif c.spectator_ui:
            # Last observed ALIVE is not a claim that the recorder is alive now.
            self._life = "unknown" if self._life == "alive" else self._life
            reason = "spectator_only_not_direct_owner_death"
        if c.new_round_reentry:
            self._marker, self._binding_receipt, self._binding_origin = None, None, "none"
        if self._view in {"spectator", "remote"} or self._life in {"dead", "downed"}:
            self._marker, self._binding_receipt, self._binding_origin = None, None, "none"
        if o.ambiguous_reappearance:
            # Keep the historical evidence, but never choose an ambiguous point.
            current = None
            binding_state = "ambiguous_reappearance"
        else:
            permitted = (self._view == "self" and self._life == "alive") or (
                self._view == "first_person_candidate"
                and self._life == "unknown"
                and o.binding_origin in {"none", "automatic_ui"}
            )
            if o.binding_marker_id is not None and permitted:
                if o.binding_marker_id not in ids:
                    raise ValueError("Binding must refer to an observed current candidate")
                self._marker = o.binding_marker_id
                self._binding_origin, self._binding_receipt = (
                    o.binding_origin,
                    o.binding_evidence_sha256,
                )
                self._suspended = False
            if self._marker is not None:
                next_ids = [b for a, b in o.associations if a == self._marker]
                if len(next_ids) == 1:
                    self._marker = next_ids[0]
                    self._suspended = False
                elif len(next_ids) > 1:
                    o = replace(o, ambiguous_reappearance=True)
            current = next((m for m in o.markers if m.marker_id == self._marker), None)
            if not permitted or o.ambiguous_reappearance or self._suspended:
                current = None
            binding_state = "observed" if current else "suspended" if self._marker else "unbound"
        self._suspended = current is None and self._marker is not None
        self._previous = o
        return {
            "life": self._life,
            "life_evidence_kind": o.life_evidence,
            "life_evidence_sha256": o.life_evidence_sha256,
            "life_subject": o.life_subject,
            "life_reason": reason,
            "life_hypothesis": life_hypothesis,
            "camera": self._view,
            "self_to_spectator_observed": camera_transition,
            "other_death_observed": o.other_death_observed,
            "recorder_marker_id": self._marker,
            "binding_state": binding_state,
            "binding_origin": self._binding_origin,
            "binding_evidence_sha256": self._binding_receipt,
            "current_observation": asdict(current) if current else None,
            "current_position_observed": current is not None,
            "current_observation_subject": "recorder_association_candidate",
            "marker_binding_qualified": False,
            "position_interpolated": False,
            "legacy_PR107_hypothesis": asdict(legacy),
            "qualification": "development_only",
            "ownership": "UNKNOWN",
            "formal_outputs": 0,
        }

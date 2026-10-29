"""Exact-frame UI observations -> PR107 owner-state hypotheses, offline only.

Report/killfeed observations never assert owner death. Current-frame inference,
temporal carry and optional exact reviewed initialization remain separate.
"""

from __future__ import annotations

import hashlib
import math
from copy import deepcopy
from dataclasses import asdict
from fractions import Fraction
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from .development_marker_attribution import _sha, freeze_native_sample
from .development_marker_features import _digest
from .development_ownership import DevelopmentOwnershipEvidence
from .development_recorder_view import DevelopmentRecorderView
from .development_self_timeline import DevelopmentSelfTimeline, SelfFrameCues
from .development_view import DevelopmentViewVeto

_FLAGS = (
    "own_hud_support",
    "spectator_ui",
    "combat_report_visible",
    "purchase_phase_visible",
    "remote_ui",
)
_OPTIONAL_FLAGS = (
    "death_animation_ui",
    "downed_ui",
    "revival_ui",
    "ability_return_ui",
    "active_phase_visible",
    "round_result_visible",
)


def _spectated_subject(
    alias: Any, sample: dict[str, Any], *, spectator_present: bool
) -> dict[str, Any] | None:
    """Forward an existing current-frame name read, never recorder identity."""
    if not isinstance(alias, dict):
        return None
    name, confidence = alias.get("observed_alias"), alias.get("ocr_confidence")
    if (
        spectator_present is not True
        or alias.get("status") != "observed"
        or alias.get("slot_kind") != "spectated_player_name"
        or not isinstance(name, str)
        or not 1 <= len(name.strip()) <= 64
        or not isinstance(confidence, (int, float))
        or isinstance(confidence, bool)
        or not math.isfinite(confidence)
        or not 0.90 <= confidence <= 1
        or not _sha(alias.get("current_name_pixels_sha256"))
        or not _sha(alias.get("activation_reference_sha256"))
    ):
        return None
    return {
        "kind": "spectated_display_alias",
        "observed_alias": name.strip(),
        "ocr_confidence": float(confidence),
        "sample_sha256": sample["sample_sha256"],
        "source_sha256": sample["source_sha256"],
        "native_epoch": sample["native_epoch"],
        "name_pixels_sha256": alias["current_name_pixels_sha256"],
        "activation_reference_sha256": alias["activation_reference_sha256"],
        "ownership": "UNKNOWN",
        "qualification": "development_only",
        "origin": "image_reader",
        "qualified": False,
        "formal_outputs": 0,
    }


def _valid_subject(subject: Any, sample: dict[str, Any]) -> bool:
    if not isinstance(subject, dict):
        return False
    expected = _spectated_subject(
        {
            "observed_alias": subject.get("observed_alias"),
            "ocr_confidence": subject.get("ocr_confidence"),
            "status": "observed",
            "slot_kind": "spectated_player_name",
            "current_name_pixels_sha256": subject.get("name_pixels_sha256"),
            "activation_reference_sha256": subject.get("activation_reference_sha256"),
        },
        sample,
        spectator_present=True,
    )
    return expected is not None and subject == expected


class DevelopmentOwnerUI:
    """Reuse current image readers; an unbound glyph never becomes own-HUD proof.

    Positive shared HUD and recorder-agent signatures are only a development
    proposal. Unconfigured remote/return detectors remain explicitly unverified.
    """

    def __init__(self, profile: dict[str, Any]) -> None:
        self.profile = deepcopy(profile)
        self.screen = DevelopmentOwnershipEvidence()
        self.agent = DevelopmentRecorderView()
        self.spectator = DevelopmentViewVeto()

    @property
    def fingerprint(self) -> str:
        references: set[str] = set()

        def strings(value: Any) -> None:
            if isinstance(value, str):
                references.add(value)
            elif isinstance(value, (list, tuple)):
                for child in value:
                    strings(child)
            elif isinstance(value, dict):
                for child in value.values():
                    strings(child)

        def walk(value: Any) -> None:
            if isinstance(value, dict):
                for key, child in value.items():
                    if key in {
                        "template_path",
                        "templates",
                        "positive_templates",
                        "negative_templates",
                    }:
                        strings(child)
                    else:
                        walk(child)
            elif isinstance(value, (list, tuple)):
                for child in value:
                    walk(child)

        walk(self.profile)
        if len(references) > 128:
            raise ValueError("Bounded source UI references required")
        content = {}
        for path in sorted(references):
            try:
                with Path(path).open("rb") as stream:
                    raw = stream.read(1_000_001)
                if len(raw) > 1_000_000:
                    raise ValueError("Bounded UI reference required")
                content[path] = hashlib.sha256(raw).hexdigest()
            except OSError:
                content[path] = "UNAVAILABLE"
        return _digest(
            {
                "profile": self.profile,
                "references": content,
                "code": {
                    name: hashlib.sha256(
                        (Path(__file__).parents[1] / name).read_bytes()
                    ).hexdigest()
                    for name in (
                        "visual/development_owner_observations.py",
                        "visual/development_ownership.py",
                        "visual/development_recorder_view.py",
                        "visual/development_actor_alias.py",
                        "visual/development_view.py",
                        "hud/spectator_icon.py",
                        "hud/readers.py",
                        "hud/templates.py",
                        "video/geometry.py",
                    )
                },
                "opencv": cv2.__version__,
                "numpy": np.__version__,
            }
        )

    def inspect(self, image: np.ndarray, sample: dict[str, Any]) -> dict[str, Any]:
        size = sample.get("frame_size_px")
        if (
            not isinstance(size, list)
            or len(size) != 2
            or freeze_native_sample(sample, frame_size_px=tuple(size)) != sample
            or not isinstance(image, np.ndarray)
            or image.dtype != np.uint8
            or image.ndim != 3
            or image.shape[2] != 3
            or image.shape[0] * image.shape[1] > 16_777_216
            or [image.shape[1], image.shape[0]] != size
            or hashlib.sha256(image.tobytes()).hexdigest() != sample["native_pixel_sha256"]
        ):
            raise ValueError("Exact bound native image required")
        fingerprint = self.fingerprint
        roi = self.profile.get("rois", {}).get("minimap")
        kwargs = {
            "minimap_roi": roi,
            "source_id": sample["source_id"],
            "acquisition_id": sample["native_epoch"],
        }
        screen = self.screen.inspect(
            image,
            self.profile.get("development_ownership_evidence"),
            time_sec=float(
                Fraction(sample["native_pts_tick"]) * Fraction(sample["native_time_base"])
            ),
            frame_index=sample["native_pts_tick"],
            **kwargs,
        )
        agent = self.agent.inspect(
            image,
            self.profile.get("development_recorder_view"),
            source_sha256=sample["source_sha256"],
            **kwargs,
        )
        spectator = self.spectator.inspect(
            image,
            self.profile.get("development_view_veto"),
            feature_mode="positive_contrast_v1",
        )
        claims = {c["claim"] for c in screen["observed_cues"] if c["status"] == "present"}
        spectator_slot = screen.get("spectator_slot", {})
        present = (
            spectator_slot.get("panel_present") is True or spectator["status"] == "spectator_ui"
        )
        absent = (
            spectator_slot.get("checked") is True
            and spectator_slot.get("panel_present") is False
            and spectator["status"] == "not_detected"
        )
        own = (
            agent.get("positive_agent_association") is True
            and "first_person_hud" in claims
            and absent
            and not agent["block_position_candidate"]
        )
        if self.fingerprint != fingerprint:
            raise ValueError("UI references changed during observation")
        return {
            "sample_sha256": sample["sample_sha256"],
            "own_hud_support": own,
            "spectator_ui": present,
            "spectator_absence_checked": absent,
            "combat_report_visible": "death_report" in claims,
            "purchase_phase_visible": "purchase_phase" in claims,
            "remote_ui": False,
            "remote_detection": "not_configured_UNVERIFIED",
            "source_profile_fingerprint": _digest(self.profile),
            "fingerprint": fingerprint,
            "screen_measurements": screen,
            "agent_measurements": agent,
            "spectator_measurements": spectator,
            "spectated_subject_observation": _spectated_subject(
                agent.get("actor_alias_evidence"), sample, spectator_present=present
            ),
            "origin": "image_reader",
            "qualified": False,
            "formal_outputs": 0,
        }


def native_continuity(
    previous: dict[str, Any] | None,
    sample: dict[str, Any],
    receipt: dict[str, Any] | None,
    *,
    max_gap: Fraction = Fraction(3, 10),
) -> bool:
    """A caller-verified native receipt is required in addition to time proximity."""
    if previous is None or not receipt:
        return False
    dt = (Fraction(sample["native_pts_tick"]) - previous["native_pts_tick"]) * Fraction(
        sample["native_time_base"]
    )
    return bool(
        all(
            sample[k] == previous[k]
            for k in (
                "source_id",
                "source_sha256",
                "native_epoch",
                "native_time_base",
                "acquisition_id",
                "frame_size_px",
            )
        )
        and 0 < dt <= max_gap
        and receipt.get("verified") is True
        and receipt.get("source_sha256") == sample["source_sha256"]
        and receipt.get("native_epoch") == sample["native_epoch"]
        and receipt.get("time_base") == sample["native_time_base"]
        and receipt.get("previous_sample_sha256") == previous["sample_sha256"]
        and receipt.get("current_sample_sha256") == sample["sample_sha256"]
        and _sha(receipt.get("receipt_sha256"))
    )


class DevelopmentOwnerTimeline:
    """Reuse PR107 life/view; retain only observation provenance around it.

    A human initialization is an explicitly separate ablation, never disguised
    as automatic HUD recognition or used as a label on later frames.
    """

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.timeline = DevelopmentSelfTimeline()
        self.previous: dict[str, Any] | None = None
        self.previous_ui: dict[str, Any] | None = None
        self.last_direct_alive: dict[str, Any] | None = None
        self.active_death: str | None = None
        self.round_state = "UNKNOWN"
        self.anchor_origin: str | None = None
        self.report_seen = False
        self.report_previous = False

    def observe(
        self,
        sample: dict[str, Any],
        ui: dict[str, Any],
        *,
        continuity: dict[str, Any] | None = None,
        initial_review: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        try:
            return self._observe(sample, ui, continuity, initial_review)
        except Exception:
            self.reset()
            raise

    def _observe(
        self,
        sample: dict[str, Any],
        ui: dict[str, Any],
        continuity: dict[str, Any] | None,
        review: dict[str, Any] | None,
    ) -> dict[str, Any]:
        size = sample.get("frame_size_px")
        if (
            not isinstance(size, list)
            or len(size) != 2
            or freeze_native_sample(sample, frame_size_px=tuple(size)) != sample
            or ui.get("sample_sha256") != sample["sample_sha256"]
            or ui.get("origin") != "image_reader"
            or ui.get("qualified") is not False
            or ui.get("formal_outputs") != 0
            or not _sha(ui.get("fingerprint"))
            or not _sha(ui.get("source_profile_fingerprint"))
            or any(type(ui.get(key)) is not bool for key in _FLAGS)
            or any(key in ui and type(ui[key]) is not bool for key in _OPTIONAL_FLAGS)
        ):
            raise ValueError("Bound exact-native image UI measurements required")
        subject = ui.get("spectated_subject_observation")
        if subject is not None and (
            ui["spectator_ui"] is not True or not _valid_subject(subject, sample)
        ):
            raise ValueError("Current exact-frame spectator subject observation required")
        adjacent = (
            native_continuity(self.previous, sample, continuity)
            and ui.get("source_discontinuity", False) is False
            and self.previous_ui is not None
            and self.previous_ui.get("source_discontinuity", False) is False
            and all(
                ui[k] == self.previous_ui[k] for k in ("fingerprint", "source_profile_fingerprint")
            )
        )
        if not adjacent:
            self.reset()
        own = ui["own_hud_support"]
        if review is not None:
            if (
                self.previous is not None
                or review.get("sample_sha256") != sample["sample_sha256"]
                or review.get("frame_sha256") != sample["acquired_frame_sha256"]
                or not _sha(review.get("review_sha256"))
                or review.get("role") != "SELF_LIVE"
                or review.get("origin") != "human_exact_frame"
                or review.get("status") != "human_confirmed"
                or review.get("qualification") != "development_only"
                or review.get("ownership") != "UNKNOWN"
            ):
                raise ValueError("Exact reviewed initial SELF_LIVE frame required")
            own = True
            self.anchor_origin = "human_exact_frame"
        elif own:
            self.anchor_origin = "image_reader"
        previous_life, previous_view = self.timeline.life, self.timeline.view
        previous_round = self.round_state
        reentry = bool(
            adjacent
            and own
            and previous_round == "PRE_ROUND"
            and (previous_life != "alive" or previous_view != "self")
            and not ui["spectator_ui"]
        )
        direct_death = bool(
            adjacent
            and previous_life == "alive"
            and previous_view == "self"
            and ui.get("death_animation_ui") is True
        )
        screen = ui.get("screen_measurements", {})
        cues = screen.get("observed_cues", []) if isinstance(screen, dict) else []
        unresolved_view_change = bool(
            adjacent
            and previous_life == "alive"
            and previous_view == "self"
            and not own
            and ui["combat_report_visible"]
            and not self.report_previous
            and isinstance(screen, dict)
            and screen.get("status") == "observed"
            and isinstance(cues, list)
            and any(isinstance(c, dict) and c.get("claim") == "death_report"
                    and c.get("status") == "present" for c in cues)
            and any(isinstance(c, dict) and c.get("claim") == "first_person_hud"
                    and c.get("status") == "not_detected" for c in cues)
        )
        cue = SelfFrameCues(
            source_sha256=sample["source_sha256"],
            source_epoch=sample["native_epoch"],
            pts_ticks=sample["native_pts_tick"],
            time_base=Fraction(sample["native_time_base"]),
            continuous_from_previous=bool(adjacent),
            own_view_ui=own,
            self_death_transition=direct_death,
            spectator_ui=ui["spectator_ui"],
            remote_view_ui=ui["remote_ui"],
            downed_transition=ui.get("downed_ui", False),
            revival_transition=ui.get("revival_ui", False),
            ultimate_return=ui.get("ability_return_ui", False),
            new_round_reentry=reentry,
            unresolved_view_change=unresolved_view_change,
        )
        state = self.timeline.observe(cue)
        if ui["purchase_phase_visible"]:
            self.round_state = "PRE_ROUND"
        elif ui.get("round_result_visible"):
            self.round_state = "ROUND_END"
        elif ui.get("active_phase_visible"):
            self.round_state = "IN_ROUND"
        candidate = None
        if (
            adjacent
            and previous_life == "alive"
            and state.life == "dead"
            and self.last_direct_alive is not None
            and self.active_death is None
        ):
            kind = "composite_death_UI" if direct_death else "self_to_spectator_inferred"
            candidate = {
                "source_sha256": sample["source_sha256"],
                "epoch": sample["native_epoch"],
                "last_self_alive_pts": self.last_direct_alive["native_pts_tick"],
                "first_dead_hypothesis_pts": sample["native_pts_tick"],
                "native_time_base": sample["native_time_base"],
                "kind": kind,
                "internal_game_death_time": None,
                "qualified": False,
            }
            candidate["candidate_id"] = _digest(candidate)
            self.active_death = candidate["candidate_id"]
        elif state.life == "alive" and state.reason in {"round_reentry", "observed_revival"}:
            self.active_death = None
        if own and state.life == "alive" and state.view == "self":
            self.last_direct_alive = deepcopy(sample)
        report = ui["combat_report_visible"]
        report_state = (
            "persistent_observation"
            if report and self.report_previous
            else "presence_after_non_detection"
            if report and self.report_seen
            else "first_observed_presence"
            if report
            else "not_detected_after_presence"
            if self.report_seen
            else "not_detected"
        )
        self.report_seen |= report
        self.report_previous = report
        direct_own = ui["own_hud_support"]
        conflict = sum((direct_own, ui["spectator_ui"], ui["remote_ui"])) > 1
        baseline = {
            "life": "alive" if direct_own and not conflict else "unknown",
            "view": "unknown"
            if conflict
            else "spectator"
            if ui["spectator_ui"]
            else "remote"
            if ui["remote_ui"]
            else "self"
            if direct_own
            else "unknown",
        }
        if ui["spectator_ui"] and not adjacent:
            life_evidence = "unanchored_spectator_hypothesis"
        elif candidate is not None:
            life_evidence = candidate["kind"]
        elif state.reason == "temporal_carry":
            life_evidence = "temporal_inference"
        else:
            life_evidence = state.reason
        self.previous, self.previous_ui = deepcopy(sample), deepcopy(ui)
        return {
            **asdict(state),
            "sample_sha256": sample["sample_sha256"],
            "sample": deepcopy(sample),
            "raw_ui": deepcopy(ui),
            "baseline_current_frame": baseline,
            "round_state": self.round_state,
            "native_continuity_used": bool(adjacent),
            "anchor_origin": self.anchor_origin,
            "state_origin": "human_exact_frame"
            if review
            else "temporal_inference"
            if state.reason == "temporal_carry"
            else "image_reader",
            "life_evidence": life_evidence,
            "report_observation": report_state,
            "death_transition_candidate": candidate,
            "active_death_candidate_id": self.active_death,
            "camera_subject": ui.get("spectated_subject_observation"),
            "last_direct_alive_sample": deepcopy(self.last_direct_alive),
            "source_visual_continuity": "UNVERIFIED",
            "origin": "image_reader",
            "ownership": "UNKNOWN",
            "qualification": "development_only",
            "formal_outputs": 0,
        }

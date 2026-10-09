"""Qualified system events, independent of player identity and ownership.

Qualification is profile-bound offline evidence, not runtime ground truth. A
current source continuity segment is mandatory; absence never means continuous.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .models import timer_display_evidence
from .round_lifecycle import (
    MAX_SAMPLE_GAP_SEC,
    MIN_START_CONFIRMATION_SEC,
    SEMANTIC_PHASE_CONFIDENCE_KEY,
    BoundaryDecision,
    LifecycleState,
    is_discontinuous,
)
from .ui_transition import PendingUiStart


def _hash(value: Any) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def global_recognizer_fingerprint() -> str:
    """Bind qualification to shared recognition code as well as profile assets."""
    digest = hashlib.sha256()
    for source in sorted(Path(__file__).parent.glob("*.py")):
        digest.update(source.name.encode("utf-8"))
        digest.update(source.read_bytes().replace(b"\r\n", b"\n"))
    return digest.hexdigest()


@dataclass(frozen=True)
class GlobalLifecycleQualification:
    profile_fingerprint: str
    report_sha256: str
    components: frozenset[str]
    recognizer_fingerprint: str

    @classmethod
    def load(cls, path: Path, profile_fingerprint: str) -> GlobalLifecycleQualification:
        """Reject mismatched profiles, overlapping splits and unreviewed results.

        The report contains hashes/counts only. Expected values, timestamps,
        round IDs and validation-pack paths are not part of this contract.
        Counts describe reviewed cases, never predictions assumed correct.
        """
        content = path.read_bytes()
        data = json.loads(content)
        if (
            not isinstance(data, dict)
            or set(data)
            != {"schema_version", "profile_fingerprint", "recognizer_fingerprint", "components"}
            or data["schema_version"] != "1.0"
            or not _hash(profile_fingerprint)
            or data["profile_fingerprint"] != profile_fingerprint
            or data["recognizer_fingerprint"] != global_recognizer_fingerprint()
            or not isinstance(data["components"], dict)
        ):
            raise ValueError("Invalid or mismatched global lifecycle qualification")
        components = data["components"]
        if not {"timer", "purchase_phase", "continuity"} <= set(components) or not set(
            components
        ) <= {
            "timer",
            "purchase_phase",
            "continuity",
            "score",
            "round_result",
            "scene_continuity",
            "ui_transition",
        }:
            raise ValueError("Missing or unknown global lifecycle component")
        scene_components = {"scene_continuity", "ui_transition"}
        if set(components) & scene_components and not scene_components <= set(components):
            raise ValueError("Scene continuity and UI transition require paired qualification")
        for name, proof in components.items():
            if not isinstance(proof, dict) or set(proof) != {
                "training_hashes",
                "holdout_hashes",
                "negative_hashes",
                "holdout_correct",
                "holdout_unknown",
                "holdout_wrong",
                "negative_false_positive",
                "review_provenance",
            }:
                raise ValueError(f"Invalid qualification evidence: {name}")
            splits = []
            for key in ("training_hashes", "holdout_hashes", "negative_hashes"):
                hashes = proof[key]
                if (
                    not isinstance(hashes, list)
                    or len(hashes) < 3
                    or not all(_hash(h) for h in hashes)
                    or len(set(hashes)) != len(hashes)
                ):
                    raise ValueError(f"Insufficient distinct qualification support: {name}/{key}")
                splits.append(set(hashes))
            if any(splits[i] & splits[j] for i in range(3) for j in range(i)):
                raise ValueError(f"Qualification training/holdout/control overlap: {name}")
            counts = [
                proof[k]
                for k in (
                    "holdout_correct",
                    "holdout_unknown",
                    "holdout_wrong",
                    "negative_false_positive",
                )
            ]
            if (
                any(type(n) is not int or n < 0 for n in counts)
                or counts[0] < 3
                or counts[0] + counts[1] + counts[2] != len(splits[1])
                or counts[2:] != [0, 0]
                or not isinstance(proof["review_provenance"], str)
                or not proof["review_provenance"].strip()
            ):
                raise ValueError(f"Unqualified or unreviewed global component: {name}")
        aggregate_splits = [
            {h for proof in components.values() for h in proof[key]}
            for key in ("training_hashes", "holdout_hashes", "negative_hashes")
        ]
        if any(aggregate_splits[i] & aggregate_splits[j] for i in range(3) for j in range(i)):
            raise ValueError("Qualification splits overlap across global components")
        return cls(
            profile_fingerprint,
            hashlib.sha256(content).hexdigest(),
            frozenset(components),
            data["recognizer_fingerprint"],
        )


def _score(value: Any) -> float:
    return (
        float(value)
        if (type(value) in (int, float) and math.isfinite(value) and 0.90 <= value <= 1)
        else 0.0
    )


def _timer(observation: Mapping[str, Any]) -> tuple[float | None, float]:
    value = observation.get("values", {}).get("round_time_remaining_sec")
    score = _score(
        observation.get("quality", {}).get("roi_confidence", {}).get("round_timer_value")
    )
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
        return None, 0.0
    return float(value), score


def _phase(observation: Mapping[str, Any]) -> float:
    if (
        "buy_phase_banner" not in observation.get("state_flags", ())
        or observation.get("values", {}).get("buy_phase_visible") is not True
    ):
        return 0.0
    return _score(
        observation.get("quality", {}).get("roi_confidence", {}).get(SEMANTIC_PHASE_CONFIDENCE_KEY)
    )


def _display(observation: Mapping[str, Any]) -> dict[str, Any] | None:
    values = observation.get("values", {})
    if not isinstance(values, dict):
        return None
    try:
        result = timer_display_evidence(values)
    except ValueError:
        return None
    return result if result is not None and _score(result["provenance"]["confidence"]) > 0 else None


def _scene_attested(
    proof: Mapping[str, Any],
    previous: Mapping[str, Any] | None,
    qualification: GlobalLifecycleQualification,
) -> bool:
    cells = proof.get("witness_cells", [])
    scores = proof.get("witness_ncc", [])
    if not (
        proof.get("scope") == "scene_only"
        and proof.get("clock_independent") is True
        and proof.get("background_checked") is True
        and proof.get("profile_fingerprint") == qualification.profile_fingerprint
        and proof.get("recognizer_fingerprint") == qualification.recognizer_fingerprint
        and _hash(proof.get("source_pixel_sha256"))
        and _hash(proof.get("previous_source_pixel_sha256"))
        and proof["source_pixel_sha256"] != proof["previous_source_pixel_sha256"]
        and isinstance(cells, list)
        and len(cells) >= 3
        and all(
            isinstance(cell, list)
            and len(cell) == 2
            and all(type(n) is int and 0 <= n <= 2 for n in cell)
            for cell in cells
        )
        and isinstance(scores, list)
        and len(scores) == len(cells)
        and all(_score(score) > 0 for score in scores)
    ):
        return False
    if len({tuple(cell) for cell in cells}) != len(cells):
        return False
    return (
        len({cell[0] for cell in cells}) >= 2
        and len({cell[1] for cell in cells}) >= 2
        and (
            previous is None
            or (
                type(proof.get("previous_source_pts_sec")) in (int, float)
                and proof.get("previous_source_pts_sec") == previous.get("time_sec")
            )
        )
    )


class GlobalRoundLifecycle:
    """System-only boundaries from qualified current-frame global inputs.

    Missing timer is neutral for at most one second, only while continuity is
    positively attested. It never supplies a value or confidence. End requires
    distinct-frame accepted scores plus a qualified semantic result. This class
    never writes observations or emits player facts.
    """

    def __init__(self, qualification: GlobalLifecycleQualification) -> None:
        self.qualification = qualification
        self.scene_transition = {"scene_continuity", "ui_transition"} <= qualification.components
        self.ui_pending: PendingUiStart | None = None
        self.phase_timer: float | None = None
        self.phase_timer_confidence = 0.0
        self.previous_scene_pixel: str | None = None
        self.diagnostic_reason: str | None = "unobserved"
        self.state: LifecycleState = "unobserved"
        self.previous: Mapping[str, Any] | None = None
        self.segment: str | None = None
        self.pending: BoundaryDecision | None = None
        self.pending_timer: float | None = None
        self.armed = False
        self.phase_count = 0
        self.phase_pts: list[float] = []
        self.phase_confidence = 0.0
        self.ended = False
        self.continuity_confidence = 0.0

    def reset(self) -> None:
        self.ui_pending = None
        self.phase_timer = None
        self.phase_timer_confidence = 0.0
        self.previous_scene_pixel = None
        self.diagnostic_reason = "unobserved"
        self.state = "unobserved"
        self.previous = None
        self.segment = None
        self.pending = None
        self.pending_timer = None
        self.armed = False
        self.phase_count = 0
        self.phase_pts.clear()
        self.phase_confidence = 0.0
        self.ended = False
        self.continuity_confidence = 0.0

    def advance(
        self, observation: Mapping[str, Any], evidence: Mapping[str, Any]
    ) -> tuple[BoundaryDecision, ...]:
        previous = self.previous
        proof = evidence.get(
            "global_scene_continuity" if self.scene_transition else "global_continuity", {}
        )
        proof = proof if isinstance(proof, Mapping) else {}
        token = proof.get("segment")
        attested = (
            isinstance(token, str)
            and bool(token.strip())
            and proof.get("qualification_sha256") == self.qualification.report_sha256
            and type(proof.get("source_pts_sec")) in (int, float)
            and proof.get("source_pts_sec") == observation.get("time_sec")
            and _score(proof.get("confidence")) > 0
            and (not self.scene_transition or _scene_attested(proof, previous, self.qualification))
        )
        if (
            not attested
            or (
                self.scene_transition
                and self.previous_scene_pixel is not None
                and proof.get("previous_source_pixel_sha256") != self.previous_scene_pixel
            )
            or is_discontinuous(previous, observation, evidence)
            or (self.segment is not None and token != self.segment)
        ):
            reason = (
                "qualified_scene_proof_unavailable"
                if self.scene_transition
                else "qualified_continuity_proof_unavailable"
            )
            if is_discontinuous(previous, observation, evidence):
                reason = "source_discontinuity"
            elif attested and self.segment is not None and token != self.segment:
                reason = "source_epoch_changed"
            elif (
                self.scene_transition
                and self.previous_scene_pixel is not None
                and (proof.get("previous_source_pixel_sha256") != self.previous_scene_pixel)
            ):
                reason = "scene_source_chain_mismatch"
            self.reset()
            self.diagnostic_reason = reason
            return ()
        self.diagnostic_reason = None
        self.segment = token
        if self.scene_transition:
            self.previous_scene_pixel = proof["source_pixel_sha256"]
        self.previous = observation
        timestamp = float(observation["time_sec"])
        if not math.isfinite(timestamp):
            self.reset()
            return ()
        phase = _phase(observation)
        if (
            self.scene_transition
            and phase
            and self.state != "round_active"
            and (
                observation.get("primary_state") not in {"unknown", "live_first_person"}
                or set(observation.get("state_flags", ())) - {"buy_phase_banner"}
            )
        ):
            self.reset()
            self.diagnostic_reason = "incompatible_preparation_state"
            return ()
        if phase:
            if self.ui_pending is not None:
                self.state = "unobserved"
            self.ui_pending = None
            self.phase_timer, self.phase_timer_confidence = _timer(observation)
            if self.scene_transition and _display(observation) is None:
                self.phase_timer = None
                self.phase_timer_confidence = 0.0
        compatible = observation.get("primary_state") in {"unknown", "live_first_person"} and not (
            set(observation.get("state_flags", ())) - {"round_end_banner"}
        )
        # Preparation cannot reopen an active round. A qualified end or a
        # source reset must close that lifecycle first; otherwise a flickering
        # phase overlay can both duplicate starts and hide a genuine end.
        if phase and self.state != "round_active":
            if self.phase_count == 0:
                self.phase_pts.clear()
                self.phase_confidence = phase
                self.armed = False
            self.phase_count += 1
            self.phase_pts.append(timestamp)
            self.phase_confidence = min(self.phase_confidence, phase)
            # Semantic text may have been confirmed before this continuity
            # segment. Only source-attested phase observations in the current
            # segment can supply the existing minimum confirmation duration.
            if (
                self.phase_count >= 2
                and timestamp - self.phase_pts[0] >= MIN_START_CONFIRMATION_SEC
            ):
                self.armed = True
                self.state = "next_round_preparation" if self.ended else "pre_round"
        else:
            self.phase_count = 0
        timer, timer_score = _timer(observation)
        continuity_score = _score(proof.get("confidence"))
        prior_continuity_score = self.continuity_confidence
        self.continuity_confidence = continuity_score
        if self.scene_transition and self.state != "round_active":
            return self._ui_start(
                observation,
                evidence,
                timestamp,
                phase,
                compatible,
                timer,
                timer_score,
                continuity_score,
            )
        if self.pending is not None:
            self.pending = BoundaryDecision(
                self.pending.kind,
                self.pending.time_sec,
                min(self.pending.confidence, continuity_score),
                self.pending.attributes,
            )
            elapsed = timestamp - self.pending.time_sec
            if not compatible or elapsed > MAX_SAMPLE_GAP_SEC or phase:
                self.pending = None
            elif (
                timer is None
                and observation.get("values", {}).get("round_time_remaining_sec") is None
            ):
                self.pending.attributes["evidence_provenance"]["neutral_timer_pts_sec"].append(
                    timestamp
                )
                return ()
            elif (
                timer is not None
                and timer_score > 0
                and self.pending_timer is not None
                and 0 <= self.pending_timer - timer <= elapsed + 1
            ):
                if elapsed >= MIN_START_CONFIRMATION_SEC:
                    decision = self.pending
                    self.pending = None
                    self.armed = False
                    self.ended = False
                    self.state = "round_active"
                    provenance = decision.attributes["evidence_provenance"]
                    provenance["confirmation_pts_sec"] = timestamp
                    provenance["pts_sec"].append(timestamp)
                    return (
                        BoundaryDecision(
                            "round_start",
                            decision.time_sec,
                            min(decision.confidence, timer_score, continuity_score),
                            decision.attributes,
                        ),
                    )
                return ()
            else:
                self.pending = None
        if previous is None:
            return ()
        before, before_score = _timer(previous)
        prior_phase = _phase(previous)
        if (
            self.armed
            and prior_phase > 0
            and compatible
            and not phase
            and before is not None
            and timer is not None
            and min(before_score, timer_score) > 0
            and timer > before + 3
        ):
            self.pending_timer = timer
            self.pending = BoundaryDecision(
                "round_start",
                timestamp,
                min(
                    prior_phase,
                    before_score,
                    timer_score,
                    continuity_score,
                    prior_continuity_score,
                    self.phase_confidence,
                ),
                {
                    "evidence_provenance": {
                        "producer": "hud_analyzer",
                        "scope": "global_system",
                        "qualification_sha256": self.qualification.report_sha256,
                        "profile_fingerprint": self.qualification.profile_fingerprint,
                        "recognizer_fingerprint": self.qualification.recognizer_fingerprint,
                        "continuity_segment": self.segment,
                        "signals": ["qualified_purchase_phase", "accepted_timer_reset"],
                        "pts_sec": [float(previous["time_sec"]), timestamp],
                        "preparation_pts_sec": [self.phase_pts[0], self.phase_pts[-1]],
                        "preparation_observation_count": len(self.phase_pts),
                        "neutral_timer_pts_sec": [],
                    }
                },
            )
        return self._end(
            previous, observation, evidence, min(continuity_score, prior_continuity_score)
        )

    def _ui_start(
        self,
        observation: Mapping[str, Any],
        evidence: Mapping[str, Any],
        timestamp: float,
        phase: float,
        compatible: bool,
        timer: float | None,
        timer_score: float,
        scene_score: float,
    ) -> tuple[BoundaryDecision, ...]:
        if phase:
            self.diagnostic_reason = None if self.armed else "preparation_unconfirmed"
            return ()
        if not compatible or (
            self.ui_pending is not None
            and (timestamp - self.ui_pending.time_sec > MAX_SAMPLE_GAP_SEC)
        ):
            self.reset()
            self.diagnostic_reason = "transient_ui_timeout_or_state_conflict"
            return ()
        if self.ui_pending is None:
            transition = evidence.get("global_ui_transition", {})
            transition_score = (
                _score(transition.get("confidence")) if isinstance(transition, Mapping) else 0.0
            )
            if not (
                self.armed
                and compatible
                and self.phase_timer is not None
                and self.phase_timer_confidence > 0
                and transition_score > 0
                and type(transition.get("source_pts_sec")) in (int, float)
                and transition.get("source_pts_sec") == timestamp
                and transition.get("qualification_sha256") == self.qualification.report_sha256
                and transition.get("source_pixel_sha256") == self.previous_scene_pixel
                and transition.get("kind") == "phase_disappearance"
            ):
                self.diagnostic_reason = "qualified_ui_transition_or_preparation_unavailable"
                return ()
            self.ui_pending = PendingUiStart(
                timestamp,
                self.phase_timer,
                min(
                    scene_score,
                    self.phase_confidence,
                    self.phase_timer_confidence,
                    transition_score,
                ),
                {
                    "producer": "hud_analyzer",
                    "scope": "global_system",
                    "qualification_sha256": self.qualification.report_sha256,
                    "profile_fingerprint": self.qualification.profile_fingerprint,
                    "recognizer_fingerprint": self.qualification.recognizer_fingerprint,
                    "continuity_segment": self.segment,
                    "signals": [
                        "qualified_purchase_phase",
                        "qualified_scene_continuity",
                        "qualified_ui_transition",
                        "coherent_accepted_clock_display",
                    ],
                    "preparation_pts_sec": [self.phase_pts[0], self.phase_pts[-1]],
                    "preparation_observation_count": len(self.phase_pts),
                },
            )
            self.state = "transient_ui_transition"
        display_proof = _display(observation)
        display_score = _score(display_proof["provenance"]["confidence"]) if display_proof else 0.0
        decision = self.ui_pending.advance(
            timestamp,
            timer,
            min(timer_score, display_score),
            observation.get("values", {}).get("round_time_remaining_display"),
            scene_score,
            display_proof["provenance"] if display_proof else None,
            evidence["global_scene_continuity"],
        )
        if decision is None:
            self.diagnostic_reason = "coherent_clock_confirmation_pending"
            return ()
        self.diagnostic_reason = None
        self.ui_pending = None
        self.armed = False
        self.ended = False
        self.state = "round_active"
        return (decision,)

    def _end(
        self,
        previous: Mapping[str, Any],
        current: Mapping[str, Any],
        evidence: Mapping[str, Any],
        continuity_score: float,
    ) -> tuple[BoundaryDecision, ...]:
        if self.state != "round_active" or not {"score", "round_result"} <= (
            self.qualification.components
        ):
            return ()
        result_score = _score(evidence.get("global_round_result_confidence"))
        if evidence.get("global_round_result_present") is not True or not result_score:
            return ()
        before = previous.get("values", {})
        after = current.get("values", {})
        scores = [before.get(k) for k in ("score_ally", "score_enemy")] + [
            after.get(k) for k in ("score_ally", "score_enemy")
        ]
        confidence = [
            _score(row.get("quality", {}).get("roi_confidence", {}).get(k))
            for row in (previous, current)
            for k in ("ally_score_value", "enemy_score_value")
        ]
        if (
            not all(type(n) is int and n >= 0 for n in scores)
            or not all(confidence)
            or sorted([scores[2] - scores[0], scores[3] - scores[1]]) != [0, 1]
        ):
            return ()
        self.state = "round_ended"
        self.ended = True
        self.pending = None
        return (
            BoundaryDecision(
                "round_end",
                float(current["time_sec"]),
                min(result_score, continuity_score, *confidence),
                {
                    "evidence_provenance": {
                        "producer": "hud_analyzer",
                        "scope": "global_system",
                        "qualification_sha256": self.qualification.report_sha256,
                        "profile_fingerprint": self.qualification.profile_fingerprint,
                        "recognizer_fingerprint": self.qualification.recognizer_fingerprint,
                        "continuity_segment": self.segment,
                        "signals": ["qualified_round_result", "accepted_score_transition"],
                        "pts_sec": [float(previous["time_sec"]), float(current["time_sec"])],
                        "confirmation_pts_sec": float(current["time_sec"]),
                    }
                },
            ),
        )

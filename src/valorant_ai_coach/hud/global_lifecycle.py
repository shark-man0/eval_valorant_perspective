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

from .round_lifecycle import (
    MAX_SAMPLE_GAP_SEC,
    MIN_START_CONFIRMATION_SEC,
    SEMANTIC_PHASE_CONFIDENCE_KEY,
    BoundaryDecision,
    LifecycleState,
    is_discontinuous,
)


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
    def load(
        cls, path: Path, profile_fingerprint: str
    ) -> GlobalLifecycleQualification:
        """Reject mismatched profiles, overlapping splits and unreviewed results.

        The report contains hashes/counts only. Expected values, timestamps,
        round IDs and validation-pack paths are not part of this contract.
        Counts describe reviewed cases, never predictions assumed correct.
        """
        content = path.read_bytes()
        data = json.loads(content)
        if (
            not isinstance(data, dict)
            or set(data) != {
                "schema_version", "profile_fingerprint", "recognizer_fingerprint", "components"
            }
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
        ) <= {"timer", "purchase_phase", "continuity", "score", "round_result"}:
            raise ValueError("Missing or unknown global lifecycle component")
        for name, proof in components.items():
            if not isinstance(proof, dict) or set(proof) != {
                "training_hashes", "holdout_hashes", "negative_hashes",
                "holdout_correct", "holdout_unknown", "holdout_wrong", "negative_false_positive",
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
            counts = [proof[k] for k in (
                "holdout_correct", "holdout_unknown", "holdout_wrong", "negative_false_positive"
            )]
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
            profile_fingerprint, hashlib.sha256(content).hexdigest(), frozenset(components),
            data["recognizer_fingerprint"],
        )


def _score(value: Any) -> float:
    return float(value) if (
        type(value) in (int, float) and math.isfinite(value) and 0.90 <= value <= 1
    ) else 0.0


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
    return _score(observation.get("quality", {}).get("roi_confidence", {}).get(
        SEMANTIC_PHASE_CONFIDENCE_KEY
    ))


class GlobalRoundLifecycle:
    """System-only boundaries from qualified current-frame global inputs.

    Missing timer is neutral for at most one second, only while continuity is
    positively attested. It never supplies a value or confidence. End requires
    distinct-frame accepted scores plus a qualified semantic result. This class
    never writes observations or emits player facts.
    """

    def __init__(self, qualification: GlobalLifecycleQualification) -> None:
        self.qualification = qualification
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
        proof = evidence.get("global_continuity", {})
        token = proof.get("segment") if isinstance(proof, Mapping) else None
        attested = (
            isinstance(token, str) and bool(token.strip())
            and proof.get("qualification_sha256") == self.qualification.report_sha256
            and type(proof.get("source_pts_sec")) in (int, float)
            and proof.get("source_pts_sec") == observation.get("time_sec")
            and _score(proof.get("confidence")) > 0
        )
        if (
            not attested
            or is_discontinuous(previous, observation, evidence)
            or (self.segment is not None and token != self.segment)
        ):
            self.reset()
            return ()
        self.segment = token
        self.previous = observation
        timestamp = float(observation["time_sec"])
        if not math.isfinite(timestamp):
            self.reset()
            return ()
        phase = _phase(observation)
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
        if self.pending is not None:
            self.pending = BoundaryDecision(
                self.pending.kind, self.pending.time_sec,
                min(self.pending.confidence, continuity_score), self.pending.attributes,
            )
            elapsed = timestamp - self.pending.time_sec
            if not compatible or elapsed > MAX_SAMPLE_GAP_SEC or phase:
                self.pending = None
            elif timer is None and observation.get("values", {}).get(
                "round_time_remaining_sec"
            ) is None:
                self.pending.attributes["evidence_provenance"]["neutral_timer_pts_sec"].append(
                    timestamp
                )
                return ()
            elif (
                timer is not None and timer_score > 0 and self.pending_timer is not None
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
                    return (BoundaryDecision(
                        "round_start", decision.time_sec,
                        min(decision.confidence, timer_score, continuity_score),
                        decision.attributes,
                    ),)
                return ()
            else:
                self.pending = None
        if previous is None:
            return ()
        before, before_score = _timer(previous)
        prior_phase = _phase(previous)
        if (
            self.armed and prior_phase > 0 and compatible and not phase
            and before is not None and timer is not None
            and min(before_score, timer_score) > 0 and timer > before + 3
        ):
            self.pending_timer = timer
            self.pending = BoundaryDecision(
                "round_start", timestamp,
                min(
                    prior_phase, before_score, timer_score,
                    continuity_score, prior_continuity_score, self.phase_confidence,
                ),
                {"evidence_provenance": {
                    "producer": "hud_analyzer", "scope": "global_system",
                    "qualification_sha256": self.qualification.report_sha256,
                    "profile_fingerprint": self.qualification.profile_fingerprint,
                    "recognizer_fingerprint": self.qualification.recognizer_fingerprint,
                    "continuity_segment": self.segment,
                    "signals": ["qualified_purchase_phase", "accepted_timer_reset"],
                    "pts_sec": [float(previous["time_sec"]), timestamp],
                    "preparation_pts_sec": [self.phase_pts[0], self.phase_pts[-1]],
                    "preparation_observation_count": len(self.phase_pts),
                    "neutral_timer_pts_sec": [],
                }},
            )
        return self._end(
            previous, observation, evidence, min(continuity_score, prior_continuity_score)
        )

    def _end(
        self, previous: Mapping[str, Any], current: Mapping[str, Any],
        evidence: Mapping[str, Any], continuity_score: float,
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
            for row in (previous, current) for k in ("ally_score_value", "enemy_score_value")
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
        return (BoundaryDecision(
            "round_end", float(current["time_sec"]),
            min(result_score, continuity_score, *confidence),
            {"evidence_provenance": {
                "producer": "hud_analyzer", "scope": "global_system",
                "qualification_sha256": self.qualification.report_sha256,
                "profile_fingerprint": self.qualification.profile_fingerprint,
                "recognizer_fingerprint": self.qualification.recognizer_fingerprint,
                "continuity_segment": self.segment,
                "signals": ["qualified_round_result", "accepted_score_transition"],
                "pts_sec": [float(previous["time_sec"]), float(current["time_sec"])],
                "confirmation_pts_sec": float(current["time_sec"]),
            }},
        ),)

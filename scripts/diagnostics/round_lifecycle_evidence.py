"""Offline End/Buy/next-clock evidence; no decoder, GT writer or runtime hook."""
from __future__ import annotations

import argparse
import re
from fractions import Fraction
from pathlib import Path
from typing import Any

from scripts.diagnostics.round_transition_evidence import (
    _bracket,
    _score,
    _segments,
    _timer,
    _timer_conflicts,
    _witness,
    _word,
    integrate,
)
from scripts.e2e.run_dataset_case import sha256_file
from scripts.temporal_gt.contract import canonical_hash


def review_scores(packet: dict[str, Any], response: dict[str, Any]) -> dict[str, Any]:
    """Import literal screen-left/right transcription without replacing readers.

    The caller verifies the original assets against packet hashes. The human
    observes screen positions, not ally identity or qualification correctness.
    """
    if (packet.get("kind") != "DEVELOPMENT_blind_transcription_score_NOT_GT"
            or response.get("packet_sha256") != canonical_hash(packet)
            or response.get("origin") != "human"
            or not isinstance(response.get("reviewer"), str)
            or not response["reviewer"].strip()):
        raise ValueError("bound score packet and human reviewer required")
    cases, answers = packet["cases"], response["cases"]
    ids = {c["id"] for c in cases}
    if (len(ids) != len(cases) or len(answers) != len(cases)
            or {a["id"] for a in answers} != ids):
        raise ValueError("exact unique score review cases required")
    indexed = {c["id"]: c for c in cases}
    observations = []
    for a in answers:
        pair = [a.get("left_score"), a.get("right_score")]
        if (type(a.get("reviewed")) is not bool
                or any(v is not None and (type(v) is not int or not 0 <= v <= 99) for v in pair)
                or not a["reviewed"] and any(v is not None for v in pair)):
            raise ValueError("explicit review and literal Score digits required")
        c = indexed[a["id"]]
        observations.append({"case_id": c["id"], "candidate_id": c["candidate_id"],
                             "frame": _witness(c["frame"]),
                             "score": pair if a["reviewed"] and None not in pair else None,
                             "status": "OBSERVED" if a["reviewed"] and None not in pair
                             else "UNKNOWN", "reviewer": response["reviewer"],
                             "origin": "human",
                             "review_sha256": canonical_hash(response)})
    return {"observations": observations, "approved_gt": False, "formal_events": [],
            "team_ownership": "UNVERIFIED", "qualification_created": False}


def _upper(f: dict[str, Any]) -> bool:
    return f["geometry_consistent"] is True


def _human_score(f: dict[str, Any]) -> tuple[int, int] | None:
    v = f.get("human_score_observation")
    if v is None:
        return None
    pair = v.get("score")
    if (v.get("origin") != "human" or not isinstance(v.get("reviewer"), str)
            or not v["reviewer"].strip()
            or re.fullmatch(r"[0-9a-f]{64}", v.get("review_sha256", "")) is None
            or any(v.get("frame", {}).get(k) != f[k] for k in (
                "source_id", "source_sha256", "tick", "time_base", "pixel_sha256"))
            or not isinstance(pair, list) or len(pair) != 2
            or any(type(n) is not int or not 0 <= n <= 99 for n in pair)):
        raise ValueError("bound human Score observation required")
    return pair[0], pair[1]


def _repeated(frames: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep observations with a nearby same-state witness; no filled frames."""
    return [b for a, b in zip(frames, frames[1:], strict=False)
            if (b["tick"] - a["tick"]) * Fraction(b["time_base"]) <= 1]


def lifecycle(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Associate only within fully recorded native segments, retaining holes.

    Clock reset after a supported purchase countdown is a next-active display
    hypothesis, not proof of gameplay onset or an internal Round Start event.
    """
    segments, gaps = _segments(rows)
    for f in rows:
        _human_score(f)
    end_report = integrate(rows)
    chains = []
    for end in end_report["candidates"]:
        boundary = end["score_boundary"]
        segment = next(s for s in segments if s[0]["epoch"] == boundary["epoch"]
                       and s[0]["tick"] <= boundary["upper_tick"] <= s[-1]["tick"])
        tail = [f for f in segment if 0 < (f["tick"] - boundary["upper_tick"]) * (
            Fraction(f["time_base"])) <= 90]
        reasons = list(end["reasons"])
        score = tuple(end["score_after"])
        stop = next((i for i, f in enumerate(tail)
                     if _score(f) is not None and _score(f) != score), len(tail))
        score_stopped = stop < len(tail)
        tail = tail[:stop]
        score_frames = [f for f in segment if f["tick"] in (
            boundary["lower_tick"], boundary["upper_tick"])] + tail
        conflicts = [f for f in score_frames if _human_score(f) is not None
                     and _score(f) is not None and _human_score(f) != _score(f)]
        if conflicts:
            reasons.append("human_score_disagrees_with_reader")
        buy = [f for f in tail if f.get("buy_phase") is True and _upper(f)
               and _score(f) == score and (clock := _timer(f)) is not None
               and 0 <= clock <= 45 and _word(f) is None]
        repeated_buy = _repeated(buy)
        if not repeated_buy:
            reasons.append("purchase_not_observed")
        if _timer_conflicts(buy):
            reasons.append("purchase_clock_contradiction")
        active: list[dict[str, Any]] = []
        reset = None
        if repeated_buy:
            first_buy = buy[0]
            for f in tail:
                if (f["tick"] <= first_buy["tick"] or not _upper(f) or _score(f) != score
                        or f.get("buy_phase") is True
                        or (clock := _timer(f)) is None or clock < 60):
                    continue
                previous = [b for b in tail if first_buy["tick"] <= b["tick"] < f["tick"]
                            and _upper(b) and _score(b) == score
                            and (value := _timer(b)) is not None and 0 <= value <= 45]
                if not previous:
                    continue
                last = previous[-1]
                elapsed = (f["tick"] - last["tick"]) * Fraction(f["time_base"])
                # Existing timer quantization is a display interval. A reset far
                # from the last countdown is context only, not a start bracket.
                if abs(elapsed - _timer(last)) > 2:
                    continue
                if active and f["tick"] - active[-1]["tick"] > (
                        Fraction(1) / Fraction(f["time_base"])):
                    active = []
                active.append(f)
                if len(_repeated(active)):
                    reset = _bracket(last, active[0])
                    break
            if _timer_conflicts(active):
                reasons.append("next_clock_contradiction")
            if reset is None:
                reasons.append("next_active_clock_not_observed")
        if score_stopped and reset is None:
            reasons.append("score_changed_before_next_start")
        chains.append({"end_candidate_id": end["candidate_id"],
                       "status": "UNKNOWN" if reasons else "DEVELOPMENT_LIFECYCLE_CANDIDATE",
                       "reasons": sorted(set(reasons)), "end": end,
                       "buy_support_interval": _bracket(buy[0], repeated_buy[0])
                       if repeated_buy else None,
                       "buy_witnesses": [_witness(f) for f in buy],
                       "next_clock_reset_bracket": reset,
                       "next_clock_witnesses": [_witness(f) for f in active],
                       "unread_score_witnesses": [_witness(f) for f in tail if _score(f) is None],
                       "human_score_conflicts": [_witness(f) for f in conflicts],
                       "human_score_observations": [f["human_score_observation"]
                                                    for f in score_frames
                                                    if _human_score(f) is not None],
                       "purchase_onset_status": "UNVERIFIED",
                       "next_start_semantic_status": "UNVERIFIED",
                       "internal_End_tick": None, "internal_Start_tick": None,
                       "source_continuity": "UNVERIFIED", "formal_events": []})
    return {"kind": "offline_Round_lifecycle_evidence_NOT_GT", "chains": chains,
            "source_gaps": gaps, "end_report": end_report,
            "cross_epoch_association": False, "formal_events": [],
            "qualification_created": False, "approved_gt": False}


def main() -> None:
    from scripts.diagnostics.round_transition_evidence import run
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review-session", type=Path, required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    def bound(rows: list[dict[str, Any]]) -> dict[str, Any]:
        report = lifecycle(rows)
        report["lifecycle_implementation_sha256"] = sha256_file(Path(__file__))
        return report

    run(args.review_session, args.input, args.output, integrator=bound)


if __name__ == "__main__":
    main()

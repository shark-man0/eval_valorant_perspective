"""Offline End/Buy/next-clock evidence; no decoder, GT writer or runtime hook."""
from __future__ import annotations

import argparse
import re
from fractions import Fraction
from pathlib import Path
from typing import Any

from scripts.diagnostics.round_transition_evidence import (
    _bracket,
    _buy,
    _geometry,
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
    return _geometry(f, 'score') and _geometry(f, 'timer')


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



def _purchase_clock(tail: list[dict[str, Any]], score: tuple[int, ...]) -> dict[str, Any]:
    """Existing Buy/next-clock rules, also usable without a preceding End."""
    reasons: list[str] = []
    buy = [f for f in tail if _buy(f) and _upper(f)
           and _score(f) == score and (clock := _timer(f)) is not None
           and 0 <= clock <= 45 and _word(f) is None]
    repeated_buy = _repeated(buy)
    if not repeated_buy:
        reasons.append("purchase_not_observed")
    if _timer_conflicts(buy):
        reasons.append("purchase_clock_contradiction")
    active: list[dict[str, Any]] = []
    rejected_clocks: list[dict[str, Any]] = []
    reset = None
    if repeated_buy:
        first_buy = buy[0]
        for f in tail:
            if (active and _upper(f) and _score(f) == score
                    and (_buy(f)
                         or (clock := _timer(f)) is not None and clock <= 45)):
                rejected_clocks.append({"status": "UNKNOWN",
                                        "reason": "preparation_reappeared",
                                        "witnesses": [_witness(a) for a in active],
                                        "display_values": [_timer(a) for a in active],
                                        "contradiction": _bracket(active[-1], f)})
                active = []
            if (f["tick"] <= first_buy["tick"] or not _upper(f) or _score(f) != score
                    or _buy(f)
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
                rejected_clocks.append({"status": "UNKNOWN",
                                        "reason": "clock_support_gap",
                                        "witnesses": [_witness(a) for a in active],
                                        "display_values": [_timer(a) for a in active],
                                        "contradiction": _bracket(active[-1], f)})
                active = []
            if active and _timer_conflicts([active[-1], f]):
                rejected_clocks.append({"status": "UNKNOWN",
                                        "reason": "inconsistent_clock_prefix",
                                        "witnesses": [_witness(a) for a in active],
                                        "display_values": [_timer(a) for a in active],
                                        "contradiction": _bracket(active[-1], f)})
                active = []
            active.append(f)
            if len(_repeated(active)):
                reset = _bracket(last, active[0])
                break
        if reset is None and any(p["reason"] == "inconsistent_clock_prefix"
                                 for p in rejected_clocks):
            reasons.append("next_clock_contradiction")
        if reset is None:
            reasons.append("next_active_clock_not_observed")
    return {'reasons': reasons,
            'buy_support_interval': _bracket(buy[0], repeated_buy[0]) if repeated_buy else None,
            'buy_witnesses': [_witness(f) for f in buy],
            'next_clock_reset_bracket': reset,
            'next_clock_witnesses': [_witness(f) for f in active],
            'rejected_clock_prefixes': rejected_clocks}


def _purchase_windows(segments: list[list[dict[str, Any]]]) -> list[dict[str, Any]]:
    observations = []
    for segment in segments:
        score = None
        run: list[dict[str, Any]] = []
        runs = []
        for frame in segment:
            value = _score(frame)
            if value is not None and score is not None and value != score:
                runs.append((score, run))
                run = []
            if value is not None:
                score = value
            run.append(frame)
        if score is not None:
            runs.append((score, run))
        for pair, frames in runs:
            view = _purchase_clock(frames, pair)
            if not view['buy_witnesses']:
                continue
            observations.append({**view,
                'status': 'UNKNOWN' if view['reasons'] else 'DEVELOPMENT_PURCHASE_CLOCK_CANDIDATE',
                'score': pair, 'first_frame': _witness(frames[0]),
                'last_frame': _witness(frames[-1]), 'End_association_required': False,
                'start_semantic_status': 'UNVERIFIED', 'internal_Start_tick': None,
                'formal_events': []})
    return observations


def lifecycle(rows: list[dict[str, Any]], *, observed_score_brackets: bool = False,
              observed_score_persistence: bool = False,
              scoped_score_boundaries: bool = False
              ) -> dict[str, Any]:
    """Associate only within fully recorded native segments, retaining holes.

    Clock reset after a supported purchase countdown is a next-active display
    hypothesis, not proof of gameplay onset or an internal Round Start event.
    """
    segments, gaps = _segments(rows)
    for f in rows:
        _human_score(f)
    end_report = integrate(rows, observed_score_brackets=observed_score_brackets,
                           observed_score_persistence=observed_score_persistence,
                           scoped_score_boundaries=scoped_score_boundaries)
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
        purchase = _purchase_clock(tail, score)
        reasons.extend(purchase['reasons'])
        reset = purchase['next_clock_reset_bracket']
        if score_stopped and reset is None:
            reasons.append("score_changed_before_next_start")
        chains.append({"end_candidate_id": end["candidate_id"],
                       "status": "UNKNOWN" if reasons else "DEVELOPMENT_LIFECYCLE_CANDIDATE",
                       "reasons": sorted(set(reasons)), "end": end,
                       **{key: value for key, value in purchase.items() if key != 'reasons'},
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
            "purchase_next_clock_observations": _purchase_windows(segments),
            "cross_epoch_association": False, "formal_events": [],
            "qualification_created": False, "approved_gt": False}


def main() -> None:
    from scripts.diagnostics.round_transition_evidence import run
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review-session", type=Path, required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--observed-score-brackets", action="store_true")
    parser.add_argument("--observed-score-persistence", action="store_true")
    parser.add_argument("--scoped-score-boundaries", action="store_true")
    args = parser.parse_args()

    def bound(rows: list[dict[str, Any]]) -> dict[str, Any]:
        report = lifecycle(rows, observed_score_brackets=args.observed_score_brackets,
                           observed_score_persistence=args.observed_score_persistence,
                           scoped_score_boundaries=args.scoped_score_boundaries)
        report["lifecycle_implementation_sha256"] = sha256_file(Path(__file__))
        return report

    run(args.review_session, args.input, args.output, integrator=bound)


def round_timeline(reports: list[dict[str, Any]]) -> dict[str, Any]:
    """Project existing offline reports without joining their acquisitions.

    Repeated/overlapping Score-boundary hypotheses share one timeline entry.
    Evidence alternatives stay separate: a complete chain must have been
    supported inside one acquisition. No sparse sample becomes a Native bracket,
    no UNKNOWN interval becomes negative, and no internal event is generated.
    """
    entries: list[dict[str, Any]] = []
    unknown_scopes: list[dict[str, Any]] = []
    seen: set[str] = set()
    for report in reports:
        if (report.get('kind') != 'offline_Round_lifecycle_evidence_NOT_GT'
                or report.get('formal_events') != []
                or report.get('qualification_created') is not False
                or report.get('approved_gt') is not False):
            raise ValueError('offline lifecycle reports required')
        report_hash = canonical_hash(report)
        if report_hash in seen:
            continue
        seen.add(report_hash)
        for chain in report['chains']:
            end = chain['end']
            if (chain.get('formal_events') != [] or end.get('formal_events', []) != []
                    or chain.get('internal_End_tick') is not None
                    or chain.get('internal_Start_tick') is not None):
                raise ValueError('display candidates cannot contain formal or internal events')
            bracket = end['score_boundary']
            for key, witness in [('lower_tick', 'before'), ('upper_tick', 'after')]:
                if (type(bracket[key]) is not int or bracket[key] != bracket[witness]['tick']
                        or bracket['epoch'] != bracket[witness]['epoch']
                        or Fraction(bracket['time_base']) != Fraction(
                            bracket[witness]['time_base'])):
                    raise ValueError('bound Native Score bracket required')
            before, after = bracket['before'], bracket['after']
            if (before['source_id'] != after['source_id']
                    or before['source_sha256'] != after['source_sha256']
                    or bracket['lower_tick'] >= bracket['upper_tick']):
                raise ValueError('single source and increasing Native bracket required')
            base = Fraction(bracket['time_base'])
            entries.append({
                'source_id': before['source_id'], 'source_sha256': before['source_sha256'],
                'score_before': end['score_before'], 'score_after': end['score_after'],
                'interval': (bracket['lower_tick'] * base, bracket['upper_tick'] * base),
                'alternative': {'report_sha256': report_hash, 'chain': chain},
            })
        unknown_scopes.append({'report_sha256': report_hash,
                               'source_gaps': report['source_gaps'],
                               'unassociated_results': report['end_report']['orphan_result_groups'],
                               'purchase_clock': report['purchase_next_clock_observations'],
                               'unreviewed_is_negative': False})
    groups: list[list[dict[str, Any]]] = []
    entries.sort(key=lambda e: (e['source_id'], e['source_sha256'], e['interval']))
    for entry in entries:
        matching = [g for g in groups if any(
            e['source_id'] == entry['source_id']
            and e['source_sha256'] == entry['source_sha256']
            and max(e['interval'][0], entry['interval'][0]) <= min(
                e['interval'][1], entry['interval'][1]) for e in g)]
        if not matching:
            groups.append([entry])
        else:
            group = matching[0]
            for other in matching[1:]:
                group.extend(other)
                groups.remove(other)
            group.append(entry)
    timeline = []
    for group in groups:
        score_pairs = {canonical_hash([e['score_before'], e['score_after']]) for e in group}
        alternatives = [e['alternative'] for e in group]
        complete = any(a['chain']['status'] == 'DEVELOPMENT_LIFECYCLE_CANDIDATE'
                       for a in alternatives)
        conflict = len(score_pairs) > 1
        identity = {k: group[0][k] for k in ('source_id', 'source_sha256')}
        identity['intervals'] = sorted({tuple(str(v) for v in e['interval']) for e in group})
        timeline.append({
            'round_candidate_id': canonical_hash(identity),
            'source_id': group[0]['source_id'], 'source_sha256': group[0]['source_sha256'],
            'status': 'DEVELOPMENT_LIFECYCLE_CANDIDATE' if complete and not conflict else 'UNKNOWN',
            'score_conflict': conflict, 'alternatives': alternatives,
            'evidence_joined_across_acquisitions': False,
            'physical_event_id': None, 'internal_End_tick': None, 'internal_Start_tick': None,
            'semantic_correctness': 'UNVERIFIED', 'formal_events': [],
        })
    return {'kind': 'DEVELOPMENT_Round_Timeline_NOT_GT', 'round_candidates': timeline,
            'unknown_scopes': unknown_scopes,
            'duplicate_reports_suppressed': len(reports)-len(seen),
            'qualified': False, 'formal_events': [], 'approved_gt': False}


if __name__ == "__main__":
    main()

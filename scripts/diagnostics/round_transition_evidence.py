"""Offline native evidence association; never emits or times an internal End.

Unknown OCR frames remain unknown inside a supported display episode. Acquisition
and missing-frame gaps break association. No decoder, GT or production hook.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from collections import defaultdict
from collections.abc import Callable
from copy import deepcopy
from fractions import Fraction
from pathlib import Path
from typing import Any

from scripts.diagnostics.analyze_personal_candidates import development_sources
from scripts.diagnostics.diagnose_result_text import accepted_result
from scripts.diagnostics.hud_scope_structure import component_support
from scripts.diagnostics.register_private_sources import write_private
from scripts.diagnostics.score_border_background import RejectedScoreBackgroundReader
from scripts.e2e.run_dataset_case import sha256_file
from scripts.temporal_gt.contract import canonical_hash
from scripts.temporal_gt.review_session import append_exposure
from valorant_ai_coach.hud.calibrate_temporal import _check_output_privacy
from valorant_ai_coach.hud.models import accept_hud_value
from valorant_ai_coach.hud.round_lifecycle import accepted_score_pair
from valorant_ai_coach.hud.score_glyphs import StrictScoreGlyphReader
from valorant_ai_coach.hud.templates import HudTemplateProfile, SubregionReader

# Frozen offline association horizon, not a matcher threshold or GT tolerance.
ASSOCIATION_SECONDS = 6


def score_readers(
    path: Path, *, foreground: str | None = None, background_fallback: bool = False,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Preflight existing readers; any alternate mode must be explicit and bound.

    An unsupported historical experiment name never silently aliases a supported
    one. The parent bytes, templates, confidence and class margin stay unchanged.
    """
    if type(background_fallback) is not bool:
        raise ValueError('explicit boolean Score background option required')
    profile_bytes = path.read_bytes()
    parent_sha256 = hashlib.sha256(profile_bytes).hexdigest()
    raw = json.loads(profile_bytes)
    candidate = deepcopy(raw)
    roles = ("ally_score", "enemy_score")
    assets = {}
    for role in roles:
        spec = candidate.get("readers", {}).get(role, {})
        if spec.get("kind") != "strict_score_glyphs":
            raise ValueError("explicit strict Score reader required")
        if foreground is not None:
            spec["foreground_preprocessing"] = foreground
    profile = HudTemplateProfile(path, candidate)
    all_readers = profile.build_readers()
    selected: dict[str, Any] = {}
    for role in roles:
        reader = all_readers.get(role)
        inner = reader.reader if isinstance(reader, SubregionReader) else reader
        if not isinstance(inner, StrictScoreGlyphReader):
            raise ValueError("Score reader unavailable: " + "; ".join(profile.reader_diagnostics))
        if background_fallback:
            alternative = RejectedScoreBackgroundReader(inner)
            selected[role] = (SubregionReader(alternative, reader.bounds)
                              if isinstance(reader, SubregionReader) else alternative)
        else:
            selected[role] = reader
        for name in candidate["readers"][role]["templates"].values():
            asset = profile.resolve_asset(name)
            assets[str(asset)] = sha256_file(asset)
    if sha256_file(path) != parent_sha256:
        raise ValueError("parent profile changed during reader preflight")
    binding: dict[str, Any] = {"parent_profile_sha256": parent_sha256,
                      "explicit_foreground": foreground, "asset_sha256": assets,
                      "production_changed": False, "formal_events": []}
    if background_fallback:
        binding['rejected_native_background'] = True
    return selected, binding


def _text(read: dict[str, Any]) -> str | None:
    value, confidence = read.get("value"), read.get("confidence")
    if (not isinstance(value, str) or not isinstance(confidence, (int, float))
            or isinstance(confidence, bool)
            or not math.isfinite(confidence) or not .90 <= confidence <= 1):
        return None
    return str(accept_hud_value(value, confidence))


def _score(f: dict[str, Any]) -> tuple[int, int] | None:
    texts = [_text(f[n]) for n in ("ally_score", "enemy_score")]
    values = [int(t) if t is not None and re.fullmatch(r"(?:0|[1-9][0-9]?)", t)
              else None for t in texts]
    values_by_role = dict(zip(("score_ally", "score_enemy"), values, strict=True))
    return accepted_score_pair({"values": values_by_role})


def _buy(frame: dict[str, Any]) -> bool:
    from scripts.diagnostics.phase_structure_evidence import phase_supported
    structural = phase_supported(frame)
    return frame.get("buy_phase") is True or structural


def _timer(f: dict[str, Any]) -> int | None:
    text = _text(f["timer"])
    if text is None or re.fullmatch(r"[0-9]{1,2}:[0-5][0-9]", text) is None:
        return None
    minutes, seconds = map(int, text.split(":"))
    return 60 * minutes + seconds


def _word(f: dict[str, Any]) -> str | None:
    return accepted_result(f["result"].get("value"), f["result"].get("confidence", 0))


def _end_timer(f: dict[str, Any]) -> tuple[Fraction, Fraction, str] | None:
    """Literal display and quantization; decimals never feed Buy/Start logic."""
    if not _geometry(f, 'timer'):
        return None
    colon = _timer(f)
    if colon is not None:
        return Fraction(colon), Fraction(1), 'MINUTES_SECONDS'
    text = _text(f['timer'])
    sources = f['timer'].get('sources', [])
    if (text is not None and re.fullmatch(r'[0-9]{2}\.[0-9]{2}', text)
            and isinstance(sources, (list,tuple))
            and 'offline_timer_seconds_hundredths_v1' in sources):
        return Fraction(text), Fraction(1, 100), 'SECONDS_HUNDREDTHS'
    return None


def _end_timer_diagnostics(frames: list[dict[str, Any]]) -> dict[str, Any]:
    reads = [(f, v) for f in frames if (v := _end_timer(f)) is not None]
    conflicts, changes = [], []
    for (a, before), (b, after) in zip(reads, reads[1:], strict=False):
        if before[2] != after[2]:
            changes.append({**_bracket(a,b), 'before_format': before[2],
                            'after_format': after[2]})
            continue
        elapsed = (b['tick']-a['tick'])*Fraction(b['time_base'])
        if not 0 <= before[0]-after[0] <= elapsed+max(before[1],after[1]):
            conflicts.append(_bracket(a,b))
    return {'reads': reads, 'conflicts': conflicts, 'changes': changes}


def _witness(f: dict[str, Any]) -> dict[str, Any]:
    return {k: f[k] for k in ("source_id", "source_sha256", "tick", "time_base", "epoch",
                              "encoded_sha256", "pixel_sha256")}


def _geometry(f: dict[str, Any], role: str) -> bool:
    # Global geometry is never rewritten; Round-only component evidence is an
    # explicit, source/profile-bound alternative for this particular ROI.
    local = component_support(f, role)
    return f['geometry_consistent'] is True or local


def _bracket(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    return {"lower_tick": a["tick"], "upper_tick": b["tick"],
            "time_base": b["time_base"], "epoch": b["epoch"],
            "before": _witness(a), "after": _witness(b)}


def _visual(f: dict[str, Any]) -> dict[str, Any] | None:
    """Optional reviewed display observation, separate from reader support/GT.

    The caller must retain the review receipt and bind it to this frame's hashes.
    An unread OCR value must never be converted into a NONE observation.
    """
    v = f.get("visual_result")
    if v is None:
        return None
    if (not isinstance(v, dict) or v.get("state") not in {"NONE", "PARTIAL", "COMPLETE", "UNKNOWN"}
            or v.get("origin") != "human" or not isinstance(v.get("reviewer"), str)
            or not v["reviewer"] or not isinstance(v.get("review_sha256"), str)
            or re.fullmatch(r"[0-9a-f]{64}", v["review_sha256"]) is None
            or (v.get("word") is not None and accepted_result(v["word"], 1) is None)
            or (v["state"] == "NONE" and v.get("word") is not None)):
        raise ValueError("invalid visual Result provenance")
    return v


def _timer_conflicts(frames: list[dict[str, Any]]) -> list[dict[str, Any]]:
    timers = [f for f in frames if _timer(f) is not None]
    conflicts = []
    for before, after in zip(timers, timers[1:], strict=False):
        earlier, later = _timer(before), _timer(after)
        assert earlier is not None and later is not None
        elapsed = (after["tick"] - before["tick"]) * Fraction(after["time_base"])
        if not 0 <= earlier - later <= elapsed + 1:
            conflicts.append(_bracket(before, after))
    return conflicts


def _segments(
    rows: list[dict[str, Any]],
) -> tuple[list[list[dict[str, Any]]], list[dict[str, Any]]]:
    if not rows:
        return [], []
    sources = set()
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for f in rows:
        try:
            base = Fraction(f["time_base"])
            if (not isinstance(f["time_base"], str) or base <= 0
                    or type(f["tick"]) is not int or f["tick"] < 0
                    or type(f["expected_step_ticks"]) is not int
                    or f["expected_step_ticks"] <= 0
                    or not isinstance(f["epoch"], str) or not f["epoch"]
                    or not isinstance(f["source_id"], str) or not f["source_id"]
                    or type(f["geometry_consistent"]) is not bool):
                raise ValueError("invalid native evidence binding")
            for key in ("source_sha256", "encoded_sha256", "pixel_sha256"):
                if not isinstance(f[key], str) or re.fullmatch(r"[0-9a-f]{64}", f[key]) is None:
                    raise ValueError("invalid native evidence hash")
            for key in ("ally_score", "enemy_score", "timer", "result"):
                if not isinstance(f[key], dict):
                    raise ValueError("reader evidence mapping required")
            _visual(f)
            component_support(f, 'score')
            _buy(f)  # validate explicit purchase receipts even without a candidate
            sources.add((f["source_id"], f["source_sha256"], base))
            groups[f["epoch"]].append(f)
        except (KeyError, TypeError, ZeroDivisionError) as exc:
            raise ValueError("invalid native evidence binding") from exc
    if len(sources) != 1:
        raise ValueError("one source and native timebase required")
    segments, gaps = [], []
    for frames in groups.values():
        frames = sorted(frames, key=lambda f: f["tick"])
        bindings = {canonical_hash(f['component_geometry']['bindings']) for f in frames
                    if f.get('component_geometry') is not None}
        if len(bindings) > 1:
            raise ValueError('component profile changed within acquisition')
        segment: list[dict[str, Any]] = []
        for f in frames:
            if segment:
                a = segment[-1]
                delta = f["tick"] - a["tick"]
                if delta == 0:
                    raise ValueError("duplicate native PTS in one acquisition")
                if (delta != a["expected_step_ticks"]
                        or f["expected_step_ticks"] != a["expected_step_ticks"]
                        or f.get("discontinuity") is True):
                    gaps.append({**_bracket(a, f), "status": "UNKNOWN",
                                 "reason": "native_gap_or_discontinuity"})
                    segments.append(segment)
                    segment = []
            segment.append(f)
        if segment:
            segments.append(segment)
    return segments, gaps


def _candidate(segment: list[dict[str, Any]], index: int,
               before_index: int | None = None, *,
               observed_persistence: bool = False) -> dict[str, Any]:
    before_index = index - 1 if before_index is None else before_index
    a, b = segment[before_index], segment[index]
    base = Fraction(b["time_base"])
    # Do not combine evidence from another score transition in the same window.
    end = index + 1
    score_conflicts = []
    while end < len(segment):
        f = segment[end]
        score = _score(f)
        if (f["tick"] - b["tick"]) * base > ASSOCIATION_SECONDS:
            break
        if score is not None and score != _score(b):
            score_conflicts.append(_witness(f))
            break
        end += 1
    # Walk backward only through the same observed pre-change score. Unknown
    # scores and native segment boundaries are barriers, never interpolation.
    start = before_index
    while start > 0:
        f = segment[start - 1]
        if ((b["tick"] - f["tick"]) * base > ASSOCIATION_SECONDS
                or _score(f) != _score(a)):
            break
        start -= 1
    window = segment[start:end]
    raw_support = [f for f in window if _word(f)]
    support = [f for f in raw_support if _geometry(f, 'result') and _geometry(f, 'score')
               and _score(f) == _score(a if f["tick"] < b["tick"] else b)]
    unknown_word_scores = [f for f in raw_support if _score(f) is None]
    words = sorted({word for f in raw_support if (word := _word(f)) is not None})
    reasons = ["conflicting_score_observation"] if score_conflicts else []
    unread_bracket = segment[before_index + 1:index]
    if any(_word(f) is not None or _visual(f) is not None for f in unread_bracket):
        reasons.append("result_inside_unread_score_bracket")
    if len(words) > 1:
        reasons.append("conflicting_result_words")
    before_score, after_score = _score(a), _score(b)
    assert before_score is not None and after_score is not None
    if (("WON" in words and after_score[0] != before_score[0] + 1)
            or ("LOST" in words and after_score[1] != before_score[1] + 1)):
        reasons.append("result_score_direction_conflict")
    if len(support) < 2:
        reasons.append("insufficient_result_support")
    if unknown_word_scores and len(support) < 2:
        reasons.append("result_score_unknown")
    if not _geometry(a, 'score') or not _geometry(b, 'score'):
        reasons.append("score_geometry_unknown")
    # Score flicker must not become an End merely because Result is nearby.
    stable_before = before_index >= 1 and _score(segment[before_index - 1]) == _score(a)
    stable_after = index + 1 < len(segment) and _score(segment[index + 1]) == _score(b)
    persistence_witnesses: dict[str, list[dict[str, Any]]] = {'before': [], 'after': []}
    if observed_persistence:
        for role, values, anchor, expected in (
            ('before', list(reversed(segment[:before_index])), a, _score(a)),
            ('after', segment[index+1:], b, _score(b)),
        ):
            if (stable_before if role == 'before' else stable_after):
                continue
            nearest = next((f for f in values if _score(f) is not None), None)
            if (nearest is not None and _score(nearest) == expected
                    and abs(nearest['tick']-anchor['tick']) * base <= 1
                    and _geometry(nearest, 'score') and _geometry(anchor, 'score')):
                persistence_witnesses[role] = [_witness(nearest), _witness(anchor)]
                if role == 'before':
                    stable_before = True
                else:
                    stable_after = True
    if not stable_before or not stable_after:
        reasons.append('score_persistence_unverified')
    pre_support = [f for f in raw_support if f["tick"] < b["tick"]]
    post_support = [f for f in raw_support if f["tick"] >= b["tick"]]
    # A word already present before Score may be an older residual banner.
    # OCR failure is not verified absence, so require a retained human NONE
    # witness before the first pre-score word; no condition is relaxed here.
    if pre_support and not any(
        f["tick"] < pre_support[0]["tick"] and (v := _visual(f)) and v["state"] == "NONE"
        for f in window
    ):
        reasons.append("pre_result_onset_unverified")
    visual = []
    partial_brackets = []
    last_clear = None
    for f in window:
        v = _visual(f)
        if v is None:
            continue
        consistent_word = v.get("word") is not None and v["word"] in words
        association = "MATCHING_CONTENT" if consistent_word else "UNKNOWN_CONTENT"
        if v["state"] == "NONE":
            association = "CLEARANCE_CONTEXT"
            last_clear = f
            if _word(f) is not None:
                reasons.append("visual_result_conflicts_with_reader")
        elif v.get("word") is not None and words and not consistent_word:
            reasons.append("visual_result_conflicts_with_reader")
        if v["state"] == "PARTIAL" and last_clear is not None:
            partial_brackets.append({**_bracket(last_clear, f),
                                     "meaning": "reviewed NONE to PARTIAL; onset may be earlier",
                                     "content_status": association})
            last_clear = None
        visual.append({**_witness(f), **v, "association": association})
    visible = raw_support + [f for f in window if (v := _visual(f))
                             and v["state"] in {"PARTIAL", "COMPLETE"}]
    first_tick = min((f["tick"] for f in visible), default=b["tick"])
    last = max((f["tick"] for f in visible), default=b["tick"])
    if any(_buy(f) for f in window
           if min(first_tick, a["tick"]) <= f["tick"] <= max(last, b["tick"])):
        reasons.append("preparation_overlaps_result")
    # A legitimate clock change across Score is recorded separately. Neither
    # its direction nor a clock reset alone proves an End or a next Round.
    timer_end = max(last, segment[min(index + 1, len(segment) - 1)]["tick"])
    after_frames = [f for f in window if b["tick"] <= f["tick"] <= timer_end]
    after_timers = _end_timer_diagnostics(after_frames)
    pre_timers = _end_timer_diagnostics(
        [f for f in window if first_tick <= f['tick'] < b['tick']])
    timers = after_timers['reads']
    timer_conflicts = after_timers['conflicts'] + pre_timers['conflicts']
    before_timer, after_timer = _timer(a), _timer(b)
    if before_timer is not None and after_timer is not None and after_timer > before_timer:
        timer_conflicts.append(_bracket(a, b))
        reasons.append("timer_reset_at_score_boundary")
    before_display, after_display = _end_timer(a), _end_timer(b)
    if (before_display is not None and after_display is not None
            and before_display[2] != after_display[2]):
        after_timers['changes'].append({**_bracket(a,b),
                                       'before_format': before_display[2],
                                       'after_format': after_display[2]})
    if (before_display is not None and after_display is not None
            and before_display[2] == after_display[2] == 'SECONDS_HUNDREDTHS'
            and after_display[0] > before_display[0]):
        timer_conflicts.append(_bracket(a,b))
        reasons.append('timer_reset_at_score_boundary')
    repeated_format = any(sum(v[2] == fmt for _,v in timers) >= 2
                          for fmt in ('MINUTES_SECONDS','SECONDS_HUNDREDTHS'))
    if timer_conflicts:
        reasons.append("timer_contradiction")
    elif not repeated_format:
        reasons.append("timer_unknown")
    score_boundary = _bracket(a, b)
    first = raw_support[0] if raw_support else None
    first_index = segment.index(first) if first else None
    bracket = (_bracket(segment[first_index - 1], first)
               if first is not None and first_index is not None and first_index > 0 else None)
    unknown_ticks = [f["tick"] for f in window if raw_support
                     and raw_support[0]["tick"] < f["tick"] < raw_support[-1]["tick"]
                     and _word(f) is None]
    key = json.dumps([b["source_sha256"], str(base), a["tick"], b["tick"], _score(b)])
    return {"candidate_id": hashlib.sha256(key.encode("utf-8")).hexdigest(),
            "status": "UNKNOWN" if reasons else "DEVELOPMENT_TRANSITION_CANDIDATE",
            "reasons": reasons, "score_boundary": score_boundary,
            "score_before": _score(a), "score_after": _score(b),
            "score_boundary_kind": "OBSERVED_INTERVAL_WITH_UNREAD_FRAMES" if unread_bracket
            else "ADJACENT_NATIVE_OBSERVATIONS",
            "unread_score_boundary_witnesses": [_witness(f) for f in unread_bracket],
            "score_conflicts": score_conflicts,
            "result_order": ("BOTH_SIDES" if pre_support and post_support else
                             "BEFORE_SCORE" if pre_support else
                             "AFTER_SCORE" if post_support else "UNOBSERVED"),
            "result_before_score_ticks": [f["tick"] for f in pre_support],
            "result_after_score_ticks": [f["tick"] for f in post_support],
            "visual_result_observations": visual,
            "partial_display_brackets": partial_brackets,
            "score_persistence": {"before": stable_before, "after": stable_after},
            "observed_score_persistence_witnesses": persistence_witnesses,
            "score_endpoint_timer_values": [_timer(a), _timer(b)],
            "result_words": words, "result_support_ticks": [f["tick"] for f in support],
            "unread_result_ticks_between_support": unknown_ticks,
            "result_support_witnesses": [_witness(f) for f in support],
            "raw_result_witnesses": [_witness(f) for f in raw_support],
            "geometry_rejected_word_observations": sum(
                not (_geometry(f, 'result') and _geometry(f, 'score')) for f in raw_support),
            "unknown_score_word_observations": [
                {**_witness(f), "status": "UNKNOWN", "reason": "result_score_unknown"}
                for f in unknown_word_scores],
            "first_word_bracket": bracket,
            "timer_status": "CONTRADICTORY" if timer_conflicts else (
                "CONSISTENT" if repeated_format else "UNKNOWN"),
            "timer_conflicts": timer_conflicts, "timer_observation_count": len(timers),
            "timer_observation_formats": sorted({v[2] for _, v in timers}),
            "timer_format_changes": after_timers['changes'] + pre_timers['changes'],
            "timer_display_observations": [
                {**_witness(f), 'display': _text(f['timer']), 'format': v[2],
                 'quantization_seconds': str(v[1])} for f,v in timers],
            "complete_display_status": "UNVERIFIED", "internal_End_tick": None,
            "physical_event_id": None, "source_continuity": "UNVERIFIED",
            "acquisitions": [{"epoch": b["epoch"], "score_boundary": score_boundary,
                              "raw_result_witnesses": [_witness(f) for f in raw_support],
                              "visual_result_observations": visual}],
            "formal_events": []}


def integrate(rows: list[dict[str, Any]], *, observed_score_brackets: bool = False,
              observed_score_persistence: bool = False
              ) -> dict[str, Any]:
    if type(observed_score_brackets) is not bool:
        raise ValueError('explicit observed Score bracket option required')
    if (type(observed_score_persistence) is not bool
            or observed_score_persistence and not observed_score_brackets):
        raise ValueError('explicit bounded Score observation policy required')
    segments, gaps = _segments(rows)
    candidates: dict[str, dict[str, Any]] = {}
    covered: set[tuple[str, int]] = set()
    for segment in segments:
        previous_read = 0
        for i in range(1, len(segment)):
            left = previous_read if observed_score_brackets else i - 1
            before, after = _score(segment[left]), _score(segment[i])
            if after is not None:
                previous_read = i
            if (observed_score_brackets
                    and (segment[i]['tick'] - segment[left]['tick']) * Fraction(
                        segment[i]['time_base']) > 1):
                continue
            if before is None or after is None or sorted(
                y - x for x, y in zip(before, after, strict=True)
            ) != [0, 1]:
                continue
            c = _candidate(segment, i, left,
                           observed_persistence=observed_score_persistence)
            covered.update((f["epoch"], f["tick"]) for f in c["raw_result_witnesses"])
            if c["candidate_id"] in candidates:
                existing = candidates[c["candidate_id"]]
                if (existing["status"] != c["status"]
                        or existing["result_words"] != c["result_words"]
                        or existing["result_support_ticks"] != c["result_support_ticks"]
                        or existing["timer_status"] != c["timer_status"]):
                    existing["status"] = "UNKNOWN"
                    existing["reasons"].append("acquisition_replay_disagrees")
                existing["acquisitions"].extend(c["acquisitions"])
            else:
                candidates[c["candidate_id"]] = c
    owners: dict[tuple[str, int], set[str]] = defaultdict(set)
    for key, c in candidates.items():
        for f in c["raw_result_witnesses"]:
            owners[(f["epoch"], f["tick"])].add(key)
    for keys in owners.values():
        if len(keys) > 1:
            for key in keys:
                c = candidates[key]
                c["status"] = "UNKNOWN"
                reason = "result_shared_between_score_boundaries"
                if reason not in c["reasons"]:
                    c["reasons"].append(reason)
    orphan_groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for f in rows:
        word = _word(f)
        if word and (f["epoch"], f["tick"]) not in covered:
            orphan_groups[(f["epoch"], word)].append(f)
    orphans = [{"status": "UNKNOWN", "reason": "word_without_native_multicue_boundary",
                "word": key[1], "witnesses": [_witness(f) for f in frames]}
               for key, frames in orphan_groups.items()]
    return {"kind": "offline_Round_transition_evidence_NOT_GT",
            "association_horizon_sec": ASSOCIATION_SECONDS,
            "observation_policy": {"observed_score_brackets": observed_score_brackets,
                                   "observed_score_persistence": observed_score_persistence},
            "candidates": list(candidates.values()), "orphan_result_groups": orphans,
            "source_gaps": gaps, "complete_display_status": "UNVERIFIED",
            "acquisition_epochs": sorted({f["epoch"] for f in rows}),
            "cross_epoch_association": False,
            "formal_events": [], "qualification_created": False, "approved_gt": False}


def run(session: Path, input_path: Path, output: Path, *,
        integrator: Callable[[list[dict[str, Any]]], dict[str, Any]] = integrate,
        ) -> dict[str, Any]:
    _check_output_privacy(output.resolve())
    before = sha256_file(input_path)
    raw = json.loads(input_path.read_bytes())
    sources = development_sources(session)
    if not any(s["video_id"] == raw["source_id"]
               and s["source_sha256"] == raw["source_sha256"] for s in sources):
        raise ValueError("DEVELOPMENT source binding required")
    if any(f["source_id"] != raw["source_id"]
           or f["source_sha256"] != raw["source_sha256"] for f in raw["rows"]):
        raise ValueError("frame source differs from declared source")
    report = integrator(raw["rows"])
    if sha256_file(input_path) != before:
        raise ValueError("input evidence changed")
    report.update(input_sha256=before, implementation_sha256=sha256_file(Path(__file__)))
    write_private(output, report)
    append_exposure(
        session, "prediction", output,
        "Offline native Round evidence association; no GT, event or qualification created.",
        source_id=raw["source_id"],
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ("review-session", "input", "output"):
        parser.add_argument("--" + key, type=Path, required=True)
    parser.add_argument("--observed-score-brackets", action="store_true")
    parser.add_argument("--observed-score-persistence", action="store_true")
    args = parser.parse_args()
    report = run(args.review_session, args.input, args.output,
                 integrator=lambda rows: integrate(
                     rows, observed_score_brackets=args.observed_score_brackets,
                     observed_score_persistence=args.observed_score_persistence))
    print(json.dumps({"candidates": len(report["candidates"]), "events_emitted": 0}))


if __name__ == "__main__":
    main()

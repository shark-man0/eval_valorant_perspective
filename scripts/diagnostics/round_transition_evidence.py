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
from copy import deepcopy
from fractions import Fraction
from pathlib import Path
from typing import Any

from scripts.diagnostics.analyze_personal_candidates import development_sources
from scripts.diagnostics.diagnose_result_text import accepted_result
from scripts.diagnostics.register_private_sources import write_private
from scripts.e2e.run_dataset_case import sha256_file
from scripts.temporal_gt.review_session import append_exposure
from valorant_ai_coach.hud.calibrate_temporal import _check_output_privacy
from valorant_ai_coach.hud.models import accept_hud_value
from valorant_ai_coach.hud.round_lifecycle import accepted_score_pair
from valorant_ai_coach.hud.score_glyphs import StrictScoreGlyphReader
from valorant_ai_coach.hud.templates import HudTemplateProfile, SubregionReader

# Frozen offline association horizon, not a matcher threshold or GT tolerance.
ASSOCIATION_SECONDS = 6


def score_readers(
    path: Path, *, foreground: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Preflight existing readers; any alternate mode must be explicit and bound.

    An unsupported historical experiment name never silently aliases a supported
    one. The parent bytes, templates, confidence and class margin stay unchanged.
    """
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
    selected = {}
    for role in roles:
        reader = all_readers.get(role)
        inner = reader.reader if isinstance(reader, SubregionReader) else reader
        if not isinstance(inner, StrictScoreGlyphReader):
            raise ValueError("Score reader unavailable: " + "; ".join(profile.reader_diagnostics))
        selected[role] = reader
        for name in candidate["readers"][role]["templates"].values():
            asset = profile.resolve_asset(name)
            assets[str(asset)] = sha256_file(asset)
    if sha256_file(path) != parent_sha256:
        raise ValueError("parent profile changed during reader preflight")
    return selected, {"parent_profile_sha256": parent_sha256,
                      "explicit_foreground": foreground, "asset_sha256": assets,
                      "production_changed": False, "formal_events": []}


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


def _timer(f: dict[str, Any]) -> int | None:
    text = _text(f["timer"])
    if text is None or re.fullmatch(r"[0-9]{1,2}:[0-5][0-9]", text) is None:
        return None
    minutes, seconds = map(int, text.split(":"))
    return 60 * minutes + seconds


def _word(f: dict[str, Any]) -> str | None:
    return accepted_result(f["result"].get("value"), f["result"].get("confidence", 0))


def _witness(f: dict[str, Any]) -> dict[str, Any]:
    return {k: f[k] for k in ("source_id", "source_sha256", "tick", "time_base", "epoch",
                              "encoded_sha256", "pixel_sha256")}


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
            sources.add((f["source_id"], f["source_sha256"], base))
            groups[f["epoch"]].append(f)
        except (KeyError, TypeError, ZeroDivisionError) as exc:
            raise ValueError("invalid native evidence binding") from exc
    if len(sources) != 1:
        raise ValueError("one source and native timebase required")
    segments, gaps = [], []
    for frames in groups.values():
        frames = sorted(frames, key=lambda f: f["tick"])
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


def _candidate(segment: list[dict[str, Any]], index: int) -> dict[str, Any]:
    a, b = segment[index - 1:index + 1]
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
    start = index - 1
    while start > 0:
        f = segment[start - 1]
        if ((b["tick"] - f["tick"]) * base > ASSOCIATION_SECONDS
                or _score(f) != _score(a)):
            break
        start -= 1
    window = segment[start:end]
    raw_support = [f for f in window if _word(f)]
    support = [f for f in raw_support if f["geometry_consistent"]
               and _score(f) == _score(a if f["tick"] < b["tick"] else b)]
    unknown_word_scores = [f for f in raw_support if _score(f) is None]
    words = sorted({word for f in raw_support if (word := _word(f)) is not None})
    reasons = ["conflicting_score_observation"] if score_conflicts else []
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
    if not a["geometry_consistent"] or not b["geometry_consistent"]:
        reasons.append("score_geometry_unknown")
    # Score flicker must not become an End merely because Result is nearby.
    stable_before = index >= 2 and _score(segment[index - 2]) == _score(a)
    stable_after = index + 1 < len(segment) and _score(segment[index + 1]) == _score(b)
    if not stable_before or not stable_after:
        reasons.append("score_persistence_unverified")
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
    if any(f.get("buy_phase") is True for f in window
           if min(first_tick, a["tick"]) <= f["tick"] <= max(last, b["tick"])):
        reasons.append("preparation_overlaps_result")
    # A legitimate clock change across Score is recorded separately. Neither
    # its direction nor a clock reset alone proves an End or a next Round.
    timer_end = max(last, segment[min(index + 1, len(segment) - 1)]["tick"])
    after_frames = [f for f in window if b["tick"] <= f["tick"] <= timer_end]
    timers = [f for f in after_frames if _timer(f) is not None]
    timer_conflicts = _timer_conflicts(after_frames) + _timer_conflicts(
        [f for f in window if first_tick <= f["tick"] < b["tick"]])
    before_timer, after_timer = _timer(a), _timer(b)
    if before_timer is not None and after_timer is not None and after_timer > before_timer:
        timer_conflicts.append(_bracket(a, b))
        reasons.append("timer_reset_at_score_boundary")
    if timer_conflicts:
        reasons.append("timer_contradiction")
    elif len(timers) < 2:
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
            "score_conflicts": score_conflicts,
            "result_order": ("BOTH_SIDES" if pre_support and post_support else
                             "BEFORE_SCORE" if pre_support else
                             "AFTER_SCORE" if post_support else "UNOBSERVED"),
            "result_before_score_ticks": [f["tick"] for f in pre_support],
            "result_after_score_ticks": [f["tick"] for f in post_support],
            "visual_result_observations": visual,
            "partial_display_brackets": partial_brackets,
            "score_persistence": {"before": stable_before, "after": stable_after},
            "score_endpoint_timer_values": [_timer(a), _timer(b)],
            "result_words": words, "result_support_ticks": [f["tick"] for f in support],
            "unread_result_ticks_between_support": unknown_ticks,
            "result_support_witnesses": [_witness(f) for f in support],
            "raw_result_witnesses": [_witness(f) for f in raw_support],
            "geometry_rejected_word_observations": sum(
                not f["geometry_consistent"] for f in raw_support),
            "unknown_score_word_observations": [
                {**_witness(f), "status": "UNKNOWN", "reason": "result_score_unknown"}
                for f in unknown_word_scores],
            "first_word_bracket": bracket,
            "timer_status": "CONTRADICTORY" if timer_conflicts else (
                "CONSISTENT" if len(timers) >= 2 else "UNKNOWN"),
            "timer_conflicts": timer_conflicts, "timer_observation_count": len(timers),
            "complete_display_status": "UNVERIFIED", "internal_End_tick": None,
            "physical_event_id": None, "source_continuity": "UNVERIFIED",
            "acquisitions": [{"epoch": b["epoch"], "score_boundary": score_boundary,
                              "raw_result_witnesses": [_witness(f) for f in raw_support],
                              "visual_result_observations": visual}],
            "formal_events": []}


def integrate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    segments, gaps = _segments(rows)
    candidates: dict[str, dict[str, Any]] = {}
    covered: set[tuple[str, int]] = set()
    for segment in segments:
        for i in range(1, len(segment)):
            before, after = _score(segment[i - 1]), _score(segment[i])
            if before is None or after is None or sorted(
                y - x for x, y in zip(before, after, strict=True)
            ) != [0, 1]:
                continue
            c = _candidate(segment, i)
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
            "candidates": list(candidates.values()), "orphan_result_groups": orphans,
            "source_gaps": gaps, "complete_display_status": "UNVERIFIED",
            "acquisition_epochs": sorted({f["epoch"] for f in rows}),
            "cross_epoch_association": False,
            "formal_events": [], "qualification_created": False, "approved_gt": False}


def run(session: Path, input_path: Path, output: Path) -> dict[str, Any]:
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
    report = integrate(raw["rows"])
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
    args = parser.parse_args()
    report = run(args.review_session, args.input, args.output)
    print(json.dumps({"candidates": len(report["candidates"]), "events_emitted": 0}))


if __name__ == "__main__":
    main()

"""Exact observed-frame associations to offline lifecycle candidates, never rounds.

No timestamp proximity, interval filling or cross-epoch continuity is inferred.
HUD producers keep their own contracts; callers supply explicit witness rows.
"""

from __future__ import annotations

import re
from collections import Counter
from fractions import Fraction
from typing import Any


def _native_key(row: dict[str, Any], *, map_row: bool) -> tuple[Any, ...] | None:
    names = (("native_pts_tick", "native_time_base", "native_epoch",
              "acquired_frame_sha256", "native_pixel_sha256") if map_row else
             ("tick", "time_base", "epoch", "encoded_sha256", "pixel_sha256"))
    tick, base, epoch, encoded, pixels = (row.get(n) for n in names)
    source, source_sha = row.get("source_id"), row.get("source_sha256")
    if (not isinstance(source, str) or not source or not isinstance(epoch, str) or not epoch
            or not isinstance(tick, int) or isinstance(tick, bool) or tick < 0
            or any(not isinstance(s, str) or re.fullmatch(r"[0-9a-f]{64}", s) is None
                   for s in (source_sha, encoded, pixels)) or not isinstance(base, str)):
        return None
    try:
        time_base = Fraction(base)
    except (ValueError, ZeroDivisionError):
        return None
    if time_base <= 0:
        return None
    return source, source_sha, tick, time_base, epoch, encoded, pixels


def associate_lifecycle_witnesses(
    records: list[dict[str, Any]], witnesses: list[dict[str, Any]],
) -> dict[str, Any]:
    """Associate only identical native observations, with no ownership promotion.

    Witnesses require lifecycle_candidate_id and phase_candidate strings, native
    frame identity, development_only qualification, UNKNOWN ownership. Several
    candidate/phase claims for one native frame remain ambiguous. No matching
    observation means UNKNOWN, including different acquisitions of the same PTS.
    """
    index: dict[tuple[Any, ...], set[tuple[str, str]]] = {}
    for witness in witnesses:
        key = _native_key(witness, map_row=False)
        candidate, phase = witness.get("lifecycle_candidate_id"), witness.get("phase_candidate")
        if (key is None or witness.get("qualification") != "development_only"
                or witness.get("ownership") != "UNKNOWN"
                or not isinstance(candidate, str) or not candidate
                or not isinstance(phase, str) or not phase):
            raise ValueError("Explicit development lifecycle candidate and native witness required")
        index.setdefault(key, set()).add((candidate, phase))
    associations = []
    reasons: Counter[str] = Counter()
    for ordinal, record in enumerate(records):
        if (record.get("qualification") != "development_only"
                or record.get("ownership", {}).get("identity") != "UNKNOWN"
                or record.get("formal_self_position_fact") is not None):
            raise ValueError("UNKNOWN development Map observations required")
        key = _native_key(record, map_row=True)
        matches = index.get(key, set()) if key is not None else set()
        reason = ("native_identity_unavailable" if key is None else
                  "no_identical_native_witness" if not matches else
                  "ambiguous_lifecycle_witness" if len(matches) > 1 else
                  "identical_native_observation")
        reasons[reason] += 1
        link = next(iter(matches)) if len(matches) == 1 else (None, None)
        associations.append({"observation_index": ordinal, "reason": reason,
                             "lifecycle_candidate_id": link[0], "phase_candidate": link[1],
                             "round_id": None, "ownership": "UNKNOWN",
                             "qualification": "development_only"})
    return {"qualification": "development_only", "ownership": "UNKNOWN",
            "association_scope": "identical_observation_only", "associations": associations,
            "reasons": dict(reasons), "formal_events": [], "qualification_created": False}

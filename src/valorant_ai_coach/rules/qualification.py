"""Promotion conditions from development candidates to formal Facts/Events.

A producer (a reader or detector feeding the rules) may become ``qualified``
only when all of the following hold; until then its outputs stay development
candidates and ``formal_outputs`` stays 0.

1. Reviewed precision on recordings outside TRAIN: the Wilson 95 % lower bound
   is at least ``MIN_PRECISION_LOWER`` over at least ``MIN_REVIEWED`` reviewed
   outputs.
2. Coverage (or recall, for event detectors) is measured and at least
   ``MIN_COVERAGE``.
3. The same measurement on INDEPENDENT_TEST recordings (registered as unexposed,
   see the continual-learning registry) covers at least ``MIN_INDEPENDENT``
   matches and also meets 1 and 2.
4. A named approval is recorded.

``config/producer_qualification_v1.json`` records the evidence per producer;
``qualification`` evaluates it. It never marks anything qualified by itself.
"""

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from pathlib import Path
from typing import Any

MIN_REVIEWED = 100
MIN_PRECISION_LOWER = 0.95
MIN_COVERAGE = 0.5
MIN_INDEPENDENT = 5
Z95 = 1.96


def wilson_lower(correct: int, total: int, z: float = Z95) -> float:
    if total <= 0:
        return 0.0
    phat = correct / total
    denom = 1 + z * z / total
    centre = phat + z * z / (2 * total)
    margin = z * math.sqrt(phat * (1 - phat) / total + z * z / (4 * total * total))
    return (centre - margin) / denom


def _check(evidence: Mapping[str, Any] | None) -> list[str]:
    if not evidence:
        return ["no reviewed evidence"]
    gaps = []
    total, correct = int(evidence.get("reviewed", 0)), int(evidence.get("correct", 0))
    if total < MIN_REVIEWED:
        gaps.append(f"reviewed {total} < {MIN_REVIEWED}")
    lower = wilson_lower(correct, total)
    if lower < MIN_PRECISION_LOWER:
        gaps.append(f"precision lower bound {lower:.3f} < {MIN_PRECISION_LOWER}")
    coverage = evidence.get("coverage")
    if coverage is None or float(coverage) < MIN_COVERAGE:
        gaps.append(f"coverage {coverage} < {MIN_COVERAGE}")
    return gaps


def qualification(entry: Mapping[str, Any]) -> dict[str, Any]:
    """Which promotion conditions an evidence entry still misses."""
    development = _check(entry.get("development"))
    independent_entry = entry.get("independent") or {}
    independent = (_check(independent_entry) if independent_entry
                   else ["no INDEPENDENT_TEST evidence"])
    if int(independent_entry.get("matches", 0)) < MIN_INDEPENDENT:
        independent.append(f"independent matches {independent_entry.get('matches', 0)}"
                           f" < {MIN_INDEPENDENT}")
    approval = [] if str(entry.get("approval") or "").strip() else ["no approval recorded"]
    missing = ([f"development: {g}" for g in development]
               + [f"independent: {g}" for g in independent] + approval)
    dev = entry.get("development") or {}
    return {
        "qualified": not missing,
        "missing": missing,
        "development_precision_lower": round(
            wilson_lower(int(dev.get("correct", 0)), int(dev.get("reviewed", 0))), 3),
    }


def load_qualification(path: Path) -> dict[str, dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return {name: qualification(entry) for name, entry in data["producers"].items()}

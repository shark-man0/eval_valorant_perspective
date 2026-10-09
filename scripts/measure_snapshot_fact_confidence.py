"""Measure snapshot-derived fact confidence against the source observation confidence.

Question: how often does a snapshot-derived fact reach the deterministic 0.90 gate while
the HUD observation it was read from is below 0.90 ("over"), how often is a fact held below
the gate although its observation is >= 0.90 ("under"), and how often does a fact carry
more confidence than its source at all ("raised")?

Uses the production path only (RoundPackageBuilder.build -> FactBuilder.enrich) on a
deterministic *synthetic* observation population. It illustrates the mechanism and its
scale under stated distributions; it is NOT a frequency measured on real recordings
(no raw observations are available in the repository).

    python scripts/measure_snapshot_fact_confidence.py [--json]
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from valorant_ai_coach.events import EventSourceContract  # noqa: E402
from valorant_ai_coach.facts import FactBuilder  # noqa: E402
from valorant_ai_coach.rounds import RoundPackageBuilder  # noqa: E402
from valorant_ai_coach.schema_validation import SchemaValidator  # noqa: E402
from valorant_ai_coach.video import VideoMetadata  # noqa: E402

GATE = 0.90
SNAPSHOT_KEYS = {
    "numbers_state",
    "clutch_state",
    "spike_carried_by_player",
    "spike_planted",
    "round_time_remaining_sec",
    "weapon",
    "utility_available_count",
}
DURATION = 60.0
STEP = 0.5

SCENARIOS: dict[str, Any] = {
    "uniform_0.65_1.00": lambda rng: rng.uniform(0.65, 1.0),
    "bimodal_70pct_high": lambda rng: (
        rng.uniform(0.90, 0.99) if rng.random() < 0.7 else rng.uniform(0.65, 0.89)
    ),
    "mostly_high_90pct": lambda rng: (
        rng.uniform(0.95, 0.99) if rng.random() < 0.9 else rng.uniform(0.65, 0.80)
    ),
    "constant_0.80": lambda rng: 0.80,
}


def observation(index: int, confidence: float) -> dict[str, Any]:
    time_sec = round(index * STEP, 3)
    return {
        "schema_version": "2.0",
        "time_sec": time_sec,
        "frame_index": index,
        "primary_state": "live_first_person",
        "state_flags": [],
        "view_context": {
            "remote_view_type": "none",
            "is_player_world_view_trustworthy": True,
        },
        "values": {
            "round_time_remaining_sec": max(0.0, 100.0 - time_sec),
            "score_ally": 1,
            "score_enemy": 2,
            "ally_alive": 5 - (index // 8) % 3,
            "enemy_alive": 5 - (index // 5) % 4,
            "hp": 100,
            "armor": 50,
            "ammo_current": 25,
            "ammo_reserve": 50,
            "weapon_text": None,
            "spike_state": "planted" if index > 60 else "not_carried",
            "location_text": None,
            "kill_feed_rows": [],
            "ability_slots": [],
            "combat_report_visible": False,
            "buy_phase_visible": False,
            "round_end_text": None,
            "zone_id": None,
            "player_specific_hud_valid": True,
        },
        "quality": {
            "hud_confidence": confidence,
            "visual_confidence": 0.0,
            "occluded_rois": [],
            "notes": [],
            "state_confidence": confidence,
            # Reserved value-level provenance (the analyzer sets it to the timer reader's
            # accepted confidence); equal to the observation confidence in this population.
            "roi_confidence": {"round_timer_value": confidence},
        },
    }


def event(event_id: str, time_sec: float, event_type: str) -> dict[str, Any]:
    return {
        "event_id": event_id,
        "time_sec": time_sec,
        "type": event_type,
        "actor": "system",
        "attributes": {},
        "confidence": 0.95,
    }


def measure_package(builder: RoundPackageBuilder, rng: random.Random, draw: Any) -> dict[str, Any]:
    count = int(DURATION / STEP)
    confidences = [round(draw(rng), 4) for _ in range(count)]
    observations = [observation(i, c) for i, c in enumerate(confidences)]
    metadata = VideoMetadata(
        path=Path(tempfile.gettempdir()) / "m.mp4",
        duration_sec=DURATION,
        width=1920,
        height=1080,
        fps=60,
        video_codec="h264",
        audio_codec=None,
        has_audio=False,
        file_size=0,
    )
    package = builder.build(
        match_id="M",
        video_metadata=metadata,
        hud_observations=observations,
        hud_events=[event("S", 0.0, "round_start"), event("E", DURATION - 0.5, "round_end")],
    )[0]
    source = {obs["time_sec"]: obs["quality"]["hud_confidence"] for obs in observations}
    enriched = FactBuilder().enrich(package)
    total = over = under = raised = 0
    worst = 0.0
    for fact in enriched["deterministic_facts"]:
        if fact["key"] not in SNAPSHOT_KEYS or fact.get("provenance_event_ids"):
            continue
        origin = source.get(fact.get("time_sec"))
        if origin is None:
            continue
        total += 1
        if origin < GATE and fact["confidence"] >= GATE:
            over += 1
            worst = max(worst, fact["confidence"] - origin)
        if origin >= GATE and fact["confidence"] < GATE:
            under += 1
        if fact["confidence"] > origin + 1e-9:
            raised += 1
    return {
        "facts": total,
        "over": over,
        "under": under,
        "raised": raised,
        "worst_gap": worst,
        "aggregate": package["observation_quality"]["hud_confidence"],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--packages", type=int, default=50)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    contract = EventSourceContract.load(ROOT / "config" / "event_source_contract_v1.json")
    builder = RoundPackageBuilder(contract=contract, validator=SchemaValidator())
    report: dict[str, Any] = {}
    for name, draw in SCENARIOS.items():
        tally: Counter[str] = Counter()
        aggregates: list[float] = []
        worst = 0.0
        for seed in range(args.packages):
            result = measure_package(builder, random.Random(seed), draw)
            tally["packages"] += 1
            tally["facts"] += result["facts"]
            tally["over"] += result["over"]
            tally["under"] += result["under"]
            tally["raised"] += result["raised"]
            tally["packages_with_over"] += 1 if result["over"] else 0
            aggregates.append(result["aggregate"])
            worst = max(worst, result["worst_gap"])
        report[name] = {
            **tally,
            "share_of_facts_over": (
                round(tally["over"] / tally["facts"], 4) if tally["facts"] else 0
            ),
            "aggregate_min": round(min(aggregates), 4),
            "aggregate_max": round(max(aggregates), 4),
            "worst_gap": round(worst, 4),
        }
    if args.json:
        print(json.dumps(report, indent=2))
        return
    header = (
        f"{'scenario':<22}{'pkgs':>5}{'facts':>7}{'over':>6}{'under':>7}{'raised':>7}"
        f"{'pkgs>=1':>9}{'share':>8}{'agg':>14}"
    )
    print(header)
    for name, row in report.items():
        agg = f"{row['aggregate_min']:.2f}-{row['aggregate_max']:.2f}"
        print(
            f"{name:<22}{row['packages']:>5}{row['facts']:>7}{row['over']:>6}"
            f"{row['under']:>7}{row['raised']:>7}{row['packages_with_over']:>9}{row['share_of_facts_over']:>8.3f}{agg:>14}"
        )


if __name__ == "__main__":
    main()

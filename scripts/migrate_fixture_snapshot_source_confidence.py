"""One-off migration of the SYNTHETIC test fixtures (tests/cases/*/input.json).

Round Package state_snapshots now carry per-field `source_confidence`; a snapshot without it
yields snapshot-derived facts at confidence 0.0 (there is no runtime fallback). These
fixtures model production packages, so each populated field gets the confidence the previous
implementation implicitly gave it: observation_quality.hud_confidence for HUD fields and
observation_quality.visual_confidence for location / spatial fields.

DO NOT run this on real or stored round packages: it would assign confidence that was never
measured per observation. Only the synthetic fixtures are migrated.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HUD_FIELDS = (
    "ally_alive",
    "enemy_alive",
    "weapon",
    "spike_state",
    "round_time_remaining_sec",
    "utility_available_count",
)


def migrate(package: dict) -> int:
    quality = package["observation_quality"]
    hud, visual = quality["hud_confidence"], quality["visual_confidence"]
    changed = 0
    for snapshot in package["state_snapshots"]:
        if "source_confidence" in snapshot:
            continue
        source = {field: hud for field in HUD_FIELDS if snapshot.get(field) is not None}
        if (snapshot.get("player_location") or {}).get("zone_id") is not None:
            source["player_location"] = visual
        spatial = snapshot.get("spatial_context") or {}
        values = [
            spatial.get(key)
            for key in (
                "cover_available",
                "escape_route_available",
                "exposed_directions_count",
                "view_target_zone_id",
            )
        ]
        if any(value is not None for value in values) or spatial.get(
            "line_of_sight_state"
        ) not in (None, "unknown"):
            source["spatial_context"] = visual
        snapshot["source_confidence"] = source
        changed += 1
    return changed


def main() -> None:
    total = 0
    for path in sorted((ROOT / "tests" / "cases").glob("TC-*/input.json")):
        raw = path.read_text(encoding="utf-8")
        package = json.loads(raw)
        if json.dumps(package, indent=2, ensure_ascii=False) != raw:
            sys.exit(f"{path}: formatting would change beyond the added field; aborting")
        changed = migrate(package)
        if changed:
            path.write_text(json.dumps(package, indent=2, ensure_ascii=False), encoding="utf-8")
            total += changed
    print(f"migrated {total} snapshots")


if __name__ == "__main__":
    main()

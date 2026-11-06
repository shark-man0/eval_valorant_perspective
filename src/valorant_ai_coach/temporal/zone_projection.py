"""Expose exact-pixel viewed location labels without assigning recorder Zones."""

from copy import deepcopy
from fractions import Fraction
from typing import Any

from .evidence import native_time
from .pixel_projection import attach_pixel_evidence
from .zone_contract import MEASUREMENT_SCHEMA, viewed_zone_candidate


def attach_viewed_zones(bundle: dict[str, Any], rows: list[dict[str, Any]]) -> None:
    """Reuse the existing validated location contract and native sidecar join.

    The single state engine alone owns current recorder association. This
    advisory projection leaves all existing marker/owner/state fields intact.
    """
    origin = Fraction(bundle["recording"]["native_origin_seconds"])

    def validate(row: dict[str, Any]) -> None:
        viewed_zone_candidate(row)

    def project(current: list[dict[str, Any]]) -> dict[str, Any]:
        zones = [r for r in current if r["raw"].get("schema") == MEASUREMENT_SCHEMA]
        second = int((native_time(zones[0]["sample"]) - origin) // 1)
        result: dict[str, Any] = deepcopy(bundle["seconds"][second]["map_observations"])
        ids = {z.get("observation_id") for z in result["zone_candidates"]}
        for row in zones:
            candidate = viewed_zone_candidate(row)
            if candidate and candidate["observation_id"] not in ids:
                result["zone_candidates"].append(candidate)
                ids.add(candidate["observation_id"])
        if result["zone_candidates"]:
            result["status"] = "CANDIDATES"
        result["viewed_location_scope"] = "display_label_only; no_recorder_or_geometric_association"
        return result

    attach_pixel_evidence(
        bundle,
        rows,
        schema=MEASUREMENT_SCHEMA,
        stream_kind="hud_zone",
        prefix="HUD_zone",
        target_field="map_observations",
        validate=validate,
        project=project,
    )

"""Join value-only HUD evidence without adding state lanes."""

from collections.abc import Callable
from typing import Any

from .hud_values import VERSION
from .pixel_projection import attach_pixel_evidence


def attach_hud_values(
    bundle: dict[str, Any], rows: list[dict[str, Any]],
    project_fields: Callable[[list[dict[str, Any]]], dict[str, Any]],
) -> None:
    def validate(row: dict[str, Any]) -> None:
        if row["raw"].get("ownership") != "UNKNOWN":
            raise ValueError("Original same-Source value-only HUD evidence required")

    attach_pixel_evidence(bundle, rows, schema=VERSION, stream_kind="hud_values",
                          prefix="HUD_value", target_field="hud_observations",
                          validate=validate, project=project_fields)

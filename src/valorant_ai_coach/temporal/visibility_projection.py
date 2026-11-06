"""Visibility-only current pixel links; no recorder or lifecycle authority."""

from typing import Any

from .hud_visibility import visibility_summary
from .pixel_projection import attach_pixel_evidence


def attach_visibility(bundle: dict[str, Any], rows: list[dict[str, Any]]) -> None:
    def validate(row: dict[str, Any]) -> None:
        visibility_summary([row])

    attach_pixel_evidence(bundle, rows, schema="development_HUD_visibility_observation_v1",
                          stream_kind="hud_visibility", prefix="HUD_visibility",
                          target_field="hud_visibility_observations", validate=validate,
                          project=visibility_summary)

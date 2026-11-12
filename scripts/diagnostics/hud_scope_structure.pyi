"""Typed image-helper boundary without following unrelated diagnostic CLIs."""

from typing import Any

from valorant_ai_coach.hud.layout import HudLayout
from valorant_ai_coach.hud.timer_glyphs import ImageU8

class ComponentReferenceCache:
    def __init__(
        self, layout: HudLayout, references: list[tuple[ImageU8, ImageU8]],
        bindings: dict[str, str],
    ) -> None: ...
    def scopes(
        self, observed: ImageU8, layout: HudLayout,
        references: list[tuple[ImageU8, ImageU8]], bindings: dict[str, str],
        joint_regions: bool,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]: ...

def outline_mask(template: ImageU8, mask: ImageU8) -> ImageU8: ...
def top_scope(template: ImageU8, mask: ImageU8, observed: ImageU8) -> dict[str, Any]: ...
def joint_scope(
    template: ImageU8, mask: ImageU8, observed: ImageU8,
    regions: dict[str, list[int]],
) -> dict[str, Any]: ...
def reference_fingerprint(references: list[tuple[ImageU8, ImageU8]]) -> str: ...
def component_geometry(
    frame: dict[str, Any], image: ImageU8, layout: HudLayout,
    references: list[tuple[ImageU8, ImageU8]], bindings: dict[str, str], *,
    joint_regions: bool = False,
    reference_cache: ComponentReferenceCache | None = None,
) -> dict[str, Any]: ...
def component_support(frame: dict[str, Any], role: str) -> bool: ...

"""Opt-in native pixel HUD visibility supplier around an existing observer.

The wrapped observer still owns its original signals and HUD values. Visibility
is advisory metadata; BUY_MENU and TRACKER do not establish Round state.
"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, Protocol

import numpy as np

from .evidence import digest
from .hud_visibility import HUDVisibilityReader


class NativeObserver(Protocol):
    fingerprint: str
    bindings: dict[str, Any]

    def inspect(self, image: np.typing.NDArray[np.uint8]) -> dict[str, Any]: ...


class VisibilitySupplier:
    """Append measured visibility to the same native frame, without new state."""

    def __init__(self, base: NativeObserver, tessdata: Path) -> None:
        self.base = base
        self.visibility = HUDVisibilityReader(tessdata)
        self.bindings = {"base_fingerprint": base.fingerprint,
                         "base_bindings": base.bindings,
                         "HUD_visibility": self.visibility.bindings,
                         "supplier": "development_visibility_supplier_v1"}
        self.fingerprint = digest(self.bindings)

    def inspect(self, image: np.typing.NDArray[np.uint8]) -> dict[str, Any]:
        measured = deepcopy(self.base.inspect(image))
        if "supplier_observations" in measured:
            raise ValueError("Wrap an individual native HUD observer, not a composite summary")
        raw = measured.setdefault("raw", {})
        if "hud_visibility" in raw:
            raise ValueError("Base observer already supplies HUD visibility")
        # The exact same native pixels and base UI anchor measurements are used.
        raw["hud_visibility"] = self.visibility.inspect(image, raw.get("ui", {}))
        return measured

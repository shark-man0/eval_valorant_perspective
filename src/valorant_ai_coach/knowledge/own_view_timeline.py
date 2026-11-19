"""Own-view HUD readings (magazine count, carried spike) as timeline observations.

Same interface as ``top_bar_timeline``: one ``temporal.game.observation`` row per
decoded frame, carrying the readings as ``raw["values"]`` entries with a
confidence. ``temporal.application`` turns them into ``hud_observations``
candidates (``ammo_current``, ``ammo_reserve``, ``spike_carried``) with the HUD subject
``viewed_HUD; recorder_ownership_unresolved``: these panels show whoever is
being viewed, so whether a reading belongs to the recorder is the timeline's
view-ownership decision, never this module's.

Rows add no signals and no state; promotion to formal Facts stays with the
shared-timeline promoter (``facts.timeline_promotion``, #164).
"""

from __future__ import annotations

import hashlib
from typing import Any

import numpy as np

from ..temporal.game import observation
from .ammo_reader import AMMO_ROI, AmmoReader
from .spike_carrier import INVENTORY_ROI, SpikeCarrierReader
from .top_bar_timeline import hud_crop

AMMO_STREAM_KIND = "own_view_magazine_v1"
SPIKE_STREAM_KIND = "own_view_spike_carrier_v1"


def _fingerprint(kind: str, *arrays: np.ndarray) -> str:
    digest = hashlib.sha256(kind.encode("ascii"))
    for array in arrays:
        digest.update(np.ascontiguousarray(array, dtype=np.float32).tobytes())
    return digest.hexdigest()


def ammo_fingerprint(reader: AmmoReader) -> str:
    arrays = [reader.templates] + ([reader.reserve_templates]
                                   if reader.reserve_templates is not None else [])
    return _fingerprint(AMMO_STREAM_KIND, *arrays)


def spike_fingerprint(reader: SpikeCarrierReader) -> str:
    arrays = [reader.template] + ([reader.negative] if reader.negative is not None else [])
    return _fingerprint(SPIKE_STREAM_KIND, *arrays)


def magazine_observation(frame: np.ndarray, sample: dict[str, Any], reader: AmmoReader,
                         *, producer: str | None = None) -> dict[str, Any]:
    """Magazine and reserve counts of the viewed player's current weapon
    (full-scale crop). The reserve changes only on a reload or a weapon switch,
    which is how ``rules.second_series.classify_ammo_change`` tells a switch or
    a reload from firing."""
    crop = hud_crop(frame, AMMO_ROI, 1.0)
    values: dict[str, Any] = {}
    for name, reading in (("ammo_current", reader.read(crop)),
                          ("ammo_reserve", reader.read_reserve(crop))):
        if reading.value is not None:
            values[name] = {"value": reading.value,
                            "confidence": round(float(reading.match or 0.0), 4)}
    return observation(sample=sample, producer=producer or ammo_fingerprint(reader),
                       signals=[], raw={"values": values},
                       context={"stream_kind": AMMO_STREAM_KIND})


def spike_carrier_observation(frame: np.ndarray, sample: dict[str, Any],
                              reader: SpikeCarrierReader, *,
                              producer: str | None = None) -> dict[str, Any]:
    """Whether the viewed player's inventory shows the spike header."""
    reading = reader.read(hud_crop(frame, INVENTORY_ROI, reader.scale))
    values = {"spike_carried": {"value": reading.carried,
                                "confidence": round(min(1.0, max(0.0, float(reading.score))), 4)}}
    return observation(sample=sample, producer=producer or spike_fingerprint(reader),
                       signals=[], raw={"values": values},
                       context={"stream_kind": SPIKE_STREAM_KIND})

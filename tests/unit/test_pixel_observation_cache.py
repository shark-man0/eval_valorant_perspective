"""Observation reuse cannot import state, configuration or mutable results."""

import json
import sqlite3

import numpy as np
import pytest

from valorant_ai_coach.temporal.pixel_cache import CachedPixelObserver


class Pixels:
    def __init__(self, fingerprint="a" * 64):
        self.fingerprint = fingerprint
        self.bindings = {"profile": "b" * 64}
        self.calls = 0

    def inspect(self, image):
        self.calls += 1
        return {"signals": [], "context": {}, "map_candidates": [],
                "raw": {"pixel_value": int(image[0, 0, 0]), "coordinates": (1, 2)}}


def test_cache_reuses_exact_pixels_without_mutating_measurements(tmp_path):
    child = Pixels()
    cache = CachedPixelObserver(child, tmp_path/"private.sqlite")
    image = np.zeros((8, 9, 3), dtype=np.uint8)
    expected = json.loads(json.dumps(child.inspect(image)))
    first = cache.inspect(image)
    assert first == expected
    first["raw"]["pixel_value"] = 999
    assert cache.inspect(image.copy()) == expected
    assert child.calls == 2  # one direct reference, one cold cache call
    assert cache.stats == {"hits": 1, "misses": 1}
    assert cache.bindings["pixel_cache"]["recognition_state_authority"] is False
    cache.close()


def test_cache_namespace_binds_recognizer_and_profile_but_not_private_path(tmp_path):
    image = np.zeros((8, 9, 3), dtype=np.uint8)
    first = CachedPixelObserver(Pixels(), tmp_path/"one.sqlite")
    same = CachedPixelObserver(Pixels(), tmp_path/"one.sqlite")
    elsewhere = CachedPixelObserver(Pixels(), tmp_path/"two.sqlite")
    changed = CachedPixelObserver(Pixels("c"*64), tmp_path/"one.sqlite")
    assert first.fingerprint == same.fingerprint == elsewhere.fingerprint
    assert changed.fingerprint != first.fingerprint
    first.inspect(image)
    same.inspect(image)
    changed.inspect(image)
    assert same.stats == {"hits": 1, "misses": 0}
    assert changed.stats == {"hits": 0, "misses": 1}
    for cache in [first, same, elsewhere, changed]:
        cache.close()


def test_shape_and_pixel_changes_are_not_a_cache_hit(tmp_path):
    cache = CachedPixelObserver(Pixels(), tmp_path/"cache.sqlite")
    for shape, value in [((8, 9, 3), 0), ((9, 8, 3), 0), ((8, 9, 3), 1)]:
        cache.inspect(np.full(shape, value, dtype=np.uint8))
    assert cache.stats == {"hits": 0, "misses": 3}
    cache.close()


def test_tampered_payload_and_changed_live_bindings_are_rejected(tmp_path):
    path = tmp_path/"cache.sqlite"
    child = Pixels()
    cache = CachedPixelObserver(child, path)
    image = np.zeros((8, 9, 3), dtype=np.uint8)
    cache.inspect(image)
    with sqlite3.connect(path) as db:
        db.execute("UPDATE pixels SET payload='{}'")
    with pytest.raises(ValueError, match="integrity"):
        cache.inspect(image)
    assert child.calls == 1
    child.bindings["profile"] = "d"*64
    with pytest.raises(ValueError, match="bindings"):
        cache.inspect(image)
    cache.close()


@pytest.mark.parametrize("image", [np.zeros((8,9),dtype=np.uint8),
    np.zeros((8,9,4),dtype=np.uint8),np.zeros((8,9,3),dtype=np.float64)])
def test_non_native_pixel_layout_is_rejected(tmp_path, image):
    cache = CachedPixelObserver(Pixels(), tmp_path/"cache.sqlite")
    with pytest.raises(ValueError, match="BGR"):
        cache.inspect(image)
    assert not cache.path.exists()


def test_private_cache_cannot_be_created_under_git(tmp_path):
    (tmp_path/".git").mkdir()
    with pytest.raises(ValueError, match="outside Git"):
        CachedPixelObserver(Pixels(), tmp_path/"cache.sqlite")

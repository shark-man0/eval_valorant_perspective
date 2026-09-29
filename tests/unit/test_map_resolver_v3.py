import json
import shutil
from copy import deepcopy

import pytest

from valorant_ai_coach.maps.registry import MapRegistry, MapRegistryError
from valorant_ai_coach.maps.resolver import ZoneResolver


@pytest.fixture
def registry():
    return MapRegistry()


def resolve(resolver, t, point=None, **kwargs):
    return resolver.resolve(
        time_sec=t,
        frame_index=round(t * 10),
        point=point,
        marker_confidence=kwargs.pop("marker_confidence", 0.99),
        calibration=kwargs.pop("calibration", {"status": "ok", "confidence": 0.99}),
        **kwargs,
    )


def test_registry_selection_priority_and_fixture_isolation(registry):
    assert registry.select() is None
    assert registry.select(template_scores={"summit": 0.89}) is None
    assert registry.select(template_scores={"summit": 0.9}) == "summit"
    assert registry.select(map_label="SUMMIT", label_confidence=0.95) == "summit"
    assert registry.select(manual_map_id="summit", map_label="unknown") == "summit"
    with pytest.raises(KeyError):
        registry.select(manual_map_id="missing")
    registry.load("three_site_fixture", allow_fixture=True)
    with pytest.raises(MapRegistryError):
        registry.load("three_site_fixture")


def test_boundary_hold_restarts_new_zone_persistence(registry):
    resolver = ZoneResolver(registry.load("special_link_fixture", allow_fixture=True))
    for t in (0, 0.2, 0.4, 0.6):
        stable = resolve(resolver, t, (0.1, 0.1))
    assert stable["zone_id"] == "sl_a_site"
    assert resolve(resolver, 0.8, (0.1, 0.35))["zone_id"] is None
    for t in (1, 1.2):
        assert resolve(resolver, t, (0.1, 0.25))["held_from_previous"]
    for t in (1.4, 1.6, 1.8):
        pending = resolve(resolver, t, (0.1, 0.35))
        assert pending["zone_id"] is None
        assert "zone_transition_pending" in pending["diagnostics"]
    assert resolve(resolver, 2, (0.1, 0.35))["zone_id"] == "sl_a_app"


@pytest.mark.parametrize(
    "point,zone", [((0.9, 0.42), "summit_a_site"), ((0.08, 0.42), "summit_b_site")]
)
def test_polygon_confidence_and_real_time_debounce(registry, point, zone):
    resolver = ZoneResolver(registry.load("summit"))
    assert resolve(resolver, 0, point)["zone_id"] is None
    assert resolve(resolver, 0.59, point)["zone_id"] is None
    result = resolve(resolver, 0.6, point)
    assert result["zone_id"] == zone
    assert result["zone_confidence"] == 0.9
    assert result["resolution_source"] == "polygon"
    assert resolver.match_peek(point, result, 1) is None


def test_label_alias_stability_and_controlled_context(registry):
    definition = registry.load("summit")
    expected = definition.callouts["records"]["A Main"]["zone_id"]
    resolver = ZoneResolver(definition)
    assert resolve(resolver, 0, label="A メイン", label_confidence=0.98)["zone_id"] is None
    for t in (0.2, 0.4, 0.6, 0.8, 1, 1.2):
        result = resolve(resolver, t, label="A メイン", label_confidence=0.98)
    assert result["zone_id"] == expected
    assert result["resolution_source"] == "location_label"
    resolver.reset()
    for t in (0, 0.5, 1, 1.5):
        result = resolve(
            resolver, t, label="A メイン", label_confidence=0.99, controlled_player=False
        )
    assert result["zone_id"] is None


@pytest.mark.parametrize("label,zone", [
    ("A ロビー", "summit_a_approach"),
    ("中央ファウンテン", "summit_mid"),
    ("Bメイン", "summit_b_approach"),
])
def test_observed_alias_overlay_preserves_ownership(registry, label, zone):
    resolver = ZoneResolver(registry.load("summit"))
    for t in (0, .3, .6, .9, 1.2):
        result = resolve(resolver, t, label=label, label_confidence=.98)
    assert result["zone_id"] == zone
    assert result["zone_confidence"] <= .96
    result = resolve(resolver, 1.5, label=label, label_confidence=.98, controlled_player=False)
    assert result["zone_id"] is None


@pytest.mark.parametrize(
    "label_conf,poly_conf,expected_source,expected_zone",
    [
        (0.95, 0.95, "unknown", None),
        (0.95, 0.75, "location_label", "summit_a_site"),
        (0.75, 0.95, "polygon", "summit_b_site"),
    ],
)
def test_actual_label_polygon_disagreement(
    registry, label_conf, poly_conf, expected_source, expected_zone
):
    definition = deepcopy(registry.load("summit"))
    definition.callouts["records"]["test-label"] = {
        "zone_id": "summit_a_site",
        "confidence_cap": 1,
        "aliases": {},
    }
    resolver = ZoneResolver(definition)
    for i in range(12):
        result = resolve(
            resolver,
            i * 0.2,
            (0.08, 0.42),
            label="test-label",
            label_confidence=label_conf,
            marker_confidence=poly_conf,
        )
    assert result["zone_id"] == expected_zone
    assert result["resolution_source"] == expected_source


def test_low_same_zone_fusion_is_not_named_gameplay_evidence(registry):
    definition = deepcopy(registry.load("summit"))
    definition.callouts["records"]["test-label"] = {
        "zone_id": "summit_a_site",
        "confidence_cap": 1,
        "aliases": {},
    }
    resolver = ZoneResolver(definition)
    for i in range(12):
        result = resolve(
            resolver,
            i * 0.2,
            (0.9, 0.42),
            label="test-label",
            label_confidence=0.83,
            marker_confidence=0.82,
        )
    assert result["calibration_status"] == "degraded"
    assert result["resolution_scope"] == "coarse_role"
    assert result["zone_id"] is None
    assert result["zone_confidence"] <= 0.82


def test_boundary_hold_expires_and_does_not_invent_transition(registry):
    definition = registry.load("special_link_fixture", allow_fixture=True)
    resolver = ZoneResolver(definition)
    for t in (0, 0.2, 0.4, 0.6):
        stable = resolve(resolver, t, (0.1, 0.1))
    assert stable["zone_id"] == "sl_a_site"
    held = resolve(resolver, 0.8, (0.1, 0.25))
    assert held["held_from_previous"] and held["boundary_state"] == "ambiguous"
    decayed = resolve(resolver, 1, (0.1, 0.25))
    assert decayed["zone_confidence"] < held["zone_confidence"]
    expired = resolve(resolver, 1.5, (0.1, 0.25))
    assert expired["zone_id"] is None


@pytest.mark.parametrize("status", ["failed", "calibration_required"])
def test_calibration_failure_blocks_even_valid_label(registry, status):
    resolver = ZoneResolver(registry.load("summit"))
    for t in (0, 0.6, 1.2):
        result = resolve(
            resolver,
            t,
            (0.9, 0.42),
            label="A メイン",
            label_confidence=1,
            calibration={"status": status, "confidence": 1},
        )
    assert result["zone_id"] is None and result["zone_confidence"] == 0


@pytest.mark.parametrize(
    "mutation", ["extra", "missing_zone", "mask_gap", "wrong_hash", "nonfinite"]
)
def test_registry_rejects_invalid_data_without_rewriting_mask(registry, tmp_path, mutation):
    root = tmp_path / "bundle"
    shutil.copytree(registry.root, root)
    path = root / "config/maps/summit_map_v3.json"
    data = json.loads(path.read_text())
    if mutation == "extra":
        data["adjacency"] = {}
    elif mutation == "missing_zone":
        data["topology_edges"][0]["to_zone_id"] = "missing"
    elif mutation == "mask_gap":
        for zone in data["zones"]:
            zone["polygon_norm"] = [[0, 0], [0.01, 0], [0.01, 0.01], [0, 0.01]]
    elif mutation == "nonfinite":
        data["geometry_confidence_cap"] = float("nan")
    else:
        reference = root / "assets/summit_minimap_reference.png"
        reference.write_bytes(b"invalid reference")
    path.write_text(json.dumps(data))
    mask = root / "config/maps/summit_operational_mask_v1.json"
    before = mask.read_bytes()
    with pytest.raises(MapRegistryError):
        MapRegistry(root).load("summit")
    assert mask.read_bytes() == before

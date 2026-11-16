from __future__ import annotations

import hashlib
import json
from pathlib import Path

import cv2
import numpy as np
import pytest

from valorant_ai_coach.knowledge import assets as assets_module
from valorant_ai_coach.knowledge import load_game_knowledge, normalize_name
from valorant_ai_coach.knowledge.assets import (
    ReferenceAssets,
    ReferenceAssetsUnavailable,
    asset_id_for_url,
    content_digest,
)
from valorant_ai_coach.knowledge.catalog import HUD_ABILITY_KEYS
from valorant_ai_coach.knowledge.hud_abilities import (
    ICON_CENTER_Y,
    SLOT_CENTERS_X,
    STRIP_BOX,
    AbilityHudReader,
    identify_agent,
)
from valorant_ai_coach.knowledge.top_bar import (
    ALLY_CENTERS_X,
    BAR_ORIGIN,
    ENEMY_CENTERS_X,
    PORTRAIT_CENTER_Y,
    read_top_bar,
)
from valorant_ai_coach.models.role import RoleResolver


@pytest.fixture(scope="module")
def knowledge():
    return load_game_knowledge()


def test_snapshot_is_complete_and_versioned(knowledge) -> None:
    summary = knowledge.summary()
    assert summary["game_version"] == "13.10"
    assert summary["agents"] == 30
    assert summary["weapons"] == 21
    assert summary["maps"] == 13
    assert summary["callouts"] == 300
    assert set(summary["agents_by_role"]) == {"controller", "duelist", "initiator", "sentinel"}
    assert sum(summary["agents_by_role"].values()) == 30
    for agent in knowledge.agents:
        assert tuple(a.key for a in agent.hud_abilities()) == HUD_ABILITY_KEYS
        assert agent.provenance.source_id == "valorant_api_content"
        assert "ja-JP" in agent.names


def test_localized_lookup_and_vocabulary(knowledge) -> None:
    assert knowledge.agent("クローヴ").name == "Clove"
    assert knowledge.agent("kay/o").name == "KAY/O"
    assert knowledge.role_of("ジェット") == "duelist"
    assert knowledge.role_of("not an agent") == "unknown"
    assert knowledge.weapon("ヴァンダル").cost == 2900
    assert knowledge.weapon("Vandal").magazine_size == 25
    assert {w.name for w in knowledge.weapons_by_cost(2900)} == {"Vandal", "Phantom", "Warden"}
    assert knowledge.map("ヘイヴン").sites == ("A", "B", "C")
    assert knowledge.vocabulary("callout", "ja-JP")[normalize_name("Aロビー")] == "A Lobby"
    # Ability names can collide across agents (e.g. localized short names); all are returned.
    assert any(a.key == "C" for a in knowledge.abilities_named("Cloudburst"))


def test_rules_are_priors_with_sources(knowledge) -> None:
    assert knowledge.rule("round_time_limit_sec") == 100
    assert knowledge.rule("spike_detonation_sec") == 45
    assert knowledge.rule("hud_ability_order") == list(HUD_ABILITY_KEYS)
    for rule in knowledge.rules.values():
        assert rule.source_id
        assert rule.status in {"secondary_consistent", "recording_consistent",
                               "repository_contract"}


def test_minimap_transform_uses_swapped_axes(knowledge) -> None:
    ascent = knowledge.map("Ascent")
    x, y = ascent.world_to_minimap(1000.0, -2000.0)
    assert x == pytest.approx(-2000.0 * ascent.x_multiplier + ascent.x_scalar_to_add)
    assert y == pytest.approx(1000.0 * ascent.y_multiplier + ascent.y_scalar_to_add)
    site_a = next(c for c in ascent.callouts if c.label == "A Site")
    ranked = ascent.nearest_callouts(site_a.minimap_xy, k=2)
    assert ranked[0][0] is site_a and ranked[0][1] == 0
    with pytest.raises(ValueError):
        ascent.world_to_minimap(float("nan"), 0.0)


def test_ledger_pins_committed_files(tmp_path: Path, knowledge) -> None:
    ledger = json.loads(Path("config/game_knowledge/source_ledger_v1.json").read_text("utf-8"))
    pinned = {}
    for source in ledger["sources"]:
        pinned.update(source.get("committed_files", {}))
        assert source["rights"] in ledger["rights_categories"]
    for relative, digest in pinned.items():
        assert hashlib.sha256(Path(relative).read_bytes()).hexdigest() == digest


def test_role_resolver_from_knowledge_is_opt_in() -> None:
    assert RoleResolver().resolve("Jett") == "unknown"
    resolver = RoleResolver.from_game_knowledge()
    assert resolver.resolve("Jett") == "duelist"
    assert resolver.resolve("ジェット") == "duelist"
    assert resolver.resolve("Omen") == "controller"


def test_asset_ids_from_urls() -> None:
    uuid = "add6443a-41bd-e414-f6ad-e58d267f4e95"
    base = f"https://media.valorant-api.com/agents/{uuid}"
    ability_url = f"{base}/abilities/grenade/displayicon.png"
    assert asset_id_for_url(ability_url) == f"ability:{uuid}:Grenade"
    assert asset_id_for_url(f"{base}/killfeedportrait.png") == f"agent:{uuid}:killfeedportrait"
    assert asset_id_for_url("https://example.com/x.png") is None


def _write_cache(root: Path, images: dict[str, np.ndarray]) -> list[dict[str, object]]:
    entries = []
    for url, image in images.items():
        ok, data = cv2.imencode(".png", image)
        assert ok
        name = hashlib.sha1(url.encode('utf-8')).hexdigest()  # noqa: UP012
        relative = f"files/{name}.png"
        (root / relative).parent.mkdir(parents=True, exist_ok=True)
        (root / relative).write_bytes(data.tobytes())
        entries.append({"kind": "ability", "subject": "x", "variant": "y", "url": url,
                        "path": relative, "sha256": hashlib.sha256(data.tobytes()).hexdigest()})
    index = {"game_version": "13.10", "content_digest": content_digest(entries), "files": entries}
    (root / "index.json").write_text(json.dumps(index), "utf-8")
    return entries


def test_cache_must_match_pinned_digest(tmp_path: Path, monkeypatch) -> None:
    url = ("https://media.valorant-api.com/agents/add6443a-41bd-e414-f6ad-e58d267f4e95/"
           "abilities/grenade/displayicon.png")
    entries = _write_cache(tmp_path, {url: np.zeros((8, 8, 4), np.uint8)})
    with pytest.raises(ReferenceAssetsUnavailable):
        ReferenceAssets.load(tmp_path)
    monkeypatch.setattr(assets_module, "pinned_manifest",
                        lambda version="13.10": {"content_digest": content_digest(entries)})
    opened = ReferenceAssets.load(tmp_path)
    assert opened.image(asset_id_for_url(url)).shape == (8, 8, 4)
    (tmp_path / entries[0]["path"]).write_bytes(b"tampered")
    with pytest.raises(ReferenceAssetsUnavailable):
        ReferenceAssets.load(tmp_path)
    with pytest.raises(ReferenceAssetsUnavailable):
        ReferenceAssets.load(tmp_path / "missing")


class _SyntheticAssets:
    """Distinct random glyphs per ability; stands in for the private icon cache."""

    def image(self, asset_id: str) -> np.ndarray:
        digest = hashlib.sha256(asset_id.encode('utf-8')).hexdigest()  # noqa: UP012
        rng = np.random.default_rng(int(digest[:8], 16))
        glyph = (rng.random((8, 8)) > 0.55).astype(np.uint8) * 255
        glyph = cv2.resize(glyph, (128, 128), interpolation=cv2.INTER_NEAREST)
        icon = np.zeros((128, 128, 4), np.uint8)
        icon[:, :, :3] = 255
        icon[:, :, 3] = glyph
        icon[0, :, 3] = icon[-1, :, 3] = icon[:, 0, 3] = icon[:, -1, 3] = 255
        return icon


def _render_strip(knowledge, agent_name: str, charged: tuple[bool, ...]) -> np.ndarray:
    frame = np.full((1080, 1920, 3), 40, np.uint8)
    assets = _SyntheticAssets()
    agent = knowledge.agent(agent_name)
    for key, cx, is_charged in zip(HUD_ABILITY_KEYS, SLOT_CENTERS_X, charged, strict=True):
        icon = assets.image(agent.abilities[key].asset_id)
        glyph = cv2.resize(icon[:, :, 3], (44, 44), interpolation=cv2.INTER_AREA)
        y0, x0 = ICON_CENTER_Y - 22, cx - 22
        region = frame[y0:y0 + 44, x0:x0 + 44]
        region[glyph > 127] = 235
        if is_charged:
            frame[1038:1046, cx - 30:cx + 30] = (170, 230, 60)  # teal charge bar (BGR)
    x0, y0, x1, y1 = STRIP_BOX
    return frame[y0:y1, x0:x1]


def test_ability_reader_ranks_agent_and_reads_charges(knowledge) -> None:
    reader = AbilityHudReader(knowledge, _SyntheticAssets())
    strip = _render_strip(knowledge, "Fade", (True, False, True, True))
    reading = reader.read(strip)
    assert reading.hud_present
    assert knowledge.agent(reading.ranked(1)[0][0]).name == "Fade"
    assert reading.utility_available_count == 2
    assert reading.ultimate_ready
    readings = [reading] * 25 + [reader.read(_render_strip(knowledge, "Omen", (False,) * 4))] * 5
    ident = identify_agent(readings)
    assert ident.status == "IDENTIFIED"
    assert knowledge.agent(ident.agent_uuid).name == "Fade"
    assert identify_agent(readings[:5]).status == "NO_HUD"


def _top_bar(ally_alive: int, enemy_alive: int) -> np.ndarray:
    rng = np.random.default_rng(1)
    crop = np.zeros((100, 1155, 3), np.uint8)
    crop[15:85, :] = (90, 140, 90)
    for index, cx in enumerate(ALLY_CENTERS_X):
        if index >= len(ALLY_CENTERS_X) - ally_alive:
            x = cx - BAR_ORIGIN[0]
            crop[PORTRAIT_CENTER_Y - 20:PORTRAIT_CENTER_Y + 20, x - 20:x + 20] = rng.integers(
                0, 255, (40, 40, 3))
    for index, cx in enumerate(ENEMY_CENTERS_X):
        if index < enemy_alive:
            x = cx - BAR_ORIGIN[0]
            crop[PORTRAIT_CENTER_Y - 20:PORTRAIT_CENTER_Y + 20, x - 20:x + 20] = rng.integers(
                0, 255, (40, 40, 3))
    return crop


def test_top_bar_alive_counts_and_packing() -> None:
    reading = read_top_bar(_top_bar(3, 5))
    assert (reading.ally.alive, reading.enemy.alive) == (3, 5)
    assert reading.consistent
    assert reading.numbers_state() == "disadvantage"
    half = cv2.resize(_top_bar(2, 2), (577, 50), interpolation=cv2.INTER_AREA)
    assert read_top_bar(half).numbers_state() == "even"
    broken = _top_bar(5, 0)
    x = ALLY_CENTERS_X[2] - BAR_ORIGIN[0]
    broken[PORTRAIT_CENTER_Y - 20:PORTRAIT_CENTER_Y + 20, x - 20:x + 20] = (90, 140, 90)
    reading = read_top_bar(broken)
    assert not reading.consistent
    assert reading.numbers_state() is None

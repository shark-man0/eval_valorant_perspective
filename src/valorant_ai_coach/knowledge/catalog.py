"""Versioned VALORANT game knowledge shared by HUD, Map and timeline consumers.

Knowledge describes the game (who the agents are, what a Vandal costs, where
"A Site" is on Ascent). It is never evidence that something happened in a
recording; consumers may use it to generate, rank or constrain candidates.
Every item records its source id and game version.
"""

from __future__ import annotations

import hashlib
import json
import math
import unicodedata
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path
from typing import Any

from valorant_ai_coach.resources import resource_path

DEFAULT_VERSION = "13.10"
KNOWLEDGE_DIR = "config/game_knowledge"
API_SLOT_TO_KEY = {
    "Grenade": "C",
    "Ability1": "Q",
    "Ability2": "E",
    "Ultimate": "X",
    "Passive": "P",
}
HUD_ABILITY_KEYS = ("C", "Q", "E", "X")
ROLE_CANONICAL = {
    "Controller": "controller",
    "Duelist": "duelist",
    "Initiator": "initiator",
    "Sentinel": "sentinel",
}


def normalize_name(text: str) -> str:
    """Case, width and punctuation-insensitive key for names read from screens."""
    folded = unicodedata.normalize("NFKC", text).casefold()
    return "".join(ch for ch in folded if ch.isalnum())


@dataclass(frozen=True)
class Provenance:
    source_id: str
    game_version: str
    status: str
    file_sha256: str | None = None


@dataclass(frozen=True)
class Ability:
    agent_uuid: str
    api_slot: str
    key: str
    name: str
    names: dict[str, str]
    has_icon: bool

    @property
    def is_ultimate(self) -> bool:
        return self.key == "X"

    @property
    def asset_id(self) -> str:
        return f"ability:{self.agent_uuid}:{self.api_slot}"


@dataclass(frozen=True)
class Agent:
    uuid: str
    name: str
    names: dict[str, str]
    role: str
    release_date: str | None
    abilities: dict[str, Ability]
    provenance: Provenance

    def hud_abilities(self) -> tuple[Ability, ...]:
        """Abilities shown in the bottom HUD, in C, Q, E, X order."""
        return tuple(self.abilities[key] for key in HUD_ABILITY_KEYS if key in self.abilities)

    def asset_id(self, variant: str) -> str:
        return f"agent:{self.uuid}:{variant}"


@dataclass(frozen=True)
class DamageRange:
    start_m: float
    end_m: float
    head: float
    body: float
    leg: float


@dataclass(frozen=True)
class Weapon:
    uuid: str
    name: str
    names: dict[str, str]
    category: str
    cost: int | None
    shop_category: str | None
    fire_rate: float | None
    magazine_size: int | None
    run_speed_multiplier: float | None
    equip_time_sec: float | None
    reload_time_sec: float | None
    first_bullet_accuracy: float | None
    wall_penetration: str | None
    fire_mode: str | None
    damage_ranges: tuple[DamageRange, ...]
    provenance: Provenance

    def asset_id(self, variant: str) -> str:
        return f"weapon:{self.uuid}:{variant}"


@dataclass(frozen=True)
class Callout:
    region: str
    super_region: str
    names: dict[str, tuple[str, str]]
    world_x: float
    world_y: float
    minimap_xy: tuple[float, float]

    @property
    def label(self) -> str:
        return f"{self.super_region} {self.region}"


@dataclass(frozen=True)
class GameMap:
    uuid: str
    name: str
    names: dict[str, str]
    map_url: str
    sites: tuple[str, ...]
    x_multiplier: float
    y_multiplier: float
    x_scalar_to_add: float
    y_scalar_to_add: float
    callouts: tuple[Callout, ...]
    provenance: Provenance

    def world_to_minimap(self, world_x: float, world_y: float) -> tuple[float, float]:
        """World coordinates to normalized coordinates of the map's displayicon.

        valorant-api convention: image x uses world y, image y uses world x.
        The normalized point is reference-image geometry (0..1), not a player
        observation.
        """
        if not (math.isfinite(world_x) and math.isfinite(world_y)):
            raise ValueError("Finite world coordinates required")
        return (
            world_y * self.x_multiplier + self.x_scalar_to_add,
            world_x * self.y_multiplier + self.y_scalar_to_add,
        )

    def nearest_callouts(
        self, minimap_xy: tuple[float, float], k: int = 3
    ) -> tuple[tuple[Callout, float], ...]:
        """Callout anchors ranked by distance in normalized minimap space.

        Callouts are named anchor points, not region polygons: the result is a
        ranked hypothesis list, never a zone assignment.
        """
        x, y = minimap_xy
        ranked = sorted(
            ((c, math.hypot(c.minimap_xy[0] - x, c.minimap_xy[1] - y)) for c in self.callouts),
            key=lambda item: item[1],
        )
        return tuple(ranked[: max(0, k)])

    def asset_id(self) -> str:
        return f"map:{self.uuid}:displayicon"


@dataclass(frozen=True)
class GameRule:
    key: str
    value: Any
    unit: str | None
    status: str
    source_id: str
    note: str | None = None


@dataclass(frozen=True)
class GameKnowledge:
    game_version: str
    client_version: str
    retrieved_at: str
    agents: tuple[Agent, ...]
    weapons: tuple[Weapon, ...]
    maps: tuple[GameMap, ...]
    rules: dict[str, GameRule]
    languages: tuple[str, ...]
    fingerprint: str
    _agent_index: dict[str, Agent] = field(repr=False, compare=False, default_factory=dict)
    _weapon_index: dict[str, Weapon] = field(repr=False, compare=False, default_factory=dict)
    _map_index: dict[str, GameMap] = field(repr=False, compare=False, default_factory=dict)
    _ability_index: dict[str, tuple[Ability, ...]] = field(
        repr=False, compare=False, default_factory=dict
    )

    # Lookup ---------------------------------------------------------------
    def agent(self, name_or_uuid: str) -> Agent | None:
        return self._agent_index.get(normalize_name(name_or_uuid))

    def weapon(self, name_or_uuid: str) -> Weapon | None:
        return self._weapon_index.get(normalize_name(name_or_uuid))

    def map(self, name_or_uuid: str) -> GameMap | None:
        return self._map_index.get(normalize_name(name_or_uuid))

    def map_by_url(self, map_url: str) -> GameMap | None:
        return next((m for m in self.maps if m.map_url == map_url), None)

    def abilities_named(self, name: str) -> tuple[Ability, ...]:
        """All abilities whose name matches in any loaded language."""
        return self._ability_index.get(normalize_name(name), ())

    def role_of(self, agent_name: str | None) -> str:
        if not agent_name:
            return "unknown"
        agent = self.agent(agent_name)
        return agent.role if agent else "unknown"

    def agents_by_role(self, role: str) -> tuple[Agent, ...]:
        return tuple(a for a in self.agents if a.role == role)

    def rule(self, key: str) -> Any:
        return self.rules[key].value

    def weapons_by_cost(self, cost: int) -> tuple[Weapon, ...]:
        return tuple(w for w in self.weapons if w.cost == cost)

    # Vocabularies for readers ---------------------------------------------
    def vocabulary(self, kind: str, language: str = "en-US") -> dict[str, str]:
        """normalized screen text -> canonical English name.

        ``kind`` is agent, weapon, ability, map or callout. Readers use this to
        snap OCR text onto the closed vocabulary instead of trusting raw text.
        """
        def localized(names: dict[str, str], default: str) -> str:
            return names.get(language, default)

        if kind == "agent":
            pairs = [(localized(a.names, a.name), a.name) for a in self.agents]
        elif kind == "weapon":
            pairs = [(localized(w.names, w.name), w.name) for w in self.weapons]
        elif kind == "ability":
            pairs = [
                (localized(ab.names, ab.name), ab.name)
                for a in self.agents
                for ab in a.abilities.values()
            ]
        elif kind == "map":
            pairs = [(localized(m.names, m.name), m.name) for m in self.maps]
        elif kind == "callout":
            pairs = []
            for game_map in self.maps:
                for callout in game_map.callouts:
                    region, super_region = callout.names.get(
                        language, (callout.region, callout.super_region)
                    )
                    pairs.append((f"{super_region}{region}", callout.label))
                    pairs.append((f"{super_region} {region}", callout.label))
        else:
            raise ValueError(f"Unknown vocabulary kind: {kind}")
        return {normalize_name(text): canonical for text, canonical in pairs if text}

    def summary(self) -> dict[str, Any]:
        return {
            "game_version": self.game_version,
            "client_version": self.client_version,
            "retrieved_at": self.retrieved_at,
            "fingerprint": self.fingerprint,
            "languages": list(self.languages),
            "agents": len(self.agents),
            "agents_by_role": {
                role: len(self.agents_by_role(role)) for role in sorted(ROLE_CANONICAL.values())
            },
            "hud_abilities": sum(len(a.hud_abilities()) for a in self.agents),
            "weapons": len(self.weapons),
            "maps": len(self.maps),
            "callouts": sum(len(m.callouts) for m in self.maps),
            "rules": len(self.rules),
        }


def _read(relative: str) -> tuple[Any, str]:
    path = resource_path(relative)
    data = path.read_bytes()
    return json.loads(data.decode("utf-8")), hashlib.sha256(data).hexdigest()


def _optional_number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def _verify_ledger(ledger: dict[str, Any], files: dict[str, str]) -> None:
    pinned: dict[str, str] = {}
    for source in ledger["sources"]:
        pinned.update(source.get("committed_files", {}))
    for relative, digest in files.items():
        expected = pinned.get(relative)
        if expected is None:
            raise ValueError(f"Knowledge file is not registered in the source ledger: {relative}")
        if expected != digest:
            raise ValueError(f"Knowledge file hash differs from the source ledger: {relative}")


def build_game_knowledge(
    en: dict[str, Any],
    localized: dict[str, dict[str, Any]],
    rules: dict[str, Any],
    *,
    fingerprint: str,
    content_status: str = "secondary_mirror",
) -> GameKnowledge:
    version = en["v"]
    game_version = ".".join(version["version"].split(".")[:2])
    prov = Provenance("valorant_api_content", version["version"], content_status)
    localized_agents = {
        lang: {row[0]: row for row in data["agents"]} for lang, data in localized.items()
    }
    localized_weapons = {
        lang: {row[0]: row for row in data["weapons"]} for lang, data in localized.items()
    }
    localized_maps = {
        lang: {row[0]: row for row in data["maps"]} for lang, data in localized.items()
    }

    agents: list[Agent] = []
    for uuid, name, role, release, _portraits, abilities_raw in en["agents"]:
        if role not in ROLE_CANONICAL:
            raise ValueError(f"Unknown agent role in snapshot: {role}")
        names = {"en-US": name}
        ability_names: dict[str, dict[str, str]] = {
            slot: {"en-US": value[0]} for slot, value in abilities_raw.items()
        }
        for lang, rows in localized_agents.items():
            row = rows.get(uuid)
            if row is None:
                continue
            names[lang] = row[1]
            for slot, text in row[3].items():
                if slot in ability_names:
                    ability_names[slot][lang] = " ".join(text.split())
        abilities: dict[str, Ability] = {}
        for slot, (ability_name, has_icon) in abilities_raw.items():
            key = API_SLOT_TO_KEY.get(slot)
            if key is None:
                raise ValueError(f"Unknown ability slot: {slot}")
            abilities[key] = Ability(
                uuid, slot, key, ability_name, ability_names[slot], bool(has_icon)
            )
        missing = [key for key in HUD_ABILITY_KEYS if key not in abilities]
        if missing:
            raise ValueError(f"{name} lacks HUD ability slots {missing}")
        agents.append(
            Agent(uuid, name, names, ROLE_CANONICAL[role], release, abilities, prov)
        )

    weapons: list[Weapon] = []
    for row in en["weapons"]:
        (uuid, name, category, cost, shop_category, fire_rate, magazine, run_speed, equip,
         reload_time, first_bullet, wall, fire_mode, ranges) = row
        names = {"en-US": name}
        for lang, rows in localized_weapons.items():
            if uuid in rows:
                names[lang] = rows[uuid][1]
        weapons.append(
            Weapon(
                uuid, name, names, category,
                None if cost is None else int(cost), shop_category,
                _optional_number(fire_rate),
                None if magazine is None else int(magazine),
                _optional_number(run_speed), _optional_number(equip),
                _optional_number(reload_time), _optional_number(first_bullet),
                wall, fire_mode,
                tuple(DamageRange(*(float(v) for v in item)) for item in ranges),
                prov,
            )
        )

    maps: list[GameMap] = []
    for uuid, name, map_url, tactical, x_mul, y_mul, x_add, y_add, callouts_raw in en["maps"]:
        names = {"en-US": name}
        localized_callouts: dict[str, list[tuple[str, str]]] = {}
        for lang, rows in localized_maps.items():
            row = rows.get(uuid)
            if row is None:
                continue
            names[lang] = row[1]
            if len(row[2]) != len(callouts_raw):
                raise ValueError(f"Localized callouts misaligned for {name} ({lang})")
            localized_callouts[lang] = [(str(item[0]), str(item[1])) for item in row[2]]
        sites = tuple(tactical.replace(" Sites", "").split("/")) if tactical else ()
        base = GameMap(uuid, name, names, map_url, sites, x_mul, y_mul, x_add, y_add, (), prov)
        callouts = []
        for index, (region, super_region, wx, wy) in enumerate(callouts_raw):
            callout_names = {"en-US": (region, super_region)}
            for lang, values in localized_callouts.items():
                callout_names[lang] = values[index]
            callouts.append(
                Callout(
                    region, super_region, callout_names, float(wx), float(wy),
                    base.world_to_minimap(float(wx), float(wy)),
                )
            )
        maps.append(
            GameMap(uuid, name, names, map_url, sites, x_mul, y_mul, x_add, y_add,
                    tuple(callouts), prov)
        )

    rule_items = {
        key: GameRule(
            key, item["value"], item.get("unit"), item["status"], item["source"], item.get("note")
        )
        for key, item in rules["rules"].items()
    }
    if rule_items["api_slot_to_key"].value != API_SLOT_TO_KEY:
        raise ValueError("Slot convention differs between rules file and code")

    knowledge = GameKnowledge(
        game_version=game_version,
        client_version=version["riotClientVersion"],
        retrieved_at=version["retrieved_at"],
        agents=tuple(agents),
        weapons=tuple(weapons),
        maps=tuple(maps),
        rules=rule_items,
        languages=("en-US", *sorted(localized)),
        fingerprint=fingerprint,
    )
    for agent in knowledge.agents:
        for text in (agent.uuid, *agent.names.values()):
            knowledge._agent_index[normalize_name(text)] = agent
        for ability in agent.abilities.values():
            for text in ability.names.values():
                key = normalize_name(text)
                knowledge._ability_index[key] = (*knowledge._ability_index.get(key, ()), ability)
    for weapon in knowledge.weapons:
        for text in (weapon.uuid, *weapon.names.values()):
            knowledge._weapon_index[normalize_name(text)] = weapon
    for game_map in knowledge.maps:
        for text in (game_map.uuid, *game_map.names.values()):
            knowledge._map_index[normalize_name(text)] = game_map
    return knowledge


@cache
def load_game_knowledge(version: str = DEFAULT_VERSION) -> GameKnowledge:
    """Load the committed, hash-pinned knowledge snapshot for ``version``."""
    files = {
        "en": f"{KNOWLEDGE_DIR}/valorant_content_en_{version}.json",
        "ja-JP": f"{KNOWLEDGE_DIR}/valorant_content_ja_{version}.json",
    }
    ledger, _ = _read(f"{KNOWLEDGE_DIR}/source_ledger_v1.json")
    rules, rules_hash = _read(f"{KNOWLEDGE_DIR}/game_rules_v1.json")
    loaded: dict[str, Any] = {}
    hashes: dict[str, str] = {}
    for lang, relative in files.items():
        loaded[lang], hashes[relative] = _read(relative)
    _verify_ledger(ledger, hashes)
    fingerprint = hashlib.sha256(
        "\n".join([*sorted(hashes.values()), rules_hash]).encode("ascii")
    ).hexdigest()[:16]
    return build_game_knowledge(
        loaded["en"], {"ja-JP": loaded["ja-JP"]}, rules, fingerprint=fingerprint
    )


def knowledge_root() -> Path:
    return resource_path(f"{KNOWLEDGE_DIR}/source_ledger_v1.json").parent

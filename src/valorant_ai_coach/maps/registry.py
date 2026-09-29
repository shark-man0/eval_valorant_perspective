from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError
from shapely.geometry import Polygon
from shapely.ops import unary_union

from valorant_ai_coach.resources import resource_path


class MapRegistryError(ValueError):
    """Raised when canonical map data or its cross-file references are invalid."""


@dataclass(slots=True)
class MapDefinition:
    data: dict[str, Any]
    callouts: dict[str, Any]
    peek: dict[str, Any]
    mask: dict[str, Any] | None
    reference_asset: Path | None

    @property
    def map_id(self) -> str:
        return str(self.data["map_id"])

    @property
    def geometry_version(self) -> str:
        return str(self.data["geometry_version"])

    @property
    def zone_index(self) -> dict[str, dict[str, Any]]:
        return {str(zone["zone_id"]): zone for zone in self.data["zones"]}

    @property
    def topology(self) -> dict[str, tuple[str, ...]]:
        """Return undirected active neighbors derived only from topology_edges."""
        neighbors: dict[str, set[str]] = {zone_id: set() for zone_id in self.zone_index}
        for edge in self.data["topology_edges"]:
            if not edge["active_by_default"]:
                continue
            left = str(edge["from_zone_id"])
            right = str(edge["to_zone_id"])
            neighbors[left].add(right)
            neighbors[right].add(left)
        return {zone_id: tuple(sorted(items)) for zone_id, items in neighbors.items()}


class MapRegistry:
    """Strict loader for the v3 production maps and explicitly requested fixtures."""

    _SCHEMA_FILES = {
        "map": "map_zone_map_schema_v3.json",
        "callouts": "callout_registry_schema_v1.json",
        "peek": "peek_exposure_registry_schema_v1.json",
        "mask": "operational_mask_schema_v1.json",
        "registry": "map_registry_schema_v1.json",
        "runtime": "map_zone_runtime_contract_schema_v1.json",
        "resolution": "zone_resolution_schema_v2.json",
    }
    _CANONICAL_PROVIDERS = ("location_label", "polygon", "coarse_fallback")
    _RESOLUTION_PRIORITY = ("location_label", "polygon", "coarse_fallback", "unknown")
    _MAX_COVERAGE_GAP = 0.12
    _MAX_CLIPPED_OVERLAP = 0.005

    def __init__(self, root: Path | None = None) -> None:
        self.root = self._bundle_root(root)
        self.schemas = {
            key: self._read_object(self.root / "schemas" / filename)
            for key, filename in self._SCHEMA_FILES.items()
        }
        self._validators: dict[str, Draft202012Validator] = {}
        for key, schema in self.schemas.items():
            try:
                Draft202012Validator.check_schema(schema)
            except SchemaError as exc:
                raise MapRegistryError(f"Invalid {key} schema: {exc.message}") from exc
            self._validators[key] = Draft202012Validator(schema)

        self.registry = self._read_object(self.root / "config" / "map_registry_v1.json")
        self.runtime = self._read_object(self.root / "config" / "map_zone_runtime_contract_v4.json")
        self._validate("registry", self.registry, "map registry")
        self._validate("runtime", self.runtime, "runtime contract")
        self.data = self.registry
        if tuple(self.runtime["canonical_provider_ids"]) != self._CANONICAL_PROVIDERS:
            raise MapRegistryError("Runtime provider ids do not match the canonical order")

        self._definitions: dict[str, MapDefinition] = {}

    @staticmethod
    def _bundle_root(root: Path | None) -> Path:
        if root is None:
            return resource_path("config/map_zone_v3/config/map_registry_v1.json").parents[1]
        candidate = Path(root).expanduser().resolve()
        if (candidate / "config" / "map_registry_v1.json").is_file():
            return candidate
        nested = candidate / "config" / "map_zone_v3"
        if (nested / "config" / "map_registry_v1.json").is_file():
            return nested
        return candidate

    @staticmethod
    def _read_object(path: Path) -> dict[str, Any]:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise MapRegistryError(f"Cannot read JSON object {path}: {exc}") from exc
        if not isinstance(value, dict):
            raise MapRegistryError(f"JSON object required: {path}")
        MapRegistry._require_finite_numbers(value, str(path))
        return value

    @staticmethod
    def _require_finite_numbers(value: Any, label: str, path: str = "$") -> None:
        if isinstance(value, float) and not math.isfinite(value):
            raise MapRegistryError(f"Non-finite number in {label} at {path}")
        if isinstance(value, dict):
            for key, child in value.items():
                MapRegistry._require_finite_numbers(child, label, f"{path}.{key}")
        elif isinstance(value, list):
            for index, child in enumerate(value):
                MapRegistry._require_finite_numbers(child, label, f"{path}[{index}]")

    def _validate(self, schema_name: str, value: Any, label: str) -> None:
        errors = sorted(
            self._validators[schema_name].iter_errors(value),
            key=lambda error: tuple(str(part) for part in error.absolute_path),
        )
        if errors:
            details = "; ".join(
                f"{'/'.join(str(part) for part in error.absolute_path) or '$'}: {error.message}"
                for error in errors[:8]
            )
            raise MapRegistryError(f"{label} violates its schema: {details}")

    def _path(self, relative: str) -> Path:
        path = (self.root / relative).resolve()
        try:
            path.relative_to(self.root.resolve())
        except ValueError as exc:
            raise MapRegistryError(f"Asset path escapes map bundle: {relative}") from exc
        return path

    def load(self, map_id: str, *, allow_fixture: bool = False) -> MapDefinition:
        production = self.registry["maps"].get(map_id)
        if production is not None:
            if map_id in self._definitions:
                return self._definitions[map_id]
            definition = self._load_production(map_id, production)
        else:
            fixture = self.registry["test_fixtures"].get(map_id)
            if fixture is None:
                raise KeyError(f"Unknown map id: {map_id}")
            if not allow_fixture:
                raise MapRegistryError(
                    f"Map fixture {map_id!r} is test-only; pass allow_fixture=True explicitly"
                )
            if map_id in self._definitions:
                return self._definitions[map_id]
            definition = self._load_fixture(map_id, fixture)
        self._definitions[map_id] = definition
        return definition

    def _load_production(self, map_id: str, entry: dict[str, Any]) -> MapDefinition:
        data = self._read_object(self._path(entry["map_file"]))
        callouts = self._read_object(self._path(entry["callout_registry_file"]))
        peek = self._read_object(self._path(entry["peek_registry_file"]))
        mask = self._read_object(self._path(entry["coverage_mask_file"]))
        for schema_name, value, label in (
            ("map", data, f"map {map_id}"),
            ("callouts", callouts, f"callouts for {map_id}"),
            ("peek", peek, f"peek registry for {map_id}"),
            ("mask", mask, f"operational mask for {map_id}"),
        ):
            self._validate(schema_name, value, label)

        reference_asset = self._path(entry["reference_asset"])
        self._check_production_integrity(map_id, entry, data, callouts, peek, mask, reference_asset)
        return MapDefinition(data, callouts, peek, mask, reference_asset)

    def _load_fixture(self, fixture_id: str, entry: dict[str, Any]) -> MapDefinition:
        data = self._read_object(self._path(entry["map_file"]))
        self._validate("map", data, f"fixture map {fixture_id}")
        if data.get("map_id") != fixture_id or data.get("geometry_status") != "test_fixture":
            raise MapRegistryError(f"Fixture identity/status mismatch: {fixture_id}")
        self._check_map_integrity(data, verify_geometry=False)
        return MapDefinition(data, {}, {}, None, None)

    def _check_production_integrity(
        self,
        map_id: str,
        entry: dict[str, Any],
        data: dict[str, Any],
        callouts: dict[str, Any],
        peek: dict[str, Any],
        mask: dict[str, Any],
        reference_asset: Path,
    ) -> None:
        if data.get("map_id") != map_id or callouts.get("map_id") != map_id:
            raise MapRegistryError(f"Map/callout map_id mismatch for {map_id}")
        if peek.get("map_id") != map_id or mask.get("map_id") != map_id:
            raise MapRegistryError(f"Peek/mask map_id mismatch for {map_id}")
        version = data.get("geometry_version")
        if version != entry.get("geometry_version"):
            raise MapRegistryError(f"Registered geometry version mismatch for {map_id}")
        if data.get("coverage_mask_file") != entry.get("coverage_mask_file"):
            raise MapRegistryError(f"Map coverage mask reference mismatch for {map_id}")
        if not reference_asset.is_file():
            raise MapRegistryError(f"Missing reference asset for {map_id}: {reference_asset}")
        if mask.get("reference_asset") != entry.get("reference_asset"):
            raise MapRegistryError(f"Reference asset path mismatch for {map_id}")
        if mask.get("reference_sha256") != entry.get("reference_sha256"):
            raise MapRegistryError(f"Registry and mask SHA-256 differ for {map_id}")
        actual_hash = hashlib.sha256(reference_asset.read_bytes()).hexdigest()
        if actual_hash != entry.get("reference_sha256"):
            raise MapRegistryError(f"Reference asset SHA-256 mismatch for {map_id}")

        self._check_map_integrity(data, verify_geometry=True)
        zone_ids = {zone["zone_id"] for zone in data["zones"]}
        for name, record in callouts["records"].items():
            if record["zone_id"] not in zone_ids:
                raise MapRegistryError(
                    f"Callout {name!r} references unknown zone {record['zone_id']!r}"
                )
        site_ids = {site["site_id"] for site in data["sites"]}
        for anchor in peek["anchors"]:
            if anchor["zone_id"] not in zone_ids:
                raise MapRegistryError(f"Peek anchor references unknown zone {anchor['zone_id']!r}")
            if anchor["site_id"] is not None and anchor["site_id"] not in site_ids:
                raise MapRegistryError(f"Peek anchor references unknown site {anchor['site_id']!r}")
        self._check_coverage(mask, data)

    def _check_map_integrity(self, data: dict[str, Any], *, verify_geometry: bool) -> None:
        if tuple(data.get("resolution_priority", ())) != self._RESOLUTION_PRIORITY:
            raise MapRegistryError(
                "Map resolution_priority does not match the canonical provider order"
            )
        if "adjacency" in data:
            raise MapRegistryError("topology_edges must be the only authored topology source")

        zones = data["zones"]
        zone_ids = [zone["zone_id"] for zone in zones]
        if len(zone_ids) != len(set(zone_ids)):
            raise MapRegistryError(f"Duplicate zone ids in map {data.get('map_id')}")
        zone_index = {zone["zone_id"]: zone for zone in zones}
        polygons: dict[str, Polygon] = {}
        for zone in zones:
            polygon = Polygon(zone["polygon_norm"])
            if not polygon.is_valid or polygon.area <= 0:
                raise MapRegistryError(f"Invalid or empty polygon for zone {zone['zone_id']}")
            if verify_geometry:
                polygons[zone["zone_id"]] = polygon

        seen_edges: set[frozenset[str]] = set()
        for edge in data["topology_edges"]:
            left = edge["from_zone_id"]
            right = edge["to_zone_id"]
            if left not in zone_index or right not in zone_index:
                raise MapRegistryError(f"Topology edge references unknown zone: {left} -> {right}")
            key = frozenset((left, right))
            if left == right or key in seen_edges:
                raise MapRegistryError(f"Duplicate or self topology edge: {left} -> {right}")
            seen_edges.add(key)

        seen_sites: set[str] = set()
        listed_site_zones: set[str] = set()
        for site in data["sites"]:
            site_id = site["site_id"]
            if site_id in seen_sites:
                raise MapRegistryError(f"Duplicate site id: {site_id}")
            seen_sites.add(site_id)
            for zone_id in site["zone_ids"]:
                zone = zone_index.get(zone_id)
                if zone is None or zone["kind"] != "site" or zone["site_id"] != site_id:
                    raise MapRegistryError(
                        f"Site {site_id!r} has inconsistent site zone {zone_id!r}"
                    )
                listed_site_zones.add(zone_id)

        valid_site_ids = {site["site_id"] for site in data["sites"]}
        for zone in zones:
            for affinity in zone["site_affinity"]:
                if affinity not in valid_site_ids:
                    raise MapRegistryError(
                        f"Zone {zone['zone_id']!r} references unknown site affinity {affinity!r}"
                    )
            if zone["kind"] == "site" and zone["zone_id"] not in listed_site_zones:
                raise MapRegistryError(f"Site zone {zone['zone_id']!r} is missing from sites[]")

        if verify_geometry and len(polygons) != len(zones):
            raise MapRegistryError("Not all map polygons passed geometry validation")

    def _check_coverage(self, mask_data: dict[str, Any], map_data: dict[str, Any]) -> None:
        mask_polygon = Polygon(mask_data["polygon_norm"])
        if not mask_polygon.is_valid or mask_polygon.area <= 0:
            raise MapRegistryError("Operational mask polygon is invalid or empty")
        clipped: dict[str, Any] = {}
        for zone in map_data["zones"]:
            polygon = Polygon(zone["polygon_norm"])
            clipped[zone["zone_id"]] = polygon.intersection(mask_polygon)

        overlap_area = 0.0
        zone_ids = list(clipped)
        for index, left in enumerate(zone_ids):
            for right in zone_ids[index + 1 :]:
                overlap_area += clipped[left].intersection(clipped[right]).area
        covered = unary_union(list(clipped.values()))
        gap_ratio = mask_polygon.difference(covered).area / mask_polygon.area
        overlap_ratio = overlap_area / mask_polygon.area
        if gap_ratio > self._MAX_COVERAGE_GAP + 1e-12:
            raise MapRegistryError(f"Operational mask coverage gap is too large: {gap_ratio:.6f}")
        if overlap_ratio > self._MAX_CLIPPED_OVERLAP + 1e-12:
            raise MapRegistryError(
                f"Operational mask clipped zone overlap is too large: {overlap_ratio:.6f}"
            )

    def select(
        self,
        manual_map_id: str | None = None,
        map_label: str | None = None,
        label_confidence: float = 0,
        template_scores: dict[str, float] | None = None,
    ) -> str | None:
        """Apply explicit, trusted-label, template, then unresolved selection."""
        if manual_map_id is not None:
            if manual_map_id not in self.registry["maps"]:
                raise KeyError(f"Unknown production map id: {manual_map_id}")
            return manual_map_id

        label_confidence = self._confidence(label_confidence, "label_confidence")
        trusted_min = float(self.runtime["fusion_thresholds"]["accept"])
        if map_label is not None and label_confidence >= trusted_min:
            normalized = self._normalize_label(map_label)
            for candidate_id in self.registry["maps"]:
                definition = self.load(candidate_id)
                labels = {
                    self._normalize_label(candidate_id),
                    self._normalize_label(definition.data["display_name"]),
                }
                if normalized in labels:
                    return str(candidate_id)

        scores = template_scores or {}
        minimum = float(self.registry["selection_policy"]["map_template_match_min_confidence"])
        accepted: list[tuple[str, float]] = []
        for candidate_id in self.registry["maps"]:
            if candidate_id not in scores:
                continue
            score = self._confidence(scores[candidate_id], f"template_scores[{candidate_id!r}]")
            if score >= minimum:
                accepted.append((candidate_id, score))
        if not accepted:
            return None
        accepted.sort(key=lambda item: item[1], reverse=True)
        if len(accepted) > 1 and math.isclose(accepted[0][1], accepted[1][1], abs_tol=1e-12):
            return None
        return accepted[0][0]

    @staticmethod
    def _normalize_label(value: str) -> str:
        return " ".join(value.strip().casefold().replace("_", " ").replace("-", " ").split())

    @staticmethod
    def _confidence(value: float, label: str) -> float:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"{label} must be a finite number in [0, 1]")
        number = float(value)
        if not math.isfinite(number) or not 0 <= number <= 1:
            raise ValueError(f"{label} must be a finite number in [0, 1]")
        return number

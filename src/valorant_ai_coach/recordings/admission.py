"""Binding the older admission paths to the recording catalog (#62 follow-up).

The catalog is the single source of truth for which recording may be used for what.
Older workflows (the staged six-source reservation, the second-recording activation
and hand-written ``SourcePolicy`` files) decided admission from their own allocation
files. This module lets them ask the catalog instead, without changing what they
analyse:

* ``require_catalog`` insists on a catalog unless the explicit compatibility mode
  (``legacy_compat`` / ``VALORANT_RECORDING_LEGACY_COMPAT=1``) is chosen.
* ``resolve_catalog`` finds the catalog given explicitly or through
  ``VALORANT_RECORDING_CATALOG`` (and an optional JSON path map in
  ``VALORANT_RECORDING_PATH_MAP`` for a mounted copy of the storage).
* ``check_allowlist`` refuses an allow-list whose recordings are unknown to the
  catalog, sit in another split, or may not be used for development.
* ``admit_for_development`` checks one recording, records the exposure in the catalog
  journal and returns a catalog-mode ``SourcePolicy`` description.
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from .catalog import LEGACY_SPLIT_NAMES, CatalogError, LeakageError, RecordingCatalog

ENV_CATALOG = "VALORANT_RECORDING_CATALOG"
ENV_PATH_MAP = "VALORANT_RECORDING_PATH_MAP"
ENV_LEGACY_COMPAT = "VALORANT_RECORDING_LEGACY_COMPAT"
CATALOG_REQUIRED = (
    "正式運用では録画カタログの指定が必要です（--catalog または "
    f"{ENV_CATALOG}）。旧方式は互換モード（--legacy-compat または "
    f"{ENV_LEGACY_COMPAT}=1）でのみ使えます"
)


def environment_path_map() -> dict[str, str]:
    raw = os.environ.get(ENV_PATH_MAP)
    if not raw:
        return {}
    value = json.loads(raw)
    if not isinstance(value, dict) or not all(
        isinstance(k, str) and isinstance(v, str) for k, v in value.items()
    ):
        raise CatalogError(f"{ENV_PATH_MAP} は文字列どうしのJSONオブジェクトです")
    return value


def resolve_catalog(
    explicit: str | Path | None = None, *, path_map: Mapping[str, str] | None = None
) -> RecordingCatalog | None:
    """The catalog named explicitly, else by the environment, else ``None``."""
    root = explicit if explicit not in (None, "") else os.environ.get(ENV_CATALOG)
    if not root:
        return None
    mapping = dict(path_map) if path_map is not None else environment_path_map()
    return RecordingCatalog(Path(root), path_map=mapping)


def legacy_compat_requested(explicit: bool = False) -> bool:
    """The old allocation-file-only admission, only when asked for explicitly."""
    return bool(explicit) or os.environ.get(ENV_LEGACY_COMPAT) == "1"


def require_catalog(
    explicit: str | Path | None = None,
    *,
    legacy_compat: bool = False,
    path_map: Mapping[str, str] | None = None,
) -> RecordingCatalog | None:
    """The catalog, which formal operation requires.

    ``None`` is returned only in the explicit compatibility mode; otherwise a missing
    catalog is an error, so no admission path silently bypasses the leak prevention.
    """
    catalog = resolve_catalog(explicit, path_map=path_map)
    if catalog is None and not legacy_compat_requested(legacy_compat):
        raise CatalogError(CATALOG_REQUIRED)
    return catalog


def _legacy_split(row: Mapping[str, Any]) -> str | None:
    """Split of a legacy row in catalog names (``*_CANDIDATE`` -> catalog split)."""
    value = row.get("split")
    if value is None:
        return None
    return LEGACY_SPLIT_NAMES.get(str(value), f"unknown:{value}")


def _legacy_physical(row: Mapping[str, Any]) -> str | None:
    """Physical match of a legacy row; ``import_legacy`` falls back to the row id."""
    value = row.get("physical_match_id") or row.get("video_id") or row.get("source_id")
    return None if value is None else str(value)


def check_allowlist(
    catalog: RecordingCatalog,
    records: Iterable[Mapping[str, Any]],
    *,
    purpose: str = "development_analysis",
) -> list[str]:
    """Every admitted recording must be in the catalog, in the same split, and allowed.

    ``records`` are allow-list rows with ``source_sha256`` and, when known, ``split``
    and ``physical_match_id``. Returns the catalog recording ids.
    """
    identifiers: list[str] = []
    problems: list[str] = []
    for row in records:
        recording = catalog.state.by_sha(str(row.get("source_sha256")))
        if recording is None:
            problems.append(f"{row.get('video_id') or row.get('source_id')}: カタログに未登録")
            continue
        split = _legacy_split(row)
        if split is not None and split != recording.split:
            problems.append(
                f"{recording.recording_id}: 旧来の割当({split})とカタログ({recording.split})が違う"
            )
            continue
        physical = _legacy_physical(row)
        if physical is not None and physical.casefold() != str(
            recording.physical_match_id
        ).casefold():
            problems.append(f"{recording.recording_id}: 物理試合IDがカタログと違う")
            continue
        identifiers.append(recording.recording_id)
    if problems:
        raise LeakageError("; ".join(problems))
    catalog.guard(identifiers, purpose)
    return identifiers


def admit_for_development(
    catalog: RecordingCatalog,
    *,
    source_sha256: str,
    split: str,
    protected_source_sha256s: Iterable[str],
    note: str,
) -> dict[str, Any]:
    """Admit one recording for development use through the catalog.

    The exposure is journaled before the policy is returned, so a recording can never
    be analysed without the catalog knowing it was seen.
    """
    (identifier,) = check_allowlist(
        catalog, [{"source_sha256": source_sha256, "split": split}]
    )
    catalog.record_exposure(identifier, "development_use", note)
    return {
        "catalog": str(catalog.root),
        "allowed_recording_ids": [identifier],
        "protected_source_sha256s": sorted(set(protected_source_sha256s)),
    }


def precheck_allocation(catalog: RecordingCatalog, records: Iterable[Mapping[str, Any]]) -> None:
    """A new allocation may not contradict the catalog (same bytes or match elsewhere).

    Uses exactly the checks of the later ``import_legacy(atomic=True)``, so nothing is
    written by the caller unless the import will succeed.
    """
    conflicts = catalog.legacy_conflicts(list(records))
    if conflicts:
        raise LeakageError(
            "; ".join(f"{item['recording_id']}: カタログと衝突（{item['reason']}）"
                      for item in conflicts)
        )

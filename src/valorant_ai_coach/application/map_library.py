"""Private, recording-bound development Map packages for the desktop application."""

from __future__ import annotations

import os
from dataclasses import dataclass
from http.server import ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from valorant_ai_coach.temporal.evidence import digest, is_sha
from valorant_ai_coach.temporal.map_timeline_report import load_map_timeline
from valorant_ai_coach.temporal.replay import SourcePolicy, file_sha, read_json, write_private

SCHEMA = "development_map_library_entry_v1"
_INPUTS = ("bundle", "policy", "standard", "recovered", "evaluation")
_ARTIFACTS = (*_INPUTS, "completion", "display")


@dataclass(frozen=True)
class MapLibraryEntry:
    receipt: Path
    recording_id: str
    label: str


def _bind(path: Path) -> dict[str, str]:
    # Keep the path inside the package, even when the producer uses a symlink.
    return {"path": str(path.absolute()), "sha256": file_sha(path)}


def _validate(paths: dict[str, Path]) -> tuple[str, str]:
    bundle = read_json(paths["bundle"])
    source = bundle["source"]
    policy = SourcePolicy(read_json(paths["policy"]))
    admitted = policy.allowed.get(source["source_sha256"])
    if (not policy.catalog_checked or admitted is None or len(policy.allowed) != 1
            or admitted["split"] != "DEVELOPMENT"
            or admitted["physical_match_id"] != source["physical_match_id"]):
        raise ValueError("A single catalog-admitted DEVELOPMENT recording is required")
    completion = read_json(paths["completion"])
    if (bundle.get("formal_outputs") != 0 or completion.get("formal_outputs", 0) != 0
            or completion["output_sha256s"][paths["bundle"].name] != file_sha(paths["bundle"])):
        raise ValueError("Map library requires an intact development timeline")
    recovered = read_json(paths["recovered"])
    if recovered.get("primary_report_sha256") != file_sha(paths["standard"]):
        raise ValueError("The Map reports must be the exact standard/recovered pair")
    load_map_timeline(paths["standard"], paths["bundle"], bundle)
    result = load_map_timeline(paths["recovered"], paths["bundle"], bundle)
    display = read_json(paths["display"])
    if (display.get("formal_outputs") != 0
            or display.get("report_sha256") != file_sha(paths["recovered"])):
        raise ValueError("The atlas display receipt must match the recovered Map report")
    evaluation = read_json(paths["evaluation"])
    development = evaluation["development_map"]
    if (evaluation.get("formal_outputs") != 0 or evaluation["formal_promotion"] is not None
            or evaluation["source"]["source_id"] != source["source_id"]
            or evaluation["source"]["physical_match_id"] != source["physical_match_id"]
            or development.get("formal_outputs") != 0
            or development["summary"] != result["summary"]):
        raise ValueError("The assessment must match the Map report with formal promotion disabled")
    return str(admitted["video_id"]), str(source["source_sha256"])


def publish_map_package(
    library: Path, *, label: str, bundle: Path, policy: Path, standard: Path,
    recovered: Path, evaluation: Path,
) -> Path:
    """Publish once; a later compatible recognizer result creates another entry."""
    library = library.resolve()
    if any((p / ".git").exists() for p in (library, *library.parents)):
        raise ValueError("Map library packages must stay outside Git checkouts")
    paths = {
        "bundle": bundle, "policy": policy, "standard": standard, "recovered": recovered,
        "evaluation": evaluation, "completion": bundle.parent / "completion_PRIVATE.json",
        "display": recovered.with_suffix(".display.json"),
    }
    recording, source_sha = _validate(paths)
    data = {
        "schema": SCHEMA, "recording_id": recording, "source_sha256": source_sha,
        "label": label, "formal_outputs": 0, "artifacts": {k: _bind(v) for k, v in paths.items()},
    }
    library.mkdir(parents=True, mode=0o700, exist_ok=True)
    destination = library / f"{digest(data)}_PRIVATE.json"
    with TemporaryDirectory(dir=library) as temporary:
        staged = Path(temporary) / destination.name
        write_private(staged, data)
        try:
            os.link(staged, destination)
        except FileExistsError:
            if read_json(destination) != data:
                raise ValueError("A Map library receipt has changed") from None
    return destination


def _receipt(path: Path) -> dict[str, Any]:
    data: dict[str, Any] = read_json(path)
    valid_name = f"{digest(data)}_PRIVATE.json"
    if (path.is_symlink() or path.name != valid_name or data.get("schema") != SCHEMA
            or data.get("formal_outputs") != 0 or not is_sha(data.get("source_sha256"))
            or set(data["artifacts"]) != set(_ARTIFACTS)):
        raise ValueError("Invalid development Map library receipt")
    return data


def list_map_packages(library: Path) -> list[MapLibraryEntry]:
    """List the most recently published package for each registered recording."""
    entries: dict[str, MapLibraryEntry] = {}
    receipts = sorted(library.glob("*_PRIVATE.json"), key=lambda p: p.stat().st_mtime_ns)
    for path in receipts:
        data = _receipt(path)
        recording = data["recording_id"]
        entries[recording] = MapLibraryEntry(path, recording, data["label"])
    return sorted(entries.values(), key=lambda row: (row.label, row.recording_id))


def verified_map_package(receipt: Path) -> dict[str, Path]:
    data = _receipt(receipt)
    paths = {key: Path(row["path"]) for key, row in data["artifacts"].items()}
    for key, path in paths.items():
        if data["artifacts"][key]["sha256"] != file_sha(path):
            raise ValueError("A bound Map library artifact has changed")
    if (paths["completion"] != paths["bundle"].parent / "completion_PRIVATE.json"
            or paths["display"] != paths["recovered"].with_suffix(".display.json")
            or _validate(paths) != (data["recording_id"], data["source_sha256"])):
        raise ValueError("Map library receipt points to a different recording")
    return paths


def open_map_package(receipt: Path) -> ThreadingHTTPServer:
    from valorant_ai_coach.temporal.viewer import make_server

    paths = verified_map_package(receipt)
    return make_server(
        paths["bundle"], paths["policy"], map_report_path=paths["recovered"],
        standard_map_report_path=paths["standard"], evaluation_path=paths["evaluation"],
    )

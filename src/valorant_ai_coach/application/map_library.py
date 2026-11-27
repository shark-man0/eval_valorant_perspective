"""Private, recording-bound development Map packages for the desktop application."""

from __future__ import annotations

import os
from dataclasses import dataclass
from http.server import ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from valorant_ai_coach.temporal.evidence import digest, is_sha
from valorant_ai_coach.temporal.map_recorder_path import measured_native_edges
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
    variant: str = ""


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
    if "parent" in paths:
        parent = _receipt(paths["parent"])
        for key in _ARTIFACTS:
            if parent["artifacts"][key] != _bind(paths[key]):
                raise ValueError("A generation changed its original package dependencies")
        if not any(
            file_sha(paths["incumbent"]) == parent["artifacts"][key]["sha256"]
            and paths["incumbent"].resolve() == Path(parent["artifacts"][key]["path"]).resolve()
            for key in ("standard", "recovered", "tracked") if key in parent["artifacts"]
        ):
            raise ValueError("The generation incumbent differs from its parent")
    if "tracked" in paths:
        tracker = read_json(paths["tracked"])
        replay = tracker["multi_marker_replay"]
        hashes = replay["input_sha256s"]
        baseline = next(
            (paths[key] for key in ("incumbent", "recovered", "standard") if key in paths
             if file_sha(paths[key]) == hashes.get("incumbent")), None,
        )
        if (replay.get("method") != "development_map_multi_marker_track_v1"
                or replay.get("formal_outputs") != 0 or baseline is None
                or hashes.get("bundle") != file_sha(paths["bundle"])):
            raise ValueError("追跡結果と元の解析結果・共通タイムラインが一致しません")
        load_map_timeline(paths["tracked"], paths["bundle"], bundle)
        before = read_json(baseline)
        if (tracker.get("zone_catalog_sha256") != before.get("zone_catalog_sha256")
                or tracker.get("frame_manifest_sha256") != before.get("frame_manifest_sha256")
                or not {digest(p) for seg in before["segments"] for p in seg}
                <= {digest(p) for seg in tracker["segments"] for p in seg}
                or not measured_native_edges(before) <= measured_native_edges(tracker)):
            raise ValueError("追跡結果が元のMap観測・Zone・軌跡を変更しています")
    return str(admitted["video_id"]), str(source["source_sha256"])


def publish_map_package(
    library: Path, *, label: str, bundle: Path, policy: Path, standard: Path,
    recovered: Path, evaluation: Path, variant: str = "", tracked: Path | None = None,
    parent: Path | None = None, incumbent: Path | None = None,
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
    if tracked is not None:
        tracked = tracked.resolve()
        if any((p / ".git").exists() for p in tracked.parents):
            raise ValueError("追跡結果をGit管理外のフォルダーに保存してください")
        paths["tracked"] = tracked
    if parent is not None or incumbent is not None:
        if parent is None or incumbent is None or tracked is None:
            raise ValueError("A generation requires its parent and exact incumbent")
        paths.update(parent=parent.resolve(), incumbent=incumbent.resolve())
    recording, source_sha = _validate(paths)
    data = {
        "schema": SCHEMA, "recording_id": recording, "source_sha256": source_sha,
        "label": label, "formal_outputs": 0, "artifacts": {k: _bind(v) for k, v in paths.items()},
        **({"variant": variant} if variant else {}),
    }
    data["generation"] = digest(data["artifacts"])
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
            or set(data["artifacts"]) not in (
                set(_ARTIFACTS), {*_ARTIFACTS, "tracked"},
                {*_ARTIFACTS, "tracked", "parent", "incumbent"},
            )
            or ("generation" in data and data["generation"] != digest(data["artifacts"]))):
        raise ValueError("Invalid development Map library receipt")
    return data


def list_map_packages(library: Path, *, all_versions: bool = False) -> list[MapLibraryEntry]:
    """List the latest or all immutable packages for each registered recording."""
    library = library.resolve()
    entries: list[MapLibraryEntry] = []
    seen = set()
    receipts = sorted(
        library.glob("*_PRIVATE.json"), key=lambda p: (p.stat().st_mtime_ns, p.name), reverse=True,
    )
    for path in receipts:
        data = _receipt(path)
        recording = data["recording_id"]
        if not all_versions and "tracked" in data["artifacts"]:
            continue
        if all_versions or recording not in seen:
            entries.append(MapLibraryEntry(path, recording, data["label"], data.get("variant", "")))
        seen.add(recording)
    return sorted(entries, key=lambda row: (row.label, row.recording_id))


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


def attach_map_tracker(library: Path, receipt: Path, tracked: Path) -> Path:
    """Register a B result alongside its original immutable standard and recovery pair."""
    data = _receipt(receipt)
    paths = verified_map_package(receipt)
    hashes = read_json(tracked)["multi_marker_replay"]["input_sha256s"]
    baseline = next((paths[key] for key in ("tracked", "recovered", "standard")
                     if key in paths and file_sha(paths[key]) == hashes.get("incumbent")), None)
    if baseline is None:
        raise ValueError("追跡結果の基準と選択した解析世代が一致しません")
    variant = data.get("variant") or "既存結果"
    return publish_map_package(
        library, label=data["label"], variant=f"{variant} · 追跡 {file_sha(tracked)[:8]}",
        tracked=tracked, parent=receipt, incumbent=baseline,
        **{key: paths[key] for key in _INPUTS},
    )


def compare_map_packages(before: Path, after: Path) -> dict[str, dict[str, int]]:
    """Compare two model versions only against the same source and exact timeline."""
    old, new = verified_map_package(before), verified_map_package(after)
    if file_sha(old["bundle"]) != file_sha(new["bundle"]):
        raise ValueError("モデル比較には同一録画・同一の共通タイムラインが必要です")

    def positions(report: dict[str, Any]) -> set[int]:
        return {
            row["timestamp"] for row in report["second_rows"]
            if any(point["kind"] == "selected" for point in row["recorder_map_observations"])
        }

    result = {}
    comparisons = {mode: (old[mode], new[mode]) for mode in ("standard", "recovered")}
    if "tracked" in new or "tracked" in old:
        tracked = new if "tracked" in new else old
        replay = read_json(tracked["tracked"])["multi_marker_replay"]
        baseline = ("standard" if file_sha(tracked["standard"])
                    == replay["input_sha256s"]["incumbent"] else "recovered")
        comparisons["tracked"] = (old.get("tracked", old[baseline]),
                                  new.get("tracked", new[baseline]))
    for mode, (first_file, second_file) in comparisons.items():
        a, b = read_json(first_file), read_json(second_file)
        first, second = positions(a), positions(b)
        left, right = measured_native_edges(a), measured_native_edges(b)
        result[mode] = {
            "before_seconds": len(first), "after_seconds": len(second),
            "added_seconds": len(second - first), "lost_seconds": len(first - second),
            "added_edges": len(right - left), "lost_edges": len(left - right),
        }
    return result


def open_map_package(receipt: Path) -> ThreadingHTTPServer:
    from valorant_ai_coach.temporal.viewer import make_server

    paths = verified_map_package(receipt)
    return make_server(
        paths["bundle"], paths["policy"], map_report_path=paths["recovered"],
        standard_map_report_path=paths["standard"], evaluation_path=paths["evaluation"],
        tracked_map_report_path=paths.get("tracked"),
    )

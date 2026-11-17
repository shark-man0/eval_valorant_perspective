"""Catalog -> continual-learning registry (#154).

The fake follows the #154 ``DatasetRegistry`` contract and always runs. The second
test runs against the real class once #154 is on main (it is skipped until then), so
the formal ``sync-learning`` step is checked the moment both are integrated.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pytest

from valorant_ai_coach.recordings import RecordingCatalog


def _catalog_with_archives(tmp_path: Path) -> tuple[RecordingCatalog, Path]:
    catalog = RecordingCatalog.create(tmp_path / "private" / "catalog", seed="s")
    registry_rows = []
    for index, split in enumerate(["TRAIN", "VALIDATION", "DEV_COMPARISON"]):
        video = tmp_path / "videos" / f"{index}.mp4"
        video.parent.mkdir(exist_ok=True)
        video.write_bytes(f"match {index}".encode("ascii") * (40 + index))
        rid = catalog.register(video, physical_match_id=f"m{index}",
                               split="DEVELOPMENT").recording_id
        archive = tmp_path / "crops" / f"fm1_{index}.zip"
        archive.parent.mkdir(exist_ok=True)
        archive.write_bytes(f"crop {index}".encode("ascii") * (9 + index))
        catalog.register_artifact(kind="frames", parents=[rid], producer={"name": "crop"},
                                  path=archive)
        registry_rows.append({
            "source_id": f"fm1_{index}", "physical_match_id": f"physical:fm1_{index}",
            "split": split,
            "source_video_sha256": catalog.state.recordings[rid].source_sha256,
        })
    assignment = tmp_path / "assignment.json"
    assignment.write_text(json.dumps({"seed": "continual-v1", "sources": registry_rows}),
                          encoding="utf-8")
    assert catalog.import_learning_assignment(assignment)["adopted"] == 3
    return catalog, assignment


@dataclass
class _Record:
    source_id: str
    split: str
    source_video_sha256: str


class _Registry:
    def __init__(self) -> None:
        self.records: dict[str, _Record] = {}

    def intake(self, source_id, physical_match_id, archive, *, source_video_sha256,
               split=None, unexposed=False, note=""):
        if source_id in self.records:
            return self.records[source_id], False
        self.records[source_id] = _Record(source_id, split, source_video_sha256)
        return self.records[source_id], True


def test_dry_run_reports_without_writing_and_detects_split_drift(tmp_path):
    catalog, _ = _catalog_with_archives(tmp_path)
    rows = catalog.learning_archives()
    registry = _Registry()
    assert catalog.sync_learning_registry(registry, rows, dry_run=True) == {
        "would_add": 3, "already_present": 0, "split_mismatch": 0, "id_mismatch": 0}
    assert registry.records == {}
    catalog.sync_learning_registry(registry, rows)
    assert catalog.sync_learning_registry(registry, rows, dry_run=True)[
        "already_present"] == 3
    registry.records["fm1_0"].split = "VALIDATION"  # the registry drifted
    assert catalog.sync_learning_registry(registry, rows, dry_run=True)[
        "split_mismatch"] == 1


def test_sync_into_the_real_continual_learning_registry(tmp_path):
    learning = pytest.importorskip("valorant_ai_coach.learning.registry")
    catalog, _ = _catalog_with_archives(tmp_path)
    rows = catalog.learning_archives()
    registry = learning.DatasetRegistry(tmp_path / "ws" / "dataset_registry.json")
    assert catalog.sync_learning_registry(registry, rows, dry_run=True)["would_add"] == 3
    assert catalog.sync_learning_registry(registry, rows) == {"added": 3,
                                                              "already_present": 0}
    assert {r.source_id: r.split for r in registry.records.values()} == {
        "fm1_0": "TRAIN", "fm1_1": "VALIDATION", "fm1_2": "DEV_COMPARISON"}
    assert catalog.sync_learning_registry(registry, rows) == {"added": 0,
                                                              "already_present": 3}

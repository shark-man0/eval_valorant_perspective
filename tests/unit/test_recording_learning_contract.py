"""Catalog -> continual-learning registry (#154).

The fake follows the #154 ``DatasetRegistry`` contract and always runs. The second
test runs against the real class once #154 is on main (it is skipped until then), so
the formal ``sync-learning`` step is checked the moment both are integrated.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import pytest

from valorant_ai_coach.recordings import LeakageError, RecordingCatalog


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
    physical_match_id: str
    split: str
    source_video_sha256: str
    archive_sha256: str


class _Registry:
    def __init__(self) -> None:
        self.records: dict[str, _Record] = {}

    def intake(self, source_id, physical_match_id, archive, *, source_video_sha256,
               split=None, unexposed=False, note=""):
        if source_id in self.records:
            return self.records[source_id], False
        self.records[source_id] = _Record(
            source_id, physical_match_id, split, source_video_sha256,
            hashlib.sha256(Path(archive).read_bytes()).hexdigest(),
        )
        return self.records[source_id], True


PROBLEMS = ("archive_changed", "catalog_mismatch", "physical_split_conflict", "id_mismatch",
            "physical_mismatch", "source_sha_mismatch", "archive_mismatch", "split_mismatch")


def test_dry_run_and_real_sync_share_every_check(tmp_path):
    catalog, _ = _catalog_with_archives(tmp_path)
    rows = catalog.learning_archives()
    registry = _Registry()
    plan = catalog.sync_learning_registry(registry, rows, dry_run=True)
    assert plan == {"would_add": 3, "already_present": 0, **dict.fromkeys(PROBLEMS, 0)}
    assert registry.records == {}
    result = catalog.sync_learning_registry(registry, rows)
    assert (result["added"], result["already_present"]) == (3, 0)
    assert catalog.sync_learning_registry(registry, rows, dry_run=True)[
        "already_present"] == 3

    drifts = {
        "split_mismatch": ("split", "VALIDATION"),
        "physical_mismatch": ("physical_match_id", "physical:other"),
        "source_sha_mismatch": ("source_video_sha256", "f" * 64),
        "archive_mismatch": ("archive_sha256", "e" * 64),
    }
    for problem, (field_name, value) in drifts.items():
        record = registry.records["fm1_0"]
        original = getattr(record, field_name)
        setattr(record, field_name, value)
        assert catalog.sync_learning_registry(registry, rows, dry_run=True)[problem] == 1
        with pytest.raises(LeakageError):  # the real sync refuses on the same check
            catalog.sync_learning_registry(registry, rows)
        setattr(record, field_name, original)


def test_real_sync_writes_nothing_when_any_row_fails(tmp_path):
    catalog, _ = _catalog_with_archives(tmp_path)
    rows = catalog.learning_archives()
    registry = _Registry()
    Path(rows[-1]["archive"]).write_bytes(b"replaced after registration")
    assert catalog.sync_learning_registry(registry, rows, dry_run=True)[
        "archive_changed"] == 1
    with pytest.raises(LeakageError):
        catalog.sync_learning_registry(registry, rows)
    assert registry.records == {}  # the two good rows were not added either


def test_new_match_already_in_another_split_is_refused(tmp_path):
    catalog, _ = _catalog_with_archives(tmp_path)
    rows = catalog.learning_archives()
    registry = _Registry()
    registry.records["other"] = _Record("other", rows[0]["physical_match_id"], "DEV_COMPARISON"
                                        if rows[0]["split"] != "DEV_COMPARISON" else "TRAIN",
                                        "d" * 64, "c" * 64)
    assert catalog.sync_learning_registry(registry, rows, dry_run=True)[
        "physical_split_conflict"] == 1


def test_sync_into_the_real_continual_learning_registry(tmp_path):
    learning = pytest.importorskip("valorant_ai_coach.learning.registry")
    catalog, _ = _catalog_with_archives(tmp_path)
    rows = catalog.learning_archives()
    registry = learning.DatasetRegistry(tmp_path / "ws" / "dataset_registry.json")
    plan = catalog.sync_learning_registry(registry, rows, dry_run=True)
    assert plan["would_add"] == 3 and not any(plan[key] for key in PROBLEMS)
    result = catalog.sync_learning_registry(registry, rows)
    assert (result["added"], result["already_present"]) == (3, 0)
    assert {r.source_id: r.split for r in registry.records.values()} == {
        "fm1_0": "TRAIN", "fm1_1": "VALIDATION", "fm1_2": "DEV_COMPARISON"}
    # The real registry's own fields (physical match, video and archive hashes) agree.
    again = catalog.sync_learning_registry(registry, rows, dry_run=True)
    assert again["already_present"] == 3 and not any(again[key] for key in PROBLEMS)
    result = catalog.sync_learning_registry(registry, rows)
    assert (result["added"], result["already_present"]) == (0, 3)

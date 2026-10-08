from __future__ import annotations

import json
import os
import stat
import sqlite3
from pathlib import Path

import pytest

from valorant_ai_coach.storage import SQLiteRepository

ROOT = Path(__file__).resolve().parents[2]


def load_case(case_id: str) -> dict[str, object]:
    path = ROOT / "tests" / "cases" / case_id / "input.json"
    return json.loads(path.read_text(encoding="utf-8"))


def evaluation(evaluation_id: str = "E-1", label: str = "good") -> dict[str, object]:
    return {
        "evaluation_id": evaluation_id,
        "clip_id": None if label == "unscored" else f"clip-{evaluation_id}",
        "primary_rule_id": "AIM-02",
        "related_rule_ids": [],
        "label": label,
        "decision_source": "hybrid",
        "fact_refs": [],
        "concept_tags": ["preaim"],
        "title": "評価",
        "reason": "根拠",
        "improvement": "改善" if label == "improve" else None,
        "confidence": 0.9 if label != "unscored" else 0.4,
        "evidence": [],
        "evidence_range": None,
        "display_clip": None,
        "missing_information": ["情報不足"] if label == "unscored" else [],
        "unscored_reason_code": "missing_required_fact" if label == "unscored" else None,
    }


def test_round_package_and_analysis_are_saved_and_replaced_atomically(tmp_path: Path) -> None:
    repository = SQLiteRepository(tmp_path / "data" / "app.db")
    package = load_case("TC-006")
    repository.create_match(package["match_id"], "match.mp4", {"duration_sec": 120})
    repository.save_round_package(package)
    repository.save_analysis_result(
        {
            "match_id": package["match_id"],
            "round_no": package["round_no"],
            "evaluations": [evaluation("E-1", "good")],
        }
    )
    repository.save_analysis_result(
        {
            "match_id": package["match_id"],
            "round_no": package["round_no"],
            "evaluations": [evaluation("E-2", "improve")],
        }
    )
    result = repository.get_match_result(package["match_id"])
    assert result is not None
    assert [item["evaluation_id"] for item in result["evaluations"]] == ["E-2"]
    assert len(repository.list_round_packages(package["match_id"])) == 1


def test_failed_replacement_rolls_back_previous_evaluations(tmp_path: Path) -> None:
    repository = SQLiteRepository(tmp_path / "app.db")
    repository.create_match("M-1", "match.mp4")
    repository.save_analysis_result(
        {"match_id": "M-1", "round_no": 1, "evaluations": [evaluation("E-1")]}
    )
    invalid = evaluation("E-2")
    invalid["label"] = "neutral"
    with pytest.raises(ValueError, match="評価ラベル"):
        repository.save_analysis_result(
            {"match_id": "M-1", "round_no": 1, "evaluations": [invalid]}
        )
    assert [item["evaluation_id"] for item in repository.list_evaluations("M-1")] == ["E-1"]


def test_clip_path_must_exist_and_stay_inside_clips_dir(tmp_path: Path) -> None:
    clips_dir = tmp_path / "clips"
    clips_dir.mkdir()
    repository = SQLiteRepository(tmp_path / "app.db", clips_dir=clips_dir)
    repository.create_match("M-1", "match.mp4")
    repository.save_analysis_result(
        {"match_id": "M-1", "round_no": 1, "evaluations": [evaluation("E-1")]}
    )
    outside = tmp_path / "outside.mp4"
    outside.write_bytes(b"clip")
    with pytest.raises(ValueError, match="ディレクトリ外"):
        repository.save_clip("clip-E-1", "E-1", outside, 1, 2, 1)
    missing = clips_dir / "missing.mp4"
    with pytest.raises(ValueError, match="存在しない"):
        repository.save_clip("clip-E-1", "E-1", missing, 1, 2, 1)
    inside = clips_dir / "clip-E-1.mp4"
    inside.write_bytes(b"clip")
    saved = repository.save_clip("clip-E-1", "E-1", inside, 1, 2, 1)
    assert saved["file_path"] == str(inside.resolve())


def test_job_checkpoint_round_trip(tmp_path: Path) -> None:
    repository = SQLiteRepository(tmp_path / "app.db")
    repository.create_match("M-1", "match.mp4")
    repository.save_job_checkpoint("M-1", "analyzing", {"completed_rounds": [1, 2]})
    checkpoint = repository.get_job_checkpoint("M-1")
    assert checkpoint is not None
    assert checkpoint["checkpoint"] == {"completed_rounds": [1, 2]}


def test_evaluation_id_cannot_be_moved_between_matches(tmp_path: Path) -> None:
    repository = SQLiteRepository(tmp_path / "app.db")
    repository.create_match("M-1", "one.mp4")
    repository.create_match("M-2", "two.mp4")
    repository.save_analysis_result(
        {"match_id": "M-1", "round_no": 1, "evaluations": [evaluation("E-SHARED")]}
    )

    with pytest.raises(ValueError, match="別match"):
        repository.save_analysis_result(
            {"match_id": "M-2", "round_no": 1, "evaluations": [evaluation("E-SHARED")]}
        )

    assert [item["evaluation_id"] for item in repository.list_evaluations("M-1")] == [
        "E-SHARED"
    ]
    assert repository.list_evaluations("M-2") == []


def test_evaluation_id_cannot_be_moved_between_rounds(tmp_path: Path) -> None:
    repository = SQLiteRepository(tmp_path / "app.db")
    repository.create_match("M-1", "one.mp4")
    repository.save_analysis_result(
        {"match_id": "M-1", "round_no": 1, "evaluations": [evaluation("E-SHARED")]}
    )

    with pytest.raises(ValueError, match="別round"):
        repository.save_analysis_result(
            {"match_id": "M-1", "round_no": 2, "evaluations": [evaluation("E-SHARED")]}
        )

    stored = repository.list_evaluations("M-1")
    assert [(item["evaluation_id"], item["round_no"]) for item in stored] == [
        ("E-SHARED", 1)
    ]


def test_clip_id_cannot_be_reassigned_to_another_evaluation(tmp_path: Path) -> None:
    clips_dir = tmp_path / "clips"
    clips_dir.mkdir()
    repository = SQLiteRepository(tmp_path / "app.db", clips_dir=clips_dir)
    repository.create_match("M-1", "match.mp4")
    first = evaluation("E-1")
    second = evaluation("E-2")
    second["clip_id"] = first["clip_id"]
    repository.save_analysis_result(
        {"match_id": "M-1", "round_no": 1, "evaluations": [first, second]}
    )
    clip = clips_dir / "shared-id.mp4"
    clip.write_bytes(b"clip")
    repository.save_clip("clip-E-1", "E-1", clip, 1, 2, 1)

    with pytest.raises(ValueError, match="別evaluation"):
        repository.save_clip("clip-E-1", "E-2", clip, 1, 2, 1)

    stored = repository.get_clip("clip-E-1")
    assert stored is not None
    assert stored["evaluation_id"] == "E-1"


def test_reset_does_not_delete_clip_file_still_referenced_by_another_match(
    tmp_path: Path,
) -> None:
    clips_dir = tmp_path / "clips"
    clips_dir.mkdir()
    repository = SQLiteRepository(tmp_path / "app.db", clips_dir=clips_dir)
    shared = clips_dir / "shared.mp4"
    shared.write_bytes(b"shared")
    for match_id, evaluation_id, clip_id in (
        ("M-1", "E-1", "clip-E-1"),
        ("M-2", "E-2", "clip-E-2"),
    ):
        repository.create_match(match_id, f"{match_id}.mp4")
        value = evaluation(evaluation_id)
        value["clip_id"] = clip_id
        repository.save_analysis_result(
            {"match_id": match_id, "round_no": 1, "evaluations": [value]}
        )
        repository.save_clip(clip_id, evaluation_id, shared, 1, 2, 1)

    repository.reset_match_analysis("M-1")

    assert shared.is_file()
    assert repository.list_clips("M-1") == []
    assert len(repository.list_clips("M-2")) == 1


def test_replacing_round_results_removes_unreferenced_clip_file(tmp_path: Path) -> None:
    clips_dir = tmp_path / "clips"
    clips_dir.mkdir()
    repository = SQLiteRepository(tmp_path / "app.db", clips_dir=clips_dir)
    repository.create_match("M-1", "match.mp4")
    repository.save_analysis_result(
        {"match_id": "M-1", "round_no": 1, "evaluations": [evaluation("E-OLD")]}
    )
    clip = clips_dir / "clip-E-OLD.mp4"
    clip.write_bytes(b"clip")
    repository.save_clip("clip-E-OLD", "E-OLD", clip, 1, 2, 1)

    repository.save_analysis_result(
        {"match_id": "M-1", "round_no": 1, "evaluations": [evaluation("E-NEW")]}
    )

    assert clip.exists() is False
    assert repository.list_clips("M-1") == []


def test_reset_commits_even_when_orphan_clip_cleanup_is_locked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    clips_dir = tmp_path / "clips"
    clips_dir.mkdir()
    repository = SQLiteRepository(tmp_path / "app.db", clips_dir=clips_dir)
    repository.create_match("M-1", "match.mp4")
    repository.save_analysis_result(
        {"match_id": "M-1", "round_no": 1, "evaluations": [evaluation("E-1")]}
    )
    clip = clips_dir / "clip-E-1.mp4"
    clip.write_bytes(b"clip")
    repository.save_clip("clip-E-1", "E-1", clip, 1, 2, 1)
    original_unlink = Path.unlink

    def locked_unlink(path: Path, *args: object, **kwargs: object) -> None:
        if path == clip:
            raise PermissionError("Windows file lock")
        original_unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", locked_unlink)
    repository.reset_match_analysis("M-1")

    assert repository.list_evaluations("M-1") == []
    assert clip.read_bytes() == b"clip"


def test_migration_recovers_a_database_left_with_partial_v1_ddl(tmp_path: Path) -> None:
    database = tmp_path / "partial.db"
    # Simulate an old interrupted executescript() run: one valid table exists,
    # but schema_migrations was never marked as version 1.
    connection = sqlite3.connect(database)
    connection.execute(
        """CREATE TABLE matches (
            match_id TEXT PRIMARY KEY,
            source_video_path TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL,
            metadata_json TEXT NOT NULL DEFAULT '{}'
        )"""
    )
    connection.commit()
    connection.close()

    repository = SQLiteRepository(database)

    with sqlite3.connect(database) as check:
        tables = {
            row[0]
            for row in check.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        version = check.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0]
    assert {"matches", "round_packages", "evaluations", "clips", "analysis_jobs"} <= tables
    assert version == 1
    repository.create_match("M-RECOVERED", "match.mp4")


def test_clip_owner_can_be_checked_before_file_generation(tmp_path: Path) -> None:
    clips_dir = tmp_path / "clips"
    clips_dir.mkdir()
    repository = SQLiteRepository(tmp_path / "app.db", clips_dir=clips_dir)
    repository.create_match("M-1", "match.mp4")
    repository.save_analysis_result(
        {"match_id": "M-1", "round_no": 1, "evaluations": [evaluation("E-1")]}
    )
    clip = clips_dir / "clip-E-1.mp4"
    clip.write_bytes(b"clip")
    repository.save_clip("clip-E-1", "E-1", clip, 1, 2, 1)

    with pytest.raises(ValueError, match="別evaluation"):
        repository.assert_clip_id_available("clip-E-1", "E-OTHER")
    assert repository.get_clip("clip-E-1")["evaluation_id"] == "E-1"  # type: ignore[index]


def test_delete_match_cascades_rows_but_keeps_clips_shared_by_other_matches(
    tmp_path: Path,
) -> None:
    clips_dir = tmp_path / "clips"
    clips_dir.mkdir()
    repository = SQLiteRepository(tmp_path / "app.db", clips_dir=clips_dir)
    shared = clips_dir / "shared.mp4"
    shared.write_bytes(b"shared")
    for match_id, evaluation_id, clip_id in (
        ("M-1", "E-1", "clip-1"),
        ("M-2", "E-2", "clip-2"),
    ):
        repository.create_match(match_id, f"{match_id}.mp4")
        item = evaluation(evaluation_id)
        item["clip_id"] = clip_id
        repository.save_analysis_result(
            {"match_id": match_id, "round_no": 1, "evaluations": [item]}
        )
        repository.save_clip(clip_id, evaluation_id, shared, 1, 2, 1)

    repository.delete_match("M-1")

    assert repository.get_match("M-1") is None
    assert repository.list_evaluations("M-1") == []
    assert shared.read_bytes() == b"shared"
    assert len(repository.list_clips("M-2")) == 1


@pytest.mark.skipif(os.name == "nt", reason="POSIX permission bits are not authoritative on Windows")
def test_sqlite_file_is_private_on_posix(tmp_path: Path) -> None:
    path = tmp_path / "app.db"
    SQLiteRepository(path)
    assert stat.S_IMODE(path.stat().st_mode) == 0o600

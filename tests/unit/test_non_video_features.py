"""Synthetic non-video application features: no recordings, screenshots or API calls."""

from __future__ import annotations

import csv
import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest

from valorant_ai_coach.non_video.features import NonVideoFeatures, _atomic_write
from valorant_ai_coach.non_video.profiles import ProfileStore
from valorant_ai_coach.settings import AppSettings, SettingsStore
from valorant_ai_coach.storage.repository import SQLiteRepository


def fixture(tmp_path: Path) -> tuple[SQLiteRepository, NonVideoFeatures]:
    repo = SQLiteRepository(tmp_path / "store.db", clips_dir=tmp_path / "clips")
    repo.create_match("match1", tmp_path / "source.mp4", status="completed")
    repo.create_match("match2", tmp_path / "other.mp4", status="partial")
    repo.create_match("empty", tmp_path / "empty.mp4", status="completed")
    repo.save_analysis_result({
        "match_id": "match1", "round_no": 1, "evaluations": [
            {"evaluation_id": "e-good", "primary_rule_id": "AIM-02",
             "label": "good", "confidence": 0.95,
             "title": "<script>alert(1)</script>", "reason": "=HYPERLINK(\"x\")",
             "fact_refs": ["F1"], "evidence_range": {"start_sec": 29, "end_sec": 31},
             "improvement": None},
            {"evaluation_id": "e-unknown", "primary_rule_id": "MOV-01",
             "label": "unscored", "confidence": 0.3,
             "reason": "映像不足", "unscored_reason_code": "missing_required_fact",
             "missing_information": ["カメラ視点が不明"]},
        ]
    })
    repo.save_analysis_result({
        "match_id": "match2", "round_no": 3, "evaluations": [
            {"evaluation_id": "e-improve", "primary_rule_id": "AIM-02",
             "label": "improve", "confidence": 0.85,
             "reason": "静止が必要", "improvement": "停止して撃つ"},
        ]
    })
    return repo, NonVideoFeatures(repo)


def test_report_formats_are_safe_and_keep_original_evaluations(
    tmp_path: Path,
) -> None:
    repo, app = fixture(tmp_path)
    before = repo.list_evaluations("match1")
    for kind in ("html", "csv", "json"):
        destination = tmp_path / f"report.{kind}"
        app.export_report("match1", destination, kind)
        output = destination.read_text(encoding="utf-8")
        assert "sk-secret" not in output
        assert str(tmp_path) not in output
        if kind == "html":
            assert "<script>" not in output
            assert "&lt;script&gt;" in output
        if kind == "csv":
            values = list(csv.reader(output.splitlines()))
            reason_index = values[0].index("reason")
            assert values[1][reason_index].startswith("'=HYPERLINK")
        if kind == "json":
            data = json.loads(output)
            assert data["export_format_version"] == 1
            assert data["counts"] == {"good": 1, "improve": 0, "unscored": 1}
            assert data["evaluations"][1]["label"] == "unscored"
            assert data["evaluations"][1]["improvement"] is None
    assert before == repo.list_evaluations("match1")


def test_empty_match_and_incomplete_match_statistics(tmp_path: Path) -> None:
    _, app = fixture(tmp_path)
    stats = app.statistics()
    assert stats["match_count"] == 3
    assert stats["evaluable_match_count"] == 1
    assert stats["incomplete_match_count"] == 1
    assert stats["matches_without_evaluations"] == 1
    assert stats["counts"] == {"good": 1, "improve": 1, "unscored": 1}
    assert stats["good_share_of_scored"] == 0.5
    assert stats["by_rule"] == {"AIM-02": 2, "MOV-01": 1}


def test_search_combined_filters_and_stable_paging(tmp_path: Path) -> None:
    _, app = fixture(tmp_path)
    result = app.search(rule="AIM-02", label="good", keyword="HYPERLINK")
    assert [r["evaluation_id"] for r in result] == ["e-good"]
    assert app.search(rule="AIM-02", label="unscored") == []
    assert app.search(keyword="' OR 1=1 --") == []
    first_page = app.search(limit=1)
    second_page = app.search(limit=1, offset=1)
    assert first_page[0]["evaluation_id"] != second_page[0]["evaluation_id"]
    assert first_page == app.search(limit=1)
    assert app.search(category_rules=("MOV-01",))[0]["evaluation_id"] == "e-unknown"
    with pytest.raises(ValueError):
        app.search(limit=10000)


def test_comparison_never_invents_skill_score(tmp_path: Path) -> None:
    _, app = fixture(tmp_path)
    result = app.compare("match1", "match2")
    assert result["match1"]["counts"]["unscored"] == 1
    assert result["match2"]["status"] == "partial"
    assert "skill_score" not in str(result)
    with pytest.raises(ValueError):
        app.compare("match1", "match1")


def test_feedback_is_independent_persistent_and_cascades(tmp_path: Path) -> None:
    repo, app = fixture(tmp_path)
    original = repo.list_evaluations("match1")
    app.save_feedback("e-good", "inappropriate", "理由が弱い")
    app.save_feedback("e-good", "pending", "")
    reopened = NonVideoFeatures(SQLiteRepository(tmp_path / "store.db"))
    assert reopened.feedback("e-good")["verdict"] == "pending"
    assert reopened.feedback("e-good")["memo"] == ""
    assert original == repo.list_evaluations("match1")
    with pytest.raises(KeyError):
        app.save_feedback("not-an-evaluation", "valid", "")
    repo.delete_match("match1")
    assert app.feedback("e-good") is None


def test_usage_unknown_cost_and_restart_persistence(tmp_path: Path) -> None:
    _, app = fixture(tmp_path)
    app.record_usage("ai_coach", "mock-model", "response_received", 100, 50)
    app.record_usage("ai_coach", "mock-model", "transport_error")
    app.record_usage("ai_coach", "mock-model", "cache_hit", cache_hit=True)
    before = app.usage()
    assert all(entry["estimated_cost"] is None for entry in before)
    assert before[0]["cache_hit"] == 1
    assert before[0]["total_tokens"] is None
    rates = {"mock-model": {
        "input_per_million": 1.0, "output_per_million": 2.0, "currency": "USD"
    }}
    after = app.usage(rates)
    priced = next(entry for entry in after if entry["input_tokens"] == 100)
    assert priced["estimated_cost"] == pytest.approx(0.0002)
    assert priced["total_tokens"] == 150
    assert all(x["estimated_cost"] is None for x in after if x["input_tokens"] is None)
    assert len(NonVideoFeatures(SQLiteRepository(tmp_path / "store.db")).usage()) == 3
    with pytest.raises(ValueError):
        app.record_usage("ai_coach", "model", "ok", -1)


def test_atomic_file_write_failure_preserves_original(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    destination = tmp_path / "existing.json"
    destination.write_text('{"original":true}', encoding="utf-8")
    def fail(_src: Any, _dst: Any) -> None:
        raise PermissionError("denied")
    monkeypatch.setattr("valorant_ai_coach.non_video.features.os.replace", fail)
    with pytest.raises(PermissionError):
        _atomic_write(destination, '{"destroyed":true}')
    assert destination.read_text(encoding="utf-8") == '{"original":true}'
    assert sorted(p.name for p in tmp_path.iterdir()) == ["existing.json"]


def test_profile_roundtrip_key_omission_and_safe_import(
    tmp_path: Path,
) -> None:
    class Credentials:
        value: str | None = None
        def get_password(self, _a: str, _b: str) -> str | None:
            return self.value
        def set_password(self, _a: str, _b: str, password: str) -> None:
            self.value = password

    credentials = Credentials()
    store = SettingsStore(tmp_path / "settings.json", credential_backend=credentials)
    store.save(AppSettings.defaults(tmp_path))
    store.set_api_key("sk-test-secret-987654321")
    profiles = ProfileStore(store)
    profiles.create("標準")
    export = tmp_path / "profile.json"
    profiles.export_file("標準", export)
    contents = export.read_text(encoding="utf-8")
    assert "sk-test-secret" not in contents
    assert "api_key" not in contents
    assert "data_dir" not in contents
    profiles.rename("標準", "別設定")
    profiles.import_file(export, "取込")
    assert profiles.list_names() == ["別設定", "取込"]
    malformed = tmp_path / "malformed.json"
    malformed.write_text('{"version":1,"settings":{"data_dir":"/oops"}}', encoding="utf-8")
    with pytest.raises(ValueError):
        profiles.import_file(malformed, "危険")
    assert store.load().data_dir == tmp_path
    profiles.delete("別設定")


def test_migration_preserves_existing_data_when_reopened(tmp_path: Path) -> None:
    repo, features = fixture(tmp_path)
    features.save_feedback("e-good", "valid", "OK")
    for _ in range(3):
        NonVideoFeatures(SQLiteRepository(repo.path))
    assert repo.list_evaluations("match1")[0]["evaluation_id"] == "e-good"
    with sqlite3.connect(repo.path) as con:
        assert con.execute("SELECT COUNT(*) FROM non_video_migrations").fetchone()[0] == 1
        assert con.execute("PRAGMA foreign_key_check").fetchall() == []

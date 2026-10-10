"""Non-video GUI surface and observed API metadata instrumentation."""

from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from valorant_ai_coach.ai.coach import OpenAICoach
from valorant_ai_coach.non_video.features import NonVideoFeatures
from valorant_ai_coach.schema_validation import SchemaValidator
from valorant_ai_coach.storage.repository import SQLiteRepository

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtCore import QCoreApplication, QEvent  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from valorant_ai_coach.ui.non_video_dialog import NonVideoDialog  # noqa: E402


def test_usage_recorder_keeps_observed_values_and_missing_as_null(tmp_path: Path) -> None:
    repo = SQLiteRepository(tmp_path / "usage.db")
    store = NonVideoFeatures(repo)
    coach = OpenAICoach(
        api_key="dummy-local-only", model="unit-model",
        rules_by_id={}, validator=SchemaValidator(),
        client=SimpleNamespace(responses=SimpleNamespace(create=lambda **_: None)),
        usage_recorder=store,
    )
    coach._record_usage(
        "response_received",
        response=SimpleNamespace(usage=SimpleNamespace(input_tokens=123, output_tokens=45)),
        repair_attempt=1,
    )
    coach._record_usage("transport_error", retry_attempt=2)
    coach._record_usage("cache_hit", cache_hit=True)
    events = store.usage()
    assert len(events) == 3
    assert events[0]["cache_hit"] == 1
    assert events[0]["input_tokens"] is None
    assert events[1]["status"] == "transport_error"
    assert events[1]["output_tokens"] is None
    assert events[2]["input_tokens"] == 123
    assert events[2]["repair_attempt"] == 1


class FakeSettingsStore:
    def __init__(self, path: Path):
        self.path = path


class FakeBackend:
    def __init__(self, repository: SQLiteRepository, tmp_path: Path):
        self.non_video = NonVideoFeatures(repository)
        self.services = SimpleNamespace(
            rules_by_id={
                "AIM-02": {"category": "Aim"},
                "MOV-02": {"category": "Movement"},
            }
        )
        self.settings_store = FakeSettingsStore(tmp_path / "settings.json")
        self.profiles = SimpleNamespace(list_names=lambda: [])

    def list_matches(self) -> list[dict[str, Any]]:
        return self.non_video.repository.list_matches()

    def search_evaluations(self, **kwargs: Any) -> list[dict[str, Any]]:
        return self.non_video.search(**kwargs)

    def get_statistics(self, **kwargs: Any) -> dict[str, Any]:
        return self.non_video.statistics(**kwargs)

    def compare_matches(self, first: str, second: str) -> dict[str, Any]:
        return self.non_video.compare(first, second)

    def get_api_usage(self, prices: dict[str, Any]) -> list[dict[str, Any]]:
        return self.non_video.usage(prices)


def test_nonvideo_dialog_navigation_uses_only_persisted_results(tmp_path: Path) -> None:
    application = QApplication.instance() or QApplication([])
    repo = SQLiteRepository(tmp_path / "app.db")
    repo.create_match("M1", tmp_path / "source1.mp4", status="completed")
    repo.create_match("M2", tmp_path / "source2.mp4", status="partial")
    repo.save_analysis_result({
        "match_id": "M1", "round_no": 1, "evaluations": [
            {"evaluation_id": "E1", "primary_rule_id": "AIM-02", "label": "good",
             "confidence": 0.9, "reason": "改善の根拠"},
        ]
    })
    dialog = NonVideoDialog(FakeBackend(repo, tmp_path))
    assert dialog.tabs.count() == 5
    assert dialog.query_table.rowCount() == 1
    assert dialog.stat_table.rowCount() == 1
    assert dialog.stat_bars.count() == 3
    assert dialog.stat_category_bars.count() == 1
    assert dialog.stat_day_bars.count() == 1
    assert dialog.stat_improve_bars.count() == 0 + 1
    dialog.query_label.setCurrentIndex(dialog.query_label.findData("unscored"))
    dialog._search()
    assert dialog.query_table.rowCount() == 0
    dialog.query_label.setCurrentIndex(0)
    dialog._search()
    assert dialog.query_table.rowCount() == 1
    dialog._compare()
    assert "M1" in dialog.compare_text.toPlainText()
    dialog.close()
    dialog.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    application.processEvents()
    del dialog

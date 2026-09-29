from __future__ import annotations

import json
from pathlib import Path

from valorant_ai_coach.application import FramePlanner
from valorant_ai_coach.models import RuleCandidate

ROOT = Path(__file__).resolve().parents[2]


def package(case_id: str) -> dict[str, object]:
    path = ROOT / "tests" / "cases" / case_id / "input.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_sparse_and_dense_context_are_separate_and_bounded() -> None:
    candidate = RuleCandidate(
        rule_id="AIM-02",
        priority="mvp_required",
        temporal_level="micro",
        label_mode="deterministic_if_confident_else_llm",
        matched_event_types=("peek", "preaim_started"),
    )
    frames = FramePlanner(max_sparse=4, max_dense=5).plan(package("TC-006"), [candidate])
    assert len([frame for frame in frames if frame.purpose == "dense_candidate_context"]) <= 5
    assert len([frame for frame in frames if frame.purpose == "sparse_round_context"]) <= 4
    assert all(0 <= frame.time_sec <= 100 for frame in frames)
    assert any(abs(frame.time_sec - 30.7) <= 0.01 for frame in frames)
    assert {round(frame.time_sec) for frame in frames}.issuperset({0, 100})


def test_frame_plan_never_uses_the_whole_source_video_window() -> None:
    value = package("TC-006")
    value["round_window"] = {"start_sec": 20, "end_sec": 40}
    frames = FramePlanner(max_sparse=3, max_dense=0).plan(value, [])
    assert [frame.time_sec for frame in frames] == [20.0, 30.0, 40.0]
    assert value["source_video"]["duration_sec"] == 120


def test_default_plan_fits_single_api_image_budget() -> None:
    candidate = RuleCandidate(
        rule_id="AIM-02",
        priority="mvp_required",
        temporal_level="micro",
        label_mode="deterministic_if_confident_else_llm",
        matched_event_types=("peek", "preaim_started"),
    )

    frames = FramePlanner().plan(package("TC-006"), [candidate])

    assert len(frames) <= 32

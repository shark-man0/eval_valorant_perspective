from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from threading import Event

import pytest

from valorant_ai_coach.application import (
    AnalysisCancelled,
    FramePlanner,
    MatchAnalysisPipeline,
    MockCoachAdapter,
    RoundAnalysis,
    RoundAnalyzer,
)
from valorant_ai_coach.clips import ClipArtifact
from valorant_ai_coach.facts import FactBuilder
from valorant_ai_coach.hud import MockHudAnalyzer
from valorant_ai_coach.resources import resource_path
from valorant_ai_coach.rules import (
    DeterministicRuleEngine,
    EvaluationAggregator,
    RuleSelector,
)
from valorant_ai_coach.schema_validation import SchemaValidator
from valorant_ai_coach.storage import SQLiteRepository
from valorant_ai_coach.video import FrameSample, VideoMetadata

ROOT = Path(__file__).resolve().parents[2]


def load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


class FakeVideoService:
    def __init__(self, video_path: Path) -> None:
        self.metadata = VideoMetadata(
            path=video_path,
            duration_sec=120.0,
            width=1920,
            height=1080,
            fps=60.0,
            video_codec="h264",
            audio_codec="aac",
            has_audio=True,
            file_size=video_path.stat().st_size,
        )
        self.requested_timestamps: list[float] = []

    def probe(self, path: Path, **_kwargs: object) -> VideoMetadata:
        assert path.resolve() == self.metadata.path.resolve()
        return self.metadata

    def extract_frames(
        self,
        path: Path,
        timestamps_sec: list[float],
        output_dir: Path,
        **_kwargs: object,
    ) -> list[FrameSample]:
        assert path == self.metadata.path
        output_dir.mkdir(parents=True, exist_ok=True)
        self.requested_timestamps.extend(timestamps_sec)
        samples = []
        for index, timestamp in enumerate(timestamps_sec):
            frame = output_dir / f"frame-{index:03d}.jpg"
            frame.write_bytes(b"jpeg")
            samples.append(FrameSample(timestamp, frame))
        return samples


class FakeClipService:
    def __init__(self, output_dir: Path) -> None:
        self.output_dir = output_dir
        self.calls = 0

    def create_clip(
        self,
        video_path: Path,
        start_sec: float,
        end_sec: float,
        source_duration_sec: float | None = None,
        clip_id: str | None = None,
        **_kwargs: object,
    ) -> ClipArtifact:
        assert source_duration_sec == 120
        assert clip_id is not None
        self.calls += 1
        self.output_dir.mkdir(parents=True, exist_ok=True)
        path = self.output_dir / f"{clip_id}.mp4"
        path.write_bytes(b"clip")
        return ClipArtifact(
            clip_id,
            path,
            start_sec,
            end_sec,
            end_sec - start_sec,
            video_path,
        )


def build_pipeline(
    tmp_path: Path,
    video_path: Path,
    fixtures: list[dict[str, object]] | None = None,
) -> tuple[MatchAnalysisPipeline, SQLiteRepository, FakeVideoService, FakeClipService]:
    registry = load_json(resource_path("config/rule_trigger_registry_v2.json"))
    rules = load_json(resource_path("config/valorant_evaluation_rules_v4.json"))
    clips_dir = tmp_path / "clips"
    repository = SQLiteRepository(tmp_path / "app.db", clips_dir=clips_dir)
    video = FakeVideoService(video_path)
    clips = FakeClipService(clips_dir)
    fixture = load_json(ROOT / "tests" / "cases" / "TC-029" / "input.json")
    validator = SchemaValidator()
    analyzer = RoundAnalyzer(
        fact_builder=FactBuilder(),
        selector=RuleSelector(registry),
        rule_engine=DeterministicRuleEngine(),
        coach=MockCoachAdapter(),
        validator=validator,
    )
    pipeline = MatchAnalysisPipeline(
        data_dir=tmp_path,
        repository=repository,
        video=video,
        clips=clips,
        hud=MockHudAnalyzer(fixtures or [fixture]),
        round_analyzer=analyzer,
        frame_planner=FramePlanner(max_sparse=5, max_dense=7),
        aggregator=EvaluationAggregator(rules, registry),
        validator=validator,
    )
    return pipeline, repository, video, clips


def test_mock_round_package_runs_through_frames_rules_db_and_clips(tmp_path: Path) -> None:
    video_path = tmp_path / "match.mp4"
    video_path.write_bytes(b"video")
    pipeline, repository, video, clips = build_pipeline(tmp_path, video_path)
    progress: list[tuple[float, str]] = []

    result = pipeline.analyze_video(
        video_path,
        lambda value, message: progress.append((value, message)),
        match_id="M-E2E",
    )

    assert result.status == "completed"
    stored = repository.get_match_result("M-E2E")
    assert stored is not None
    assert [(item["primary_rule_id"], item["label"]) for item in stored["evaluations"]] == [
        ("AIM-02", "good"),
        ("DEC-01", "improve"),
    ]
    assert len(repository.list_clips("M-E2E")) == 2
    # Both evaluations use the same evidence window, so one physical clip is reused.
    assert clips.calls == 1
    assert len(set(row["file_path"] for row in repository.list_clips("M-E2E"))) == 1
    packages = repository.list_round_packages("M-E2E")
    assert packages[0]["frames"]
    assert {frame["purpose"] for frame in packages[0]["frames"]} == {
        "dense_candidate_context",
        "sparse_round_context",
    }
    evidence_root = (tmp_path / "matches" / "M-E2E" / "evidence").resolve()
    assert all(
        Path(frame["path"]).is_file()
        and Path(frame["path"]).resolve().is_relative_to(evidence_root)
        for frame in packages[0]["frames"]
    )
    assert len(video.requested_timestamps) <= 12
    assert max(video.requested_timestamps) <= packages[0]["round_window"]["end_sec"]
    assert result.analysis_json.is_file()
    assert progress[-1][0] == 1.0
    assert not (tmp_path / "temp" / "M-E2E").exists()


def test_cancel_marks_job_and_match_cancelled(tmp_path: Path) -> None:
    video_path = tmp_path / "match.mp4"
    video_path.write_bytes(b"video")
    pipeline, repository, _video, _clips = build_pipeline(tmp_path, video_path)
    cancel = Event()
    cancel.set()
    with pytest.raises(AnalysisCancelled):
        pipeline.analyze_video(video_path, cancel_event=cancel, match_id="M-CANCEL")
    assert repository.get_match("M-CANCEL")["status"] == "cancelled"  # type: ignore[index]
    assert repository.get_job_checkpoint("M-CANCEL")["status"] == "cancelled"  # type: ignore[index]


def test_cancel_can_interrupt_initial_video_probe(tmp_path: Path) -> None:
    video_path = tmp_path / "match.mp4"
    video_path.write_bytes(b"video")
    pipeline, repository, _video, _clips = build_pipeline(tmp_path, video_path)
    cancel = Event()
    cancel.set()

    class CancelAwareVideo(FakeVideoService):
        def probe(self, path: Path, **kwargs: object) -> VideoMetadata:
            assert kwargs["cancel_event"] is cancel
            raise InterruptedError("probe cancelled")

    pipeline.video = CancelAwareVideo(video_path)
    with pytest.raises(AnalysisCancelled, match="メタデータ取得"):
        pipeline.analyze_video(video_path, cancel_event=cancel, match_id="M-PROBE-CANCEL")

    assert repository.get_match("M-PROBE-CANCEL") is None


def test_low_confidence_scored_output_is_converted_to_unscored() -> None:
    value = {
        "label": "improve",
        "confidence": 0.4,
        "clip_id": "clip-1",
        "display_clip": {"start_sec": 1, "end_sec": 2},
        "improvement": "改善",
        "missing_information": [],
        "unscored_reason_code": None,
    }
    normalized = MatchAnalysisPipeline._enforce_confidence_policy(value)
    assert normalized["label"] == "unscored"
    assert normalized["clip_id"] is None
    assert normalized["unscored_reason_code"] == "low_confidence"


def test_failed_evidence_staging_keeps_existing_evidence_and_db_reference(
    tmp_path: Path,
) -> None:
    video_path = tmp_path / "match.mp4"
    video_path.write_bytes(b"video")
    pipeline, repository, _video, _clips = build_pipeline(tmp_path, video_path)
    match_id = "M-EVIDENCE"
    round_no = 1
    old_frame = tmp_path / "matches" / match_id / "evidence" / "round-001" / "old.jpg"
    old_frame.parent.mkdir(parents=True)
    old_frame.write_bytes(b"old evidence")
    repository.create_match(match_id, video_path)
    repository.save_round_package(
        {
            "match_id": match_id,
            "round_no": round_no,
            "source_video": {"path": str(video_path)},
            "frames": [{"path": str(old_frame), "time_sec": 1.0}],
        }
    )
    failed = RoundAnalysis(
        {
            "match_id": match_id,
            "round_no": round_no,
            "frames": [{"path": str(tmp_path / "missing.jpg"), "time_sec": 2.0}],
        },
        (),
        {},
        {"evaluations": []},
    )

    with pytest.raises(FileNotFoundError):
        pipeline._persist_round_evidence(failed, match_id, round_no)

    assert old_frame.read_bytes() == b"old evidence"
    stored = repository.get_round_package(match_id, round_no)
    assert stored is not None
    assert stored["frames"][0]["path"] == str(old_frame)


def test_failed_evidence_swap_restores_existing_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    video_path = tmp_path / "match.mp4"
    video_path.write_bytes(b"video")
    pipeline, repository, _video, _clips = build_pipeline(tmp_path, video_path)
    match_id = "M-EVID-SWAP"
    source = tmp_path / "new.jpg"
    source.write_bytes(b"new evidence")
    round_root = tmp_path / "matches" / match_id / "evidence" / "round-001"
    old_frame = round_root / "old.jpg"
    round_root.mkdir(parents=True)
    old_frame.write_bytes(b"old evidence")
    repository.create_match(match_id, video_path)
    old_package = {"match_id": match_id, "round_no": 1, "frames": [{"path": str(old_frame)}]}
    repository.save_round_package(old_package)
    package = deepcopy(load_json(ROOT / "tests" / "cases" / "TC-029" / "input.json"))
    package["match_id"] = match_id
    package["round_no"] = 1
    package["frames"] = [
        {"path": str(source), "time_sec": 1.0, "purpose": "sparse_round_context"}
    ]
    replacement = RoundAnalysis(package, (), {}, {"evaluations": []})
    original_replace = Path.replace

    def fail_staging_publish(path: Path, target: Path) -> Path:
        if target == round_root and ".staging" in path.name:
            raise OSError("simulated Windows rename failure")
        return original_replace(path, target)

    monkeypatch.setattr(Path, "replace", fail_staging_publish)
    with pytest.raises(OSError, match="rename failure"):
        pipeline._persist_round_evidence(replacement, match_id, 1)

    assert old_frame.read_bytes() == b"old evidence"
    stored = repository.get_round_package(match_id, 1)
    assert stored == old_package


def test_pipeline_rejects_clip_owner_collision_before_clip_writer_runs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    video_path = tmp_path / "match.mp4"
    video_path.write_bytes(b"video")
    pipeline, repository, _video, clips = build_pipeline(tmp_path, video_path)

    def reject_owner(_clip_id: str, _evaluation_id: str) -> None:
        raise ValueError("owned by another evaluation")

    monkeypatch.setattr(repository, "assert_clip_id_available", reject_owner)
    result = pipeline.analyze_video(video_path, match_id="M-CLIP-OWNER")

    assert clips.calls == 0
    assert any("owned by another evaluation" in error for error in result.errors)


def test_delete_match_cascades_rows_and_removes_private_artifacts(tmp_path: Path) -> None:
    video_path = tmp_path / "match.mp4"
    video_path.write_bytes(b"video")
    pipeline, repository, _video, _clips = build_pipeline(tmp_path, video_path)
    pipeline.analyze_video(video_path, match_id="M-DELETE")
    clip_paths = [Path(row["file_path"]) for row in repository.list_clips("M-DELETE")]
    match_root = tmp_path / "matches" / "M-DELETE"

    pipeline.delete_match("M-DELETE")

    assert repository.get_match("M-DELETE") is None
    assert repository.list_clips("M-DELETE") == []
    assert match_root.exists() is False
    assert all(path.exists() is False for path in clip_paths)


def test_cancelled_job_resumes_without_reprocessing_completed_round(tmp_path: Path) -> None:
    video_path = tmp_path / "match.mp4"
    video_path.write_bytes(b"video")
    base = load_json(ROOT / "tests" / "cases" / "TC-029" / "input.json")
    first = deepcopy(base)
    second = deepcopy(base)
    first["round_no"] = 1
    second["round_no"] = 2
    pipeline, repository, video, _clips = build_pipeline(
        tmp_path, video_path, [first, second]
    )
    cancel = Event()

    def stop_after_first(_value: float, message: str) -> None:
        if message == "ラウンド 1 を評価しました":
            cancel.set()

    with pytest.raises(AnalysisCancelled):
        pipeline.analyze_video(
            video_path,
            progress_cb=stop_after_first,
            cancel_event=cancel,
            match_id="M-RESUME",
        )
    first_run_frame_count = len(video.requested_timestamps)
    checkpoint = repository.get_job_checkpoint("M-RESUME")
    assert checkpoint is not None
    assert checkpoint["checkpoint"]["completed_rounds"] == [1]

    result = pipeline.resume_analysis("M-RESUME")

    assert result.status == "completed"
    assert len(video.requested_timestamps) == first_run_frame_count * 2
    assert [package["round_no"] for package in repository.list_round_packages("M-RESUME")] == [
        1,
        2,
    ]


def test_resume_rejects_changed_source_video(tmp_path: Path) -> None:
    video_path = tmp_path / "match.mp4"
    video_path.write_bytes(b"video")
    pipeline, _repository, _video, _clips = build_pipeline(tmp_path, video_path)
    cancel = Event()
    cancel.set()
    with pytest.raises(AnalysisCancelled):
        pipeline.analyze_video(video_path, cancel_event=cancel, match_id="M-CHANGED")

    video_path.write_bytes(b"changed video content")
    with pytest.raises(RuntimeError, match="元動画が前回実行時から変更"):
        pipeline.resume_analysis("M-CHANGED")


def test_one_round_failure_isolated_and_later_round_continues(tmp_path: Path) -> None:
    video_path = tmp_path / "match.mp4"
    video_path.write_bytes(b"video")
    base = load_json(ROOT / "tests" / "cases" / "TC-029" / "input.json")
    first = deepcopy(base)
    second = deepcopy(base)
    first["round_no"] = 1
    second["round_no"] = 2
    pipeline, repository, _video, _clips = build_pipeline(
        tmp_path, video_path, [first, second]
    )
    delegate = pipeline.round_analyzer

    class FailsFirstRound:
        fact_builder = delegate.fact_builder
        selector = delegate.selector
        rule_engine = delegate.rule_engine
        coach = delegate.coach

        @staticmethod
        def analyze(package: dict[str, object], **_kwargs: object) -> object:
            if package["round_no"] == 1:
                raise RuntimeError("broken round")
            return delegate.analyze(package)  # type: ignore[arg-type]

    pipeline.round_analyzer = FailsFirstRound()  # type: ignore[assignment]
    result = pipeline.analyze_video(video_path, match_id="M-PARTIAL")

    assert result.status == "partial"
    assert any("round 1: broken round" in error for error in result.errors)
    assert [item.output["round_no"] for item in result.rounds] == [2]
    checkpoint = repository.get_job_checkpoint("M-PARTIAL")
    assert checkpoint is not None
    assert checkpoint["checkpoint"]["failed_rounds"] == [1]
    assert checkpoint["checkpoint"]["completed_rounds"] == [2]
    assert checkpoint["checkpoint"]["clip_errors"] == []
    assert any(
        "round 1: broken round" in error
        for error in checkpoint["checkpoint"]["processing_errors"]
    )
    analysis = json.loads(result.analysis_json.read_text(encoding="utf-8"))
    assert analysis["clip_errors"] == []
    assert any("round 1: broken round" in error for error in analysis["processing_errors"])

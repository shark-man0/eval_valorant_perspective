from __future__ import annotations

import json
import logging
import os
import stat
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from valorant_ai_coach.logging_setup import configure_logging
from valorant_ai_coach.observability import (
    DiagnosticBundleRequest,
    PerformanceRecorder,
    bind_context,
    classify_exception,
    create_diagnostic_bundle,
    current_context,
    dependency_snapshot,
    instrument_pipeline,
    sanitize_text,
)
from valorant_ai_coach.observability import environment as environment_module
from valorant_ai_coach.observability import profiling as profiling_module


def _close_root_handlers() -> None:
    root = logging.getLogger()
    for handler in tuple(root.handlers):
        root.removeHandler(handler)
        handler.close()


def test_context_is_scoped_and_restored() -> None:
    assert current_context().run_id == "-"
    with bind_context(run_id="run-1", match_id="match-1", round_no=3, phase="hud"):
        value = current_context()
        assert value.run_id == "run-1"
        assert value.match_id == "match-1"
        assert value.round_no == "3"
        assert value.phase == "hud"
    assert current_context().run_id == "-"


def test_context_does_not_mix_between_threads() -> None:
    def worker(run_id: str) -> str:
        with bind_context(run_id=run_id):
            return current_context().run_id

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(worker, ("run-a", "run-b")))
    assert results == ["run-a", "run-b"]
    assert current_context().run_id == "-"


def test_logging_is_utf8_contextual_rotating_and_redacted(tmp_path: Path) -> None:
    try:
        log_path = configure_logging(tmp_path, max_bytes=1024, backup_count=1)
        assert logging.getLogger().level == logging.INFO
        logger = logging.getLogger("observability-test")
        with bind_context(run_id="R1", match_id="M1", phase="test"):
            for _ in range(100):
                logger.info("rotation-line-%s", "x" * 40)
            logger.info(
                "日本語 api_key=sk-abcdefghijklmnopqrstuvwxyz "
                "/Users/private/Videos/a.mp4"
            )
        for handler in logging.getLogger().handlers:
            handler.flush()

        combined = log_path.read_text(encoding="utf-8")
        rotated = log_path.with_name(log_path.name + ".1")
        if rotated.exists():
            combined += rotated.read_text(encoding="utf-8")
        assert "日本語" in combined
        assert "run=R1" in combined
        assert "match=M1" in combined
        assert "phase=test" in combined
        assert "sk-abcdefghijklmnopqrstuvwxyz" not in combined
        assert "/Users/private" not in combined
        assert len(logging.getLogger().handlers) == 1
        assert rotated.exists()
    finally:
        _close_root_handlers()


def test_exception_logging_keeps_traceback_and_redacts_paths(tmp_path: Path) -> None:
    try:
        log_path = configure_logging(tmp_path, max_bytes=100_000, backup_count=1)
        logger = logging.getLogger("observability-exception-test")
        with bind_context(run_id="R2", phase="failure"):
            try:
                raise RuntimeError("failed at /mnt/data/private/video.mp4")
            except RuntimeError:
                logger.exception("expected diagnostic exception")
        for handler in logging.getLogger().handlers:
            handler.flush()
        rendered = log_path.read_text(encoding="utf-8")
        assert "expected diagnostic exception" in rendered
        assert "Traceback" in rendered
        assert "/mnt/data/private" not in rendered
        assert "run=R2" in rendered
    finally:
        _close_root_handlers()


def test_performance_report_survives_failed_phase_and_unavailable_resources(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(profiling_module, "_peak_rss_bytes", lambda: None)
    monkeypatch.setattr(profiling_module, "_resident_memory_bytes", lambda: None)
    monkeypatch.setattr(
        profiling_module,
        "tool_version",
        lambda executable, *_args: f"version:{Path(executable).name}",
    )
    recorder = PerformanceRecorder("run", include_pi_metrics=False)
    recorder.set_tool_executables(ffmpeg="custom-ffmpeg", ffprobe="custom-ffprobe")
    with recorder.phase("ok"):
        pass
    with pytest.raises(RuntimeError), recorder.phase("failed"):
        raise RuntimeError("boom")
    recorder.finish("failed", failure_category="internal")
    report = recorder.report()
    assert report["total_elapsed_sec"] >= 0
    assert report["phase_durations"]["ok"]["duration_sec"] >= 0
    assert report["phase_durations"]["failed"]["failures"] == 1
    assert report["resources"]["peak_memory_bytes"] is None
    assert report["tools"]["ffmpeg"] == "version:custom-ffmpeg"
    assert report["tools"]["ffprobe"] == "version:custom-ffprobe"
    assert report["status"] == "failed"


def test_instrumentation_delegates_without_changing_results() -> None:
    calls: list[str] = []

    class Video:
        def probe(self, value: str) -> str:
            calls.append("probe")
            return value + "-probe"

        def extract_frames(self, value: str) -> str:
            calls.append("extract")
            return value + "-frames"

    class Engine:
        def evaluate(self, value: str) -> str:
            calls.append("rule")
            return value + "-rule"

    class Coach:
        def evaluate(self, value: str) -> str:
            calls.append("coach")
            return value + "-coach"

    class Analyzer:
        def __init__(self) -> None:
            self.rule_engine = Engine()
            self.coach = Coach()

        def analyze(self, package: dict[str, object]) -> dict[str, object]:
            calls.append("analyze")
            return dict(package)

    class Clips:
        def create_clip(self, value: str) -> str:
            calls.append("clip")
            return value + "-clip"

    class Repo:
        def save_job_checkpoint(self, value: str) -> str:
            calls.append("persist")
            return value + "-saved"

    class Hud:
        def process(self, value: str) -> str:
            calls.append("hud")
            return value + "-hud"

    class Pipeline:
        def __init__(self) -> None:
            self.video = Video()
            self.round_analyzer = Analyzer()
            self.clips = Clips()
            self.repository = Repo()
            self.hud_video_processor = Hud()

        def _write_analysis_json(self, value: str) -> str:
            calls.append("report")
            return value + "-report"

    pipeline = Pipeline()
    recorder = PerformanceRecorder("run", include_pi_metrics=False)
    session = instrument_pipeline(pipeline, recorder)
    try:
        assert pipeline.video.probe("a") == "a-probe"
        assert pipeline.video.extract_frames("a") == "a-frames"
        assert pipeline.hud_video_processor.process("a") == "a-hud"
        assert pipeline.round_analyzer.rule_engine.evaluate("a") == "a-rule"
        assert pipeline.round_analyzer.coach.evaluate("a") == "a-coach"
        assert pipeline.round_analyzer.analyze({"round_no": 7}) == {"round_no": 7}
        assert pipeline.clips.create_clip("a") == "a-clip"
        assert pipeline.repository.save_job_checkpoint("a") == "a-saved"
        assert pipeline._write_analysis_json("a") == "a-report"
    finally:
        session.close()
    recorder.finish("completed")
    phases = recorder.report()["phase_durations"]
    assert set(phases) >= {
        "video_probe",
        "frame_extraction",
        "hud_observation_processing",
        "rule_coach_processing",
        "round_analysis",
        "clip_generation",
        "persistence_report_generation",
    }
    assert calls == [
        "probe",
        "extract",
        "hud",
        "rule",
        "coach",
        "analyze",
        "clip",
        "persist",
        "report",
    ]


def test_dependency_snapshot_has_no_machine_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(environment_module, "tool_version", lambda *_args, **_kwargs: None)
    snapshot = dependency_snapshot(repository_root=None, package_names=())
    encoded = json.dumps(snapshot).lower()
    assert snapshot["schema_version"] == "1.0"
    assert "python" in snapshot and "platform" in snapshot
    assert "hostname" not in encoded
    assert "username" not in encoded
    assert "mac" not in encoded
    assert snapshot["tools"]["ffmpeg"] is None


def test_dependency_snapshot_reports_package_and_missing_tool() -> None:
    assert environment_module.tool_version("__definitely_missing_valorant_tool__") is None
    snapshot = dependency_snapshot(repository_root=None, package_names=("pytest",))
    assert snapshot["packages"]["pytest"] is not None


def test_sanitize_text_removes_secret_and_private_home_path() -> None:
    text = sanitize_text(
        "Authorization: Bearer topsecret token=abc123 /home/alice/private/video.mp4 "
        "/mnt/data/private/video.mp4 C:\\private\\video.mp4"
    )
    assert "topsecret" not in text
    assert "abc123" not in text
    assert "/home/alice" not in text
    assert "/mnt/data/private" not in text
    assert "C:\\private" not in text


def test_diagnostic_bundle_is_allowlist_only_bounded_and_sanitized(tmp_path: Path) -> None:
    perf = tmp_path / "performance.json"
    snap = tmp_path / "dependency_snapshot.json"
    log = tmp_path / "app.log"
    raw_video = tmp_path / "secret.mp4"
    perf.write_text(
        json.dumps({"api_key": "sk-supersecretvalue", "path": "/home/alice/a.mp4"}),
        encoding="utf-8",
    )
    snap.write_text(json.dumps({"username": "should-not-be-added-by-snapshot"}), encoding="utf-8")
    log.write_text(
        "\n".join([f"line {i} token=abc123 /mnt/data/private/video.mp4" for i in range(1000)]),
        encoding="utf-8",
    )
    raw_video.write_bytes(b"private")
    target = tmp_path / "bundle.zip"

    create_diagnostic_bundle(
        DiagnosticBundleRequest(
            run_id="r1",
            output_path=target,
            performance_path=perf,
            dependency_snapshot_path=snap,
            log_path=log,
            metadata={"authorization": "Bearer hidden"},
        )
    )
    with zipfile.ZipFile(target) as archive:
        names = set(archive.namelist())
        combined = "\n".join(archive.read(name).decode("utf-8") for name in names)
    assert names == {
        "manifest.json",
        "performance.json",
        "dependency_snapshot.json",
        "recent.log",
    }
    assert "secret.mp4" not in names
    assert "sk-supersecretvalue" not in combined
    assert "abc123" not in combined
    assert "should-not-be-added-by-snapshot" not in combined
    assert "/home/alice" not in combined
    assert "/mnt/data/private" not in combined
    assert "line 0" not in combined
    assert "line 999" in combined


def test_diagnostic_bundle_rejects_unsafe_run_id_before_writing(tmp_path: Path) -> None:
    target = tmp_path / "outside" / "diagnostic_bundle.zip"
    with pytest.raises(ValueError, match="run_id"):
        create_diagnostic_bundle(
            DiagnosticBundleRequest(run_id="../outside", output_path=target)
        )
    assert not target.exists()


def test_diagnostic_bundle_never_overwrites_existing_archive(tmp_path: Path) -> None:
    target = tmp_path / "bundle.zip"
    target.write_bytes(b"keep-me")
    with pytest.raises(FileExistsError):
        create_diagnostic_bundle(
            DiagnosticBundleRequest(run_id="safe-run", output_path=target)
        )
    assert target.read_bytes() == b"keep-me"


def test_diagnostic_bundle_omits_symlinked_json_input(tmp_path: Path) -> None:
    source = tmp_path / "private.json"
    source.write_text('{"path": "/home/private/video.mp4"}', encoding="utf-8")
    link = tmp_path / "performance.json"
    try:
        link.symlink_to(source)
    except OSError:
        pytest.skip("symlinks are unavailable on this platform")
    target = tmp_path / "bundle.zip"

    create_diagnostic_bundle(
        DiagnosticBundleRequest(
            run_id="safe-run",
            output_path=target,
            performance_path=link,
        )
    )

    with zipfile.ZipFile(target) as archive:
        value = json.loads(archive.read("performance.json"))
    assert value == {"status": "omitted", "reason": "symlink"}


def test_bundle_records_missing_optional_report_without_failing(tmp_path: Path) -> None:
    target = tmp_path / "bundle.zip"
    create_diagnostic_bundle(
        DiagnosticBundleRequest(
            run_id="r",
            output_path=target,
            performance_path=tmp_path / "missing.json",
        )
    )
    with zipfile.ZipFile(target) as archive:
        value = json.loads(archive.read("performance.json"))
    assert value["status"] == "unavailable"


def test_bundle_handles_malformed_optional_json(tmp_path: Path) -> None:
    malformed = tmp_path / "performance.json"
    malformed.write_text("{nope", encoding="utf-8")
    target = tmp_path / "bundle.zip"
    create_diagnostic_bundle(
        DiagnosticBundleRequest(run_id="r", output_path=target, performance_path=malformed)
    )
    with zipfile.ZipFile(target) as archive:
        value = json.loads(archive.read("performance.json"))
    assert value["status"] == "malformed"


@pytest.mark.parametrize(
    ("exc", "expected"),
    [
        (InterruptedError("cancel"), "cancelled"),
        (ImportError("missing"), "dependency"),
        (RuntimeError("ffprobe failed"), "video_probe"),
        (RuntimeError("clip failed"), "clip"),
        (RuntimeError("unknown"), "internal"),
    ],
)
def test_error_taxonomy(exc: BaseException, expected: str) -> None:
    assert classify_exception(exc) == expected


@pytest.mark.skipif(
    os.name == "nt", reason="POSIX permission bits are not authoritative on Windows"
)
def test_private_observability_files_use_owner_only_permissions(tmp_path: Path) -> None:
    try:
        log_path = configure_logging(tmp_path / "logs", max_bytes=256, backup_count=1)
        logger = logging.getLogger("permission-rotation-test")
        for _ in range(40):
            logger.info("rotate-%s", "x" * 40)
        for handler in logging.getLogger().handlers:
            handler.flush()
        bundle_path = tmp_path / "bundle.zip"
        create_diagnostic_bundle(
            DiagnosticBundleRequest(run_id="secure-run", output_path=bundle_path)
        )
        assert stat.S_IMODE(log_path.stat().st_mode) == 0o600
        rotated = log_path.with_name(log_path.name + ".1")
        assert rotated.exists()
        assert stat.S_IMODE(rotated.stat().st_mode) == 0o600
        assert stat.S_IMODE(bundle_path.stat().st_mode) == 0o600
    finally:
        _close_root_handlers()


def test_diagnostic_subprocess_does_not_inherit_openai_api_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, str] = {}

    class Result:
        returncode = 0
        stdout = "tool 1.0\n"
        stderr = ""

    def fake_run(*_args: object, **kwargs: object) -> Result:
        env = kwargs.get("env")
        assert isinstance(env, dict)
        captured.update({str(key): str(value) for key, value in env.items()})
        return Result()

    monkeypatch.setenv("OPENAI_API_KEY", "do-not-inherit")
    monkeypatch.setenv("SECURITY_TEST_SENTINEL", "preserved")
    monkeypatch.setattr(environment_module.subprocess, "run", fake_run)

    assert environment_module.tool_version("tool") == "tool 1.0"
    assert "OPENAI_API_KEY" not in captured
    assert captured["SECURITY_TEST_SENTINEL"] == "preserved"

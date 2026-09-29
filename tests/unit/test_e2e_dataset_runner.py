"""Orchestration boundary tests; fake pipeline IO is not real-video accuracy proof."""

import json
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts.e2e import run_dataset_case as runner
from scripts.e2e.evidence import failure_times


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


@pytest.fixture
def case(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    root.mkdir()
    (root / "datasets").mkdir()
    shutil.copyfile(
        runner.APP_ROOT / "datasets/manifest.schema.json", root / "datasets/manifest.schema.json"
    )
    video = tmp_path / "private name video.mp4"
    video.write_bytes(b"test video bytes; metadata is injected")
    pack = tmp_path / "pack"
    write_json(
        pack / "MANIFEST.json", {"name": "pack_v3", "source_sha256": runner.sha256_file(video)}
    )
    for name in ("tests/validate_pack.py", "tests/reference_evaluator.py"):
        path = pack / name
        path.parent.mkdir(exist_ok=True)
        path.write_text("# test boundary\n")
    assertions = {
        k: []
        for k in (
            "required_point_events",
            "required_state_intervals",
            "required_snapshots",
            "event_count_constraints",
            "negative_assertions",
            "ordering_constraints",
        )
    }
    write_json(pack / "tests/generated/e2e_assertions_v3.json", assertions)
    write_json(pack / "schemas/e2e_output_trace_schema_v1.json", {"type": "object"})
    args = runner.parser().parse_args(
        [
            "--video",
            str(video),
            "--video-id",
            "match_001",
            "--validation-pack",
            str(pack),
            "--register",
        ]
    )
    calls = []
    state = {"evaluation_code": 0, "probe_error": False}

    def command(cmd, **kwargs):
        calls.append(cmd)
        if cmd[0] == "git":
            text = b"a" * 40 if "rev-parse" in cmd else b""
            return subprocess.CompletedProcess(cmd, 0, text, b"")
        if "run_real_video.py" in cmd[1]:
            dest = Path(cmd[cmd.index("--output") + 1])
            write_json(
                dest / "raw_processing.json",
                {
                    "status": "complete",
                    "observations": [],
                    "visual_observations": [],
                    "visual_events": [],
                    "zone_resolutions": [],
                    "round_packages": [],
                    "source_video": str(video),
                },
            )
            write_json(
                dest / "e2e_trace.json",
                {
                    k: []
                    for k in (
                        "events",
                        "state_intervals",
                        "ownership_intervals",
                        "snapshots",
                        "visual_observations",
                        "temporal_features",
                    )
                },
            )
        if "evaluate_saved_trace.py" in cmd[1]:
            write_json(
                Path(cmd[cmd.index("--output") + 1]),
                {
                    "pass": state["evaluation_code"] == 0,
                    "schema_valid": True,
                    "failure_count": state["evaluation_code"],
                    "negative_assertion_count": 0,
                    "failures": ["count:r1:shot"] if state["evaluation_code"] else [],
                },
            )
            return subprocess.CompletedProcess(cmd, state["evaluation_code"])
        return subprocess.CompletedProcess(cmd, 0)

    def probe(path):
        if state["probe_error"]:
            raise RuntimeError("ffprobe D:\\Users\\Private\\clip.mp4")
        return SimpleNamespace(
            duration_sec=12.0, width=1920, height=1080, fps=60.0, audio_tracks=[{}, {}, {}]
        )

    monkeypatch.setattr(runner.shutil, "which", lambda name: name)
    return SimpleNamespace(
        root=root,
        video=video,
        pack=pack,
        args=args,
        command=command,
        calls=calls,
        state=state,
        probe=probe,
    )


def execute(c):
    return runner.run_case(c.args, root=c.root, runner=c.command, probe=c.probe)


def test_register_match_run_and_never_overwrite_manifest(case):
    c = case
    assert execute(c) == 0
    manifest_path = c.root / "datasets/manifests/match_001.json"
    before = manifest_path.read_bytes()
    manifest = json.loads(before)
    runner.validate_manifest(manifest, c.root)
    assert manifest["filename"] == "match_001.mp4"
    assert str(c.video) not in before.decode()
    assert execute(c) == 2
    assert manifest_path.read_bytes() == before
    c.args.register = False
    assert execute(c) == 0
    report = json.loads((c.root / "e2e_reports/match_001/summary.json").read_text())
    assert report["metadata"]["analyzer_commit"] == "a" * 40
    assert report["metadata"]["git_is_dirty"] is False
    assert report["result"]["status"] == "pass"


@pytest.mark.parametrize(
    "fault,code",
    [
        ("absent_video", "VIDEO_NOT_FOUND"),
        ("changed_sha", "VALIDATION_PACK_VIDEO_SHA256_MISMATCH"),
        ("absent_pack", "VALIDATION_PACK_MISSING"),
        ("probe", "FFPROBE_METADATA_FAILED"),
    ],
)
def test_preflight_rejects_without_starting_analyzer(case, fault, code):
    c = case
    if fault == "absent_video":
        c.args.video = str(c.root / "missing.mp4")
    elif fault == "changed_sha":
        c.video.write_bytes(b"different recording")
    elif fault == "absent_pack":
        c.args.validation_pack = str(c.root / "missing")
    else:
        c.state["probe_error"] = True
    assert execute(c) == 2
    assert not any("run_real_video.py" in " ".join(cmd) for cmd in c.calls)
    report = json.loads((c.root / "e2e_reports/match_001/summary.json").read_text())
    assert report["result"]["status"] == "fail"
    assert report["result"]["error_code"] == code
    assert "Private" not in json.dumps(report)


def test_manifest_hash_mismatch_rejected(case):
    c = case
    assert execute(c) == 0
    manifest_path = c.root / "datasets/manifests/match_001.json"
    value = json.loads(manifest_path.read_text())
    value["sha256"] = "f" * 64
    write_json(manifest_path, value)
    c.args.register = False
    c.calls.clear()
    assert execute(c) == 2
    assert not any("run_real_video.py" in " ".join(cmd) for cmd in c.calls)


def test_evaluator_fail_propagates_and_exports_detail(case):
    case.state["evaluation_code"] = 1
    assert execute(case) == 1
    report = json.loads((case.root / "e2e_reports/match_001/summary.json").read_text())
    assert report["result"]["status"] == "fail"
    assert report["failures"][0]["category"] == "count"
    assert not list((case.root / "e2e_reports").rglob("raw_processing.json"))


def test_path_precedence_and_no_env_execution(tmp_path):
    (tmp_path / ".env.local").write_text('OTHER=secret\nVALORANT_E2E_VIDEO="file video.mp4"\n')
    args = SimpleNamespace(video=None, validation_pack=None)
    assert runner.resolve_inputs(args, tmp_path, {})[0].name == "file video.mp4"
    env = {"VALORANT_E2E_VIDEO": "env.mp4", "VALORANT_E2E_PACK": "env-pack"}
    assert runner.resolve_inputs(args, tmp_path, env)[0].name == "env.mp4"
    args.video, args.validation_pack = "cli.mp4", "cli-pack"
    video, pack = runner.resolve_inputs(args, tmp_path, env)
    assert video.name == "cli.mp4" and pack.name == "cli-pack"


def test_manifest_schema_rejects_absolute_path_and_extra_secrets(case):
    assert execute(case) == 0
    value = json.loads((case.root / "datasets/manifests/match_001.json").read_text())
    import jsonschema

    for changes in (
        {"filename": "D:\\secret\\video.mp4"},
        {"api_key": "secret"},
        {"video_id": "../escape"},
        {"sha256": "wrong"},
    ):
        with pytest.raises(jsonschema.ValidationError):
            runner.validate_manifest({**value, **changes}, case.root)


def test_evidence_failure_selection_is_bounded_and_only_for_failures():
    assertions = {
        "required_point_events": [
            {"id": f"p{i}", "acceptance_window": [i, i + 0.1]} for i in range(20)
        ]
    }
    evaluation = {"failures": [f"missing_point:p{i}" for i in range(20)]}
    assert len(failure_times(evaluation, assertions, 3)) == 3
    assert failure_times({"failures": []}, assertions, 3) == []

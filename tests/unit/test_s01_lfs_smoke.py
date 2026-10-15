"""Contract tests for the opt-in LFS source-bound point-smoke entrypoint."""

import hashlib
import json
from pathlib import Path

import pytest

from scripts.e2e import run_s01_lfs_smoke as smoke


@pytest.fixture
def inputs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path, Path]:
    video = tmp_path / "match_001.mp4"
    video.write_bytes(b"real-video-test-double")
    monkeypatch.setattr(smoke, "VIDEO_PATH", video)
    monkeypatch.setattr(smoke, "SOURCE_SHA256", hashlib.sha256(video.read_bytes()).hexdigest())
    monkeypatch.setattr(smoke, "SOURCE_SIZE", video.stat().st_size)
    pack = tmp_path / "pack"
    pack.mkdir()
    (pack / "MANIFEST.json").write_text(
        json.dumps({"source_sha256": smoke.SOURCE_SHA256}), encoding="utf-8"
    )
    layout = tmp_path / "profile.json"
    layout.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(
        smoke,
        "load_suite",
        lambda path, mode, source, categories: {"frames": [1] * (
            16 if "regression_protection" in categories else 7
        )},
    )
    return video, pack, layout


def invocation(pack: Path, layout: Path, *extra: str) -> list[str]:
    return ["--validation-pack", str(pack), "--hud-layout", str(layout), *extra]


def test_preflight_is_read_only_and_never_runs_analyzer(inputs, monkeypatch):
    _, pack, layout = inputs
    monkeypatch.setattr(
        smoke.run_dataset_case,
        "main",
        lambda argv: pytest.fail("recognition must not run in preflight-only"),
    )
    assert smoke.main(invocation(pack, layout, "--preflight-only")) == 0


def test_exact_fixture_only_invokes_bounded_seven_point_runner(inputs, monkeypatch):
    video, pack, layout = inputs
    calls = []
    monkeypatch.setattr(smoke.run_dataset_case, "main", lambda argv: calls.append(argv) or 1)

    # Existing failed numeric assertions must be propagated, never converted to PASS.
    assert smoke.main(invocation(pack, layout)) == 1
    assert len(calls) == 1
    argv = calls[0]
    assert argv[argv.index("--video") + 1] == str(video)
    assert argv[argv.index("--video-id") + 1] == "match_001"
    assert argv[argv.index("--mode") + 1] == "targeted"
    assert argv.count("--category") == 1
    assert argv[argv.index("--category") + 1] == "round_boundary"
    assert "--register" not in argv and "--mode full" not in " ".join(argv)
    assert "--unedited-input-contract" not in argv


def test_optional_regression_points_do_not_switch_to_full(inputs, monkeypatch):
    _, pack, layout = inputs
    calls = []
    monkeypatch.setattr(smoke.run_dataset_case, "main", lambda argv: calls.append(argv) or 0)
    assert smoke.main(invocation(pack, layout, "--include-regressions")) == 0
    assert calls[0].count("--category") == 2
    assert "regression_protection" in calls[0]
    assert calls[0][calls[0].index("--mode") + 1] == "targeted"


@pytest.mark.parametrize(
    ("replacement", "expected"),
    [
        (b"version https://git-lfs.github.com/spec/v1\noid sha256:...", "LFS_POINTER_ONLY"),
        (b"wrong-size", "VIDEO_SIZE_MISMATCH"),
    ],
)
def test_malformed_lfs_source_fails_before_runner(inputs, replacement, expected, capsys):
    video, pack, layout = inputs
    video.write_bytes(replacement)
    assert smoke.main(invocation(pack, layout, "--preflight-only")) == 2
    assert expected in capsys.readouterr().err


def test_same_size_different_content_is_rejected(inputs, capsys):
    video, pack, layout = inputs
    video.write_bytes(b"x" * video.stat().st_size)
    assert smoke.main(invocation(pack, layout, "--preflight-only")) == 2
    assert "VIDEO_SHA256_MISMATCH" in capsys.readouterr().err


def test_missing_or_symlink_video_rejected(inputs, tmp_path, capsys):
    video, pack, layout = inputs
    video.unlink()
    assert smoke.main(invocation(pack, layout, "--preflight-only")) == 2
    assert "LFS_VIDEO_MISSING" in capsys.readouterr().err

    other = tmp_path / "other.mp4"
    other.write_bytes(b"real-video-test-double")
    try:
        video.symlink_to(other)
    except OSError:
        pytest.skip("symlinks require additional privileges on this runner")
    assert smoke.main(invocation(pack, layout, "--preflight-only")) == 2
    assert "VIDEO_SYMLINK_REJECTED" in capsys.readouterr().err


def test_pack_source_mismatch_is_fatal(inputs, capsys):
    _, pack, layout = inputs
    (pack / "MANIFEST.json").write_text(
        json.dumps({"source_sha256": "0" * 64}), encoding="utf-8"
    )
    assert smoke.main(invocation(pack, layout, "--preflight-only")) == 2
    assert "VALIDATION_PACK_SOURCE_MISMATCH" in capsys.readouterr().err


def test_comparison_arguments_forwarded_without_mutation(inputs, monkeypatch, tmp_path):
    _, pack, layout = inputs
    calls = []
    monkeypatch.setattr(smoke.run_dataset_case, "main", lambda argv: calls.append(argv) or 0)
    old = tmp_path / "old_run"
    output = tmp_path / "new_run"
    assert smoke.main(
        invocation(pack, layout, "--previous", str(old), "--output", str(output))
    ) == 0
    assert calls[0][calls[0].index("--previous") + 1] == str(old)
    assert calls[0][calls[0].index("--output") + 1] == str(output)
    assert not old.exists() and not output.exists()

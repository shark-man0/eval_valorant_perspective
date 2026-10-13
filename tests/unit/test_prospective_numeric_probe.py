import json

import pytest
from test_geometry_candidate_challenge import fixture

from scripts.diagnostics import prospective_numeric_probe as subject
from scripts.diagnostics.prospective_numeric_probe import (
    freeze_plan,
    measure,
    sampling_times,
    verify_partition,
)
from scripts.e2e.run_dataset_case import sha256_file


@pytest.fixture(autouse=True)
def synthetic_toolchain(monkeypatch):
    monkeypatch.setattr(subject, "toolchain_fingerprints", lambda: {"synthetic": "unchanged"})


def test_plan_samples_only_fixed_unseen_development_times():
    previous = [16.75, 46.75, 75.0]
    result = sampling_times(720, previous)
    assert result == sampling_times(720, previous)
    assert all(0 <= t < 720 for t in result)
    assert all(abs(t - old) >= 2 for t in result for old in previous)
    assert 16.75 not in result and 46.75 not in result
    assert all((t - 16.75) % 30 == 0 for t in result)


@pytest.mark.parametrize("end,previous", [
    (True, []), (float("nan"), []), (-1, []), (120, []),
    (720, [float("inf")]), (720, [True]),
])
def test_no_holdout_fallback_or_nonfinite_sampling(end, previous):
    with pytest.raises(ValueError):
        sampling_times(end, previous)


def frozen(tmp_path):
    trial = fixture(tmp_path / "trial")
    video = tmp_path / "synthetic_not_real_video.bin"
    video.write_bytes(b"synthetic-only")
    source = sha256_file(video)
    history = tmp_path / "prior_diagnostic.json"
    history.write_text(json.dumps({
        "source_sha256": source, "candidate_assets_frozen_before_validation": True,
        "production_adopted": False, "identity_assets_generated": False,
        "training_frames": [{"source_frame_pts": 10, "sha256": "1" * 64}],
        "validation_frames": []}))
    plan_path = tmp_path / "plan.json"
    partition = tmp_path / "partition.json"
    partition.write_text(json.dumps({"kind": "development_holdout_partition_not_gt",
        "source_video_sha256": source,
        "development": {"start_sec_inclusive": 0, "end_sec_exclusive": 720},
        "holdout": {"start_sec_inclusive": 720, "end_sec_exclusive": 1000}}))
    plan = freeze_plan(video, source, trial, [history], 720, plan_path, partition=partition)
    return plan, plan_path, video, trial, history


def test_plan_frozen_before_decode_and_never_contains_expected_numbers(tmp_path):
    plan, plan_path, video, trial, history = frozen(tmp_path)
    assert plan_path.is_file()
    assert plan["source_labels_available"] is False
    assert plan["production_adopted"] is False
    assert plan["evaluation_holdout_used"] is False
    assert str(history.resolve()) in plan["inputs_sha256"]
    assert plan["excluded_source_hashes"] == ["1" * 64]
    assert "expected_values" not in plan
    with pytest.raises(FileExistsError):
        freeze_plan(video, sha256_file(video), trial, [history], 720, plan_path,
                    partition=tmp_path / "partition.json")


@pytest.mark.parametrize("changed", ["video", "profile", "history"])
def test_measure_rejects_drift_before_decoding(tmp_path, changed):
    _, plan_path, video, trial, history = frozen(tmp_path)
    path = {"video": video, "profile": trial / "hud_layout.templates.json",
            "history": history}[changed]
    path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(ValueError, match="inputs changed"):
        measure(plan_path, tmp_path / "probe")
    assert not (tmp_path / "probe").exists()


def test_validation_pack_cannot_be_used_as_sampling_history(tmp_path):
    _, _, video, trial, history = frozen(tmp_path)
    history.write_text(json.dumps({"source_sha256": sha256_file(video),
                                   "expected_states": ["live_first_person"]}))
    with pytest.raises(ValueError, match="diagnostics permitted"):
        freeze_plan(video, sha256_file(video), trial, [history], 720, tmp_path / "invalid.json",
                    partition=tmp_path / "partition.json")


@pytest.mark.parametrize("end", [720.1, 1000, True, float("nan"), 719])
def test_cli_end_cannot_expand_or_redefine_frozen_partition(tmp_path, end):
    _, _, video, _, _ = frozen(tmp_path)
    with pytest.raises(ValueError, match="frozen partition"):
        verify_partition(tmp_path / "partition.json", sha256_file(video), end)


@pytest.mark.parametrize("drift", ["partition", "toolchain"])
def test_partition_drift_or_toolchain_drift_rejected_before_decode(tmp_path, monkeypatch, drift):
    _, plan_path, _, _, _ = frozen(tmp_path)
    if drift == "toolchain":
        monkeypatch.setattr(subject, "toolchain_fingerprints", lambda: {"synthetic": "changed"})
    else:
        partition = tmp_path / "partition.json"
        partition.write_text(partition.read_text() + " ")
    with pytest.raises(ValueError, match="inputs changed"):
        measure(plan_path, tmp_path / "probe")
    assert not (tmp_path / "probe").exists()


def test_unversioned_completed_plan_must_not_be_upgraded_in_place(tmp_path):
    _, plan_path, _, _, _ = frozen(tmp_path)
    data = json.loads(plan_path.read_text())
    del data["schema_version"]
    plan_path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="do not rewrite v1"):
        measure(plan_path, tmp_path / "probe")


def test_other_source_or_gt_cannot_replace_partition(tmp_path):
    _, _, video, _, _ = frozen(tmp_path)
    partition = tmp_path / "partition.json"
    with pytest.raises(ValueError, match="non-GT partition"):
        verify_partition(partition, "0" * 64, 720)
    partition.write_text(json.dumps({"kind": "ground_truth", "source_video_sha256":
                                    sha256_file(video)}))
    with pytest.raises(ValueError, match="non-GT partition"):
        verify_partition(partition, sha256_file(video), 720)

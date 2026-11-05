"""Real tiny native transport with a nonzero PTS origin and no identity seed."""

import csv
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from valorant_ai_coach.temporal import match as module
from valorant_ai_coach.video.service import VideoProbeError


@pytest.fixture
def native_case(tmp_path):
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        pytest.skip("Optional development FFmpeg transport unavailable")
    video = tmp_path / "synthetic.mp4"
    subprocess.run(
        [
            shutil.which("ffmpeg"),
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "color=c=blue:s=96x64:r=2:d=2",
            "-vf",
            "setpts=PTS+5/TB",
            "-copyts",
            "-c:v",
            "mpeg4",
            "-threads",
            "1",
            str(video),
        ],
        check=True,
        timeout=20,
    )
    source_sha = hashlib.sha256(video.read_bytes()).hexdigest()
    manifest, allocation, policy, config = (
        tmp_path / name
        for name in ("manifest.json", "allocation.json", "policy.json", "config.json")
    )
    manifest.write_text(
        json.dumps(
            {
                "records": [
                    {
                        "video_id": "registered-synthetic",
                        "source_sha256": source_sha,
                        "managed_path": str(video),
                        "physical_match_id": "synthetic",
                        "status": "accepted",
                        "split": "DEVELOPMENT",
                        "exposure": "DEVELOPMENT",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    allocation.write_text("{}", encoding="utf-8")
    policy.write_text(
        json.dumps(
            {
                "manifest": str(manifest),
                "allocation": str(allocation),
                "manifest_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
                "allocation_sha256": hashlib.sha256(allocation.read_bytes()).hexdigest(),
                "allowed_source_sha256s": [source_sha],
            }
        ),
        encoding="utf-8",
    )
    config.write_text("{}", encoding="utf-8")

    return policy, config


@pytest.mark.parametrize("report_view_bridge", [False, True])
def test_full_file_native_origin_and_recording_second_grid(
    tmp_path, monkeypatch, native_case, report_view_bridge
):
    policy, config = native_case

    class PixelObserver:
        def __init__(self, config_path: Path):
            self.fingerprint, self.bindings = "a" * 64, {}

        def inspect(self, image):
            assert image.shape == (64, 96, 3)
            return {"signals": [], "context": {}, "raw": {}, "map_candidates": []}

    monkeypatch.setattr(module, "ProfileHudObserver", PixelObserver)
    output = tmp_path / "run"
    receipt = module.run_match(
        policy_path=policy,
        source_id="registered-synthetic",
        reader_config=config,
        output=output,
        max_refinement_windows=0,
        report_view_bridge=report_view_bridge,
    )
    assert receipt["whole_file_completed"] is True
    assert receipt["source_bytes_verified_before_and_after"] is True
    assert receipt["native_start_pts_tick"] > 0
    timeline = json.loads((output / "timeline_PRIVATE.json").read_text(encoding="utf-8"))
    assert receipt["shared_engine_configuration"] == timeline["configuration"]
    assert ("report_view_bridge" in timeline["configuration"]) == report_view_bridge
    assert all(
        f["sample"]["native_pts_tick"] >= receipt["native_start_pts_tick"]
        for f in timeline["frames"]
    )
    with (output / "timeline_1s_PRIVATE.csv").open(encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    assert [r["recording_second"] for r in rows] == ["0", "1"]
    assert all(r["round"] == r["life"] == r["camera"] == "UNKNOWN" for r in rows)
    assert all(r["round_number"] == r["round_number_candidates"] == "UNKNOWN" for r in rows)
    assert timeline["qualified_events"] == timeline["qualified_facts"] == []


def test_reconstruction_fingerprint_binds_mode_but_not_acquisition_epoch(
    tmp_path, monkeypatch, native_case
):
    policy, config = native_case

    class Pixels:
        def __init__(self, config_path):
            self.fingerprint, self.bindings = "a" * 64, {}

        def inspect(self, image):
            return {"signals": [], "context": {}, "raw": {}, "map_candidates": []}

    monkeypatch.setattr(module, "ProfileHudObserver", Pixels)
    receipts = [module.run_match(
        policy_path=policy, source_id="registered-synthetic", reader_config=config,
        output=tmp_path / ("fingerprint_run" + str(i)), max_refinement_windows=0,
        report_view_bridge=flag,
    ) for i, flag in enumerate([False, False, True])]
    assert len({r["epoch"] for r in receipts}) == 3
    assert len({r["reader_fingerprint"] for r in receipts}) == 1
    assert receipts[0]["state_reconstruction_fingerprint"] == receipts[1][
        "state_reconstruction_fingerprint"]
    assert receipts[0]["state_reconstruction_fingerprint"] != receipts[2][
        "state_reconstruction_fingerprint"]


class CompositePixels:
    def __init__(self, config_path):
        self.fingerprint = "a" * 64
        self.bindings = {
            "baseline_producer_fingerprints": ["b" * 64],
            "supplier_producer_fingerprints": ["b" * 64, "c" * 64],
        }

    def inspect(self, image):
        assert image.shape == (64, 96, 3)  # no Source/time/roster argument
        return {
            "signals": ["buy", "owner_hud"],
            "context": {},
            "raw": {},
            "map_candidates": [],
            "supplier_observations": [
                {
                    "producer_fingerprint": "b" * 64,
                    "signals": ["buy"],
                    "raw": {},
                    "context": {"stream_kind": "base", "score": [2, 1]},
                },
                {
                    "producer_fingerprint": "c" * 64,
                    "signals": ["owner_hud"],
                    "raw": {},
                    "context": {"stream_kind": "view", "unqualified_view_model": True},
                },
            ],
        }


def test_source_blind_factory_keeps_separate_suppliers_and_same_native_baseline(
    tmp_path, native_case
):
    policy, config = native_case
    output = tmp_path / "composite"
    receipt = module.run_match(
        policy_path=policy,
        source_id="registered-synthetic",
        reader_config=config,
        output=output,
        max_refinement_windows=0,
        observer_factory=CompositePixels,
    )
    actual = json.loads((output / "timeline_PRIVATE.json").read_text(encoding="utf-8"))
    baseline = json.loads((output / "baseline_timeline_PRIVATE.json").read_text(encoding="utf-8"))
    assert [r["sample"] for r in actual["frames"]] == [r["sample"] for r in baseline["frames"]]
    assert all(r["camera"]["value"] == "UNKNOWN" for r in baseline["frames"])
    assert all(
        r["camera"]["hypotheses"] == ["REMOTE", "SELF", "UNKNOWN"]
        and r["map"]["current_recorder_view_evidence_ids"] == []
        for r in actual["frames"]
    )
    assert all(len(r["observation_ids"]) == 2 for r in actual["frames"])
    assert all(r["round_number"]["value"] == 4 for r in actual["frames"])
    with (output / "timeline_1s_PRIVATE.csv").open(encoding="utf-8") as stream:
        csv_rows = list(csv.DictReader(stream))
    assert all(r["round_number"] == r["round_number_candidates"] == "4" for r in csv_rows)
    assert all(r["qualification"] == "development_only" for r in csv_rows)
    assert (
        receipt["artifact_sha256s"]["baseline_timeline_PRIVATE.json"]
        == hashlib.sha256((output / "baseline_timeline_PRIVATE.json").read_bytes()).hexdigest()
    )
    assert actual["qualified_facts"] == actual["qualified_events"] == []


def test_native_audit_adds_exact_off_grid_frame_and_preserves_reference_epoch(
    tmp_path, native_case
):
    from fractions import Fraction

    policy, config = native_case
    original = tmp_path / "original"
    module.run_match(
        policy_path=policy,
        source_id="registered-synthetic",
        reader_config=config,
        output=original,
        max_refinement_windows=0,
        coarse_seconds=Fraction(1, 2),
        observer_factory=CompositePixels,
    )
    samples = json.loads((original / "observations_PRIVATE.json").read_text(encoding="utf-8"))
    reference = samples["records"][1]["sample"]
    plan = tmp_path / "audit.json"
    plan.write_text(
        json.dumps({"schema": "development_native_audit_v1", "samples": [reference]}),
        encoding="utf-8",
    )
    output = tmp_path / "audited"
    receipt = module.run_match(
        policy_path=policy,
        source_id="registered-synthetic",
        reader_config=config,
        output=output,
        max_refinement_windows=0,
        observer_factory=CompositePixels,
        audit_sample_plan=plan,
    )
    assert receipt["native_audit"]["additional_native_points"] == 1
    alias = json.loads((output / "native_audit_aliases_PRIVATE.json").read_text(encoding="utf-8"))[
        "records"
    ][0]
    assert alias["reference_sample"] == reference
    assert alias["observed_sample"]["native_epoch"] != reference["native_epoch"]
    assert all(
        alias["observed_sample"][k] == reference[k]
        for k in [
            "source_sha256",
            "native_pts_tick",
            "native_time_base",
            "frame_size_px",
            "native_pixel_sha256",
        ]
    )
    assert alias["independent_confirmation"] is False


def test_missing_baseline_supplier_never_writes_completion(tmp_path, native_case):
    policy, config = native_case

    class MissingBase(CompositePixels):
        def inspect(self, image):
            result = super().inspect(image)
            result["supplier_observations"] = result["supplier_observations"][1:]
            return result

    output = tmp_path / "missing_base"
    with pytest.raises(ValueError, match="Baseline supplier missing"):
        module.run_match(
            policy_path=policy,
            source_id="registered-synthetic",
            reader_config=config,
            output=output,
            max_refinement_windows=0,
            observer_factory=MissingBase,
        )
    assert not (output / "completion_PRIVATE.json").exists()


def test_changed_observer_binding_never_writes_completion(tmp_path, native_case):
    policy, config = native_case
    count = 0

    def factory(path):
        nonlocal count
        count += 1
        instance = CompositePixels(path)
        instance.fingerprint = hashlib.sha256(str(count).encode("utf-8")).hexdigest()
        return instance

    output = tmp_path / "drift"
    with pytest.raises(ValueError, match="bindings changed"):
        module.run_match(
            policy_path=policy,
            source_id="registered-synthetic",
            reader_config=config,
            output=output,
            max_refinement_windows=0,
            observer_factory=factory,
        )
    assert not (output / "completion_PRIVATE.json").exists()


def test_pilot_limit_is_exclusive_in_native_and_display_clocks(tmp_path, native_case):
    from fractions import Fraction

    policy, config = native_case
    output = tmp_path / "one_second"
    receipt = module.run_match(
        policy_path=policy,
        source_id="registered-synthetic",
        reader_config=config,
        output=output,
        observer_factory=CompositePixels,
        stop_after=1,
        max_refinement_windows=0,
    )
    assert receipt["whole_file_completed"] is False
    data = json.loads((output / "timeline_PRIVATE.json").read_text(encoding="utf-8"))
    origin = receipt["native_start_pts_tick"] * Fraction(
        data["frames"][0]["sample"]["native_time_base"]
    )
    assert all(
        0 <= r["sample"]["native_pts_tick"] * Fraction(r["sample"]["native_time_base"]) - origin < 1
        for r in data["frames"]
    )
    assert len(data["seconds"]) == 1


def test_unbound_supplier_never_writes_completion(tmp_path, native_case):
    policy, config = native_case

    class Unbound(CompositePixels):
        def inspect(self, image):
            result = super().inspect(image)
            result["supplier_observations"][1]["producer_fingerprint"] = "f" * 64
            return result

    output = tmp_path / "unbound"
    with pytest.raises(ValueError, match="Unbound supplier"):
        module.run_match(
            policy_path=policy,
            source_id="registered-synthetic",
            reader_config=config,
            output=output,
            observer_factory=Unbound,
            max_refinement_windows=0,
        )
    assert not (output / "completion_PRIVATE.json").exists()


@pytest.mark.parametrize("fault", ["pixels", "missing_tick"])
def test_changed_or_missing_native_audit_point_never_writes_completion(
    tmp_path, native_case, fault
):
    from fractions import Fraction

    from valorant_ai_coach.temporal.evidence import freeze_native_sample

    policy, config = native_case
    original = tmp_path / "audit_reference"
    module.run_match(
        policy_path=policy,
        source_id="registered-synthetic",
        reader_config=config,
        output=original,
        max_refinement_windows=0,
        coarse_seconds=Fraction(1, 2),
        observer_factory=CompositePixels,
    )
    data = json.loads((original / "observations_PRIVATE.json").read_text(encoding="utf-8"))
    reference = dict(data["records"][1]["sample"])
    del reference["sample_sha256"]
    if fault == "pixels":
        reference["native_pixel_sha256"] = "f" * 64
    else:
        reference["native_pts_tick"] += 1
    reference = freeze_native_sample(reference)
    plan = tmp_path / "bad_audit.json"
    plan.write_text(
        json.dumps({"schema": "development_native_audit_v1", "samples": [reference]}),
        encoding="utf-8",
    )
    output = tmp_path / "bad_audit"
    with pytest.raises((ValueError, VideoProbeError)):
        module.run_match(
            policy_path=policy,
            source_id="registered-synthetic",
            reader_config=config,
            output=output,
            max_refinement_windows=0,
            observer_factory=CompositePixels,
            audit_sample_plan=plan,
        )
    assert not (output / "completion_PRIVATE.json").exists()


def test_native_identity_precedes_supplier_in_place_preprocessing(tmp_path, native_case):
    policy, config = native_case
    original = tmp_path / "native_original"
    module.run_match(
        policy_path=policy,
        source_id="registered-synthetic",
        reader_config=config,
        output=original,
        observer_factory=CompositePixels,
        max_refinement_windows=0,
    )

    class Preprocessed(CompositePixels):
        def inspect(self, image):
            image[:] = 0
            return super().inspect(image)

    processed = tmp_path / "preprocessed"
    module.run_match(
        policy_path=policy,
        source_id="registered-synthetic",
        reader_config=config,
        output=processed,
        observer_factory=Preprocessed,
        max_refinement_windows=0,
    )
    before = json.loads((original / "observations_PRIVATE.json").read_text(encoding="utf-8"))
    after = json.loads((processed / "observations_PRIVATE.json").read_text(encoding="utf-8"))
    assert [r["sample"]["native_pixel_sha256"] for r in before["records"]] == [
        r["sample"]["native_pixel_sha256"] for r in after["records"]
    ]

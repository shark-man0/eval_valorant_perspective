import hashlib
import json
import sys

import cv2
import numpy as np
import pytest
from test_hud_temporal_calibration import FakeVideoService, _frames, _layout

from scripts.diagnostics import diagnose_geometry_edges as experiment
from valorant_ai_coach.hud.layout import HudLayout, NormalizedRoi
from valorant_ai_coach.hud.templates import HudTemplateProfile


def changing_brightness():
    images = []
    for index in range(32):
        image = np.full((100, 160, 3), 20 + 4 * index, np.uint8)
        cv2.rectangle(image, (15, 15), (140, 80), (80 + 4 * index,) * 3, 3)
        cv2.line(image, (25, 30), (120, 65), (120 + 4 * index,) * 3, 3)
        images.append(image)
    return images


def test_edge_mask_survives_brightness_without_lowering_raw_ncc():
    result, assets = experiment.compare(changing_brightness(), .90)
    assert result["current_mask"]["selected_pixels"] == 0
    assert result["experiment"]["status"] == "raw_ncc_supported"
    assert result["experiment"]["training_accept_count"] == 16
    assert result["experiment"]["holdout_accept_count"] == 16
    assert result["experiment"]["holdout_similarity"]["min"] >= .90
    assert all(score < .90 for score in result["experiment"]["synthetic_flat_shift_scores"])
    assert result["production_qualified"] is False
    assert assets is not None


def test_holdout_cannot_select_or_modify_template_pixels():
    images = changing_brightness()
    before, before_assets = experiment.compare(images, .90)
    altered = [image if index % 2 == 0 else np.full_like(image, 70)
               for index, image in enumerate(images)]
    after, after_assets = experiment.compare(altered, .90)
    assert before["experiment"]["status"] == "raw_ncc_supported"
    assert after["experiment"]["status"] == "raw_ncc_rejected"
    assert after["experiment"]["holdout_accept_count"] == 0
    for left, right in zip(before_assets, after_assets, strict=True):
        assert np.array_equal(left, right)


def test_flat_and_unrelated_scene_noise_do_not_generate_candidate():
    assert experiment.edge_candidate([np.full((100, 160, 3), 70, np.uint8)] * 16) is None
    rng = np.random.default_rng(12)
    noise = [rng.integers(0, 255, (100, 160, 3), dtype=np.uint8) for _ in range(16)]
    assert experiment.edge_candidate(noise) is None
    assert experiment.edge_candidate(changing_brightness()[:7]) is None


def test_medoid_is_an_observed_training_frame_and_selection_excludes_self():
    images = changing_brightness()
    report, assets = experiment.compare(images, .90, template_strategy="training_medoid")
    assert assets is not None
    reference, mask = assets
    details = report["experiment"]
    index = details["selected_training_index"]
    assert np.array_equal(reference, cv2.cvtColor(images[index * 2], cv2.COLOR_BGR2GRAY))
    assert details["selection_scores_exclude_self"] is True
    assert max(row["nonself_accept_count"]
               for row in details["training_reference_candidates"]) == 15
    assert report["threshold"] == .90 and report["production_qualified"] is False
    assert details["selected_contrast_std"] == pytest.approx(float(reference[mask > 0].std()))
    assert all(score < .90 for score in details["synthetic_flat_shift_scores"])


def test_medoid_reference_and_mask_cannot_be_selected_by_holdout():
    images = changing_brightness()
    before, before_assets = experiment.compare(images, .90, template_strategy="training_medoid")
    poisoned = [image if i % 2 == 0 else np.full_like(image, 70)
                for i, image in enumerate(images)]
    after, after_assets = experiment.compare(poisoned, .90, template_strategy="training_medoid")
    assert before["experiment"]["status"] == "raw_ncc_supported"
    assert after["experiment"]["holdout_accept_count"] == 0
    assert after["experiment"]["status"] == "raw_ncc_rejected"
    assert before["experiment"]["training_reference_candidates"] == (
        after["experiment"]["training_reference_candidates"])
    for left, right in zip(before_assets, after_assets, strict=True):
        assert np.array_equal(left, right)


def test_unknown_template_strategy_is_not_silently_used():
    with pytest.raises(ValueError, match="strategy"):
        experiment.compare(changing_brightness(), .90, template_strategy="lower_threshold")


@pytest.mark.parametrize("fault", [None, "missing", "outside", "duplicate", "resolution"])
def test_cli_exports_only_private_diagnostics_not_a_runtime_profile(tmp_path, monkeypatch, fault):
    source = tmp_path / "video.mp4"
    source.write_bytes(b"private recording")
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    layout = tmp_path / "layout.json"
    _layout(layout)
    layout.with_suffix(".templates.json").write_text(json.dumps({
        "schema_version": "1.0", "anchors": {}, "readers": {},
    }))
    output = tmp_path / "experiment"
    class Service(FakeVideoService):
        def extract_frames(self, *args, **kwargs):
            from valorant_ai_coach.video import FrameSample
            frames = super().extract_frames(*args, **kwargs)
            if fault == "missing":
                frames.pop()
            elif fault == "outside":
                frames[0] = FrameSample(1.0, frames[0].path)
            elif fault == "duplicate":
                frames[1] = FrameSample(frames[0].time_sec, frames[1].path)
            elif fault == "resolution":
                assert cv2.imwrite(str(frames[0].path), np.zeros((50, 60, 3), np.uint8))
            return frames

    monkeypatch.setattr(experiment, "CachedVideoService", lambda *args: Service(_frames(count=32)))
    monkeypatch.setattr(experiment, "decoder_fingerprints", lambda _: ("probe", "frame"))
    monkeypatch.setattr(sys, "argv", [
        "diagnose", "--video", str(source), "--layout", str(layout),
        "--output", str(output), "--sampling-window", "2", "4", "--source-sha256", digest,
    ])
    if fault:
        with pytest.raises(ValueError):
            experiment.main()
        assert not (output / "diagnostics.json").exists()
        assert not list(output.glob("*.png"))
        return
    experiment.main()
    report = json.loads((output / "diagnostics.json").read_text())
    assert report["production_qualified"] is False
    assert report["identity_assets_generated"] is False
    assert report["sample_count"] == 32
    assert report["source_hash_verified_after_processing"] is True
    assert report["input_hashes_verified_after_processing"] is True
    assert set(report["input_sha256"]) == {
        "experiment_code", "baseline_code", "layout", "template_config",
    }
    assert all(len(value) == 64 for value in report["input_sha256"].values())
    assert all(2 <= frame["source_frame_pts"] < 4 for frame in report["frames"])
    assert len(report["training_indices"]) == len(report["holdout_indices"]) == 16
    assert not (output / "hud_layout.json").exists()
    assert not (output / "hud_layout.templates.json").exists()
    assert report["runtime_geometry_replay"]["sample_count"] == 32
    assert report["runtime_geometry_replay"]["production_qualified"] is False
    assert report["runtime_geometry_replay"]["temporal_geometry_retention"] is False
    assert set(report["synthetic_geometry_negative_controls"]) == {
        "flat_frame", "large_horizontal_wrap_shift",
    }
    assert str(tmp_path) not in json.dumps(report)


def test_runtime_geometry_replay_needs_three_fresh_inliers_and_rejects_negatives(tmp_path):
    """Actual runtime matcher, not fixed-ROI scores or supplied anchor boxes."""
    image = np.full((300, 480, 3), 100, np.uint8)
    regions, specs = {}, {}
    rng = np.random.default_rng(14)
    for name, (x, y) in zip(
        ("round_timer", "top_match_bar", "player_hp_armor"),
        ((20, 20), (180, 20), (340, 240)), strict=True,
    ):
        pixels = rng.integers(30, 230, (40, 80), dtype=np.uint8)
        image[y:y + 40, x:x + 80] = cv2.cvtColor(pixels, cv2.COLOR_GRAY2BGR)
        assert cv2.imwrite(str(tmp_path / f"{name}.png"), pixels)
        assert cv2.imwrite(str(tmp_path / f"{name}.mask.png"), np.full_like(pixels, 255))
        regions[name] = NormalizedRoi(x / 480, y / 300, 80 / 480, 40 / 300)
        specs[name] = {
            "template": f"{name}.png", "mask": f"{name}.mask.png", "threshold": .90,
            "search_region": [(x - 10) / 480, (y - 10) / 300,
                              (x + 90) / 480, (y + 50) / 300],
        }
    layout = HudLayout("3.0", True, (480, 300), regions, layout_format="v3")
    profile = HudTemplateProfile(tmp_path / "never_written.json", {
        "schema_version": "1.0", "anchors": specs,
    })
    replay = experiment.replay_geometry([
        image, np.full_like(image, 70), np.roll(image, 96, axis=1),
    ], layout, profile)
    assert replay["fresh_geometry_success_count"] == 1
    assert replay["frames"][0]["fresh_geometry_success"] is True
    assert replay["frames"][0]["median_position_error_norm"] == pytest.approx(0)
    assert all(not row["fresh_geometry_success"] for row in replay["frames"][1:])
    # A prior successful frame cannot make a subsequent two-anchor frame valid.
    two = image.copy()
    two[240:280, 340:420] = 100
    replay = experiment.replay_geometry([image, two], layout, profile)
    assert replay["fresh_geometry_success_count"] == 1
    assert len(replay["frames"][1]["accepted_anchors"]) == 2
    assert "insufficient_anchors" in replay["frames"][1]["reasons"]
    assert replay["production_qualified"] is False
    assert not (tmp_path / "never_written.json").exists()
    # Three high NCC matches are insufficient when only two positions agree.
    displaced = image.copy()
    displaced[240:280, 340:420] = 100
    displaced[240:280, 250:330] = image[240:280, 340:420]
    wide_specs = {name: {**spec, "search_region": [0, 0, 1, 1]}
                  for name, spec in specs.items()}
    wide_profile = HudTemplateProfile(tmp_path / "never_written.json", {
        "schema_version": "1.0", "anchors": wide_specs,
    })
    replay = experiment.replay_geometry([displaced], layout, wide_profile)
    assert len(replay["frames"][0]["accepted_anchors"]) == 3
    assert replay["fresh_geometry_success_count"] == 0
    assert "insufficient_anchor_inliers" in replay["frames"][0]["reasons"]

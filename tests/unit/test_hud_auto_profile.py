import json
from dataclasses import replace
from pathlib import Path

import cv2
import numpy as np
import pytest
from test_hud_temporal_calibration import FakeVideoService, _frames, _layout

from valorant_ai_coach.hud.calibrate import create_anchor_profile
from valorant_ai_coach.hud.calibrate_profile import (
    _bundle_assets,
    _panel_neighborhood_times,
    _validate_identity_assets,
    clear_reference,
    create_profile,
    structure_reference,
)
from valorant_ai_coach.hud.identity import STRUCTURES, live_identity
from valorant_ai_coach.hud.layout import HudLayout
from valorant_ai_coach.hud.templates import HudTemplateProfile
from valorant_ai_coach.video.service import FrameSample


def test_panel_neighborhood_plan_uses_training_only_and_freezes_split():
    times = [10.0, 20.0, 30.0, 40.0]
    samples = [
        {"sample_index": 0, "training": True, "all_components": True},
        {"sample_index": 1, "training": False, "all_components": True},
        {"sample_index": 2, "training": True, "all_components": False},
        {"sample_index": 3, "training": True, "all_components": True},
    ]
    stats = {"samples": samples, "cluster_count": 0, "holdout_rejected": 0}
    plan = _panel_neighborhood_times(times, 60.0, stats)
    assert plan == [8.5, 9.0, 9.5, 10.5, 11.0, 11.5]
    assert not set(plan) & set(times)
    assert len(plan[::2]) == len(plan[1::2]) == 3
    samples[1]["all_components"] = False
    assert _panel_neighborhood_times(times, 60.0, stats) == plan
    assert _panel_neighborhood_times(times, 60.0, {**stats, "holdout_rejected": 1}) == []
    assert _panel_neighborhood_times(times, 60.0, {**stats, "cluster_count": 1}) == []
    assert _panel_neighborhood_times(times[:-1], 60.0, stats) == []


def test_panel_neighborhood_plan_excludes_collisions_and_caps_sampling():
    times = [float(i * 10 + 10) for i in range(32)]
    stats = {"samples": [
        {"sample_index": i, "training": True, "all_components": True}
        for i in range(0, 32, 2)
    ]}
    plan = _panel_neighborhood_times(times, 400.0, stats)
    assert len(plan) == len(set(plan)) == 48
    assert max(plan) < times[16]
    # Both members of a pair are omitted when one aliases an original sample.
    short = _panel_neighborhood_times([1.0, 1.5], 2.0, {
        "samples": [{"sample_index": 0, "training": True, "all_components": True}]
    })
    assert short == []


def test_bundled_assets_keep_bytes_and_load_after_source_directory_moves(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    asset = source / "参照.png"
    ok, encoded = cv2.imencode(".png", _frames()[0][36:162, 19:147])
    assert ok
    asset.write_bytes(encoded.tobytes())
    original = asset.read_bytes()
    stage = tmp_path / "profile"
    stage.mkdir()
    raw = {
        "schema_version": "1.0",
        "anchors": {"round_timer": {"template": str(asset), "threshold": 0.94}},
        "readers": {"round_timer": {"templates": {"0": [str(asset)]}}},
        "signals": {"marker": {"roi": "round_timer", "template": str(asset)}},
    }
    bundled = _bundle_assets(raw, stage)
    reference = bundled["anchors"]["round_timer"]["template"]
    assert not Path(reference).is_absolute()
    assert bundled["readers"]["round_timer"]["templates"]["0"] == [reference]
    assert bundled["signals"]["marker"]["template"] == reference
    assert bundled["anchors"]["round_timer"]["threshold"] == 0.94
    assert (stage / reference).read_bytes() == original
    source.rename(tmp_path / "moved-source")
    stage.rename(tmp_path / "移動-profile")
    profile = HudTemplateProfile(tmp_path / "移動-profile/profile.json", bundled)
    assert not profile.reader_diagnostics
    assert profile.load_template("round_timer", reference).path.read_bytes() == original


def test_ready_requires_production_readable_assets_not_generation_status(tmp_path):
    diagnostics = {
        "spectator_method": "compound",
        "references": {role: {"status": "generated"} for role in (*STRUCTURES, "spectator_panel")},
    }
    raw = {"schema_version": "1.0", "signals": {
        role: {"roi": "abilities", "template": "missing.png", "threshold": 0.9}
        for role in STRUCTURES
    }, "spectator_panel_detector": {"version": 2, "template": "missing.png"}}
    _validate_identity_assets(raw, tmp_path, diagnostics)
    assert diagnostics["identity_reference_ready"] is False
    for row in diagnostics["references"].values():
        assert row["status"] == "insufficient_evidence"
        assert row["reason"] == "reference_load_failed"
        assert row["rejection_stage"] == "profile_load"


def test_nested_digit_bank_assets_participate_in_profile_fingerprint(tmp_path):
    layout = tmp_path / "layout.json"
    layout.write_text("{}")
    sidecar = tmp_path / "profile.json"
    first, second = tmp_path / "first.png", tmp_path / "second.png"
    first.write_bytes(b"first reference")
    second.write_bytes(b"second reference")
    raw = {"schema_version": "1.0", "readers": {
        "player_hp_armor": {"templates": {"0": [first.name, second.name]}}
    }}
    sidecar.write_text(json.dumps(raw))
    profile = HudTemplateProfile(sidecar, raw)
    assert set(profile.asset_paths) == {Path(first.name), Path(second.name)}
    before = profile.fingerprint(layout)
    second.write_bytes(b"changed second reference")
    assert profile.fingerprint(layout) != before


def inputs(tmp_path, panel_images):
    layout = tmp_path / "base.json"
    _layout(layout)
    raw = json.loads(layout.read_text())
    raw["rois"]["ammo_current_weapon"] = {"norm": [0.03, 0.60, 0.23, 0.95], "px": None}
    raw["rois"]["spectated_player_panel"] = {"norm": [0.30, 0.60, 0.55, 0.95], "px": None}
    layout.write_text(json.dumps(raw))
    frames = _frames(changing=True, count=32)
    hud = HudLayout.load(layout)
    for index, frame in enumerate(frames):
        x1, y1, x2, y2 = hud.normalized_roi("ammo_current_weapon").pixel_bounds(640, 360)
        frame[y1:y2, x1:x2] = frame[36 : 36 + y2 - y1, 19 : 19 + x2 - x1]
        x1, y1, x2, y2 = hud.normalized_roi("spectated_player_panel").pixel_bounds(640, 360)
        panel, scene = panel_images(x2 - x1, y2 - y1, index % 8)
        frame[y1:y2, x1:x2] = panel if index % 4 >= 2 else scene
    return layout, frames


@pytest.mark.parametrize("fault", ["duplicate", "missing", "resolution"])
def test_panel_resampling_rejects_unusable_native_observations(
    tmp_path, panel_images, monkeypatch, fault,
):
    import valorant_ai_coach.hud.calibrate_profile as generator

    layout, frames = inputs(tmp_path, panel_images)
    base = create_anchor_profile(layout, frames[0], tmp_path / "seed")

    def geometry(_video, _layout, stage, **kwargs):
        stage.mkdir()
        profile = HudTemplateProfile.load(base.with_suffix(".templates.json"))
        raw = generator._localize_assets(profile.raw, base.parent)
        selected = stage / "hud_layout.json"
        selected.write_bytes(base.read_bytes())
        selected.with_suffix(".templates.json").write_text(json.dumps(raw))
        return selected

    proposal_calls = []

    def proposals(crops, stats):
        proposal_calls.append(len(crops))
        stats.update(training_count=16, holdout_count=16, candidate_count=1,
                     cluster_count=0, holdout_rejected=0, samples=[{
                         "sample_index": 16, "training": True, "all_components": True,
                     }])
        return None

    class FaultyService(FakeVideoService):
        def probe(self, path):
            return replace(super().probe(path), duration_sec=100.0)

        def extract_frames(self, video, timestamps, output_dir, **kwargs):
            result = super().extract_frames(video, timestamps, output_dir, **kwargs)
            if output_dir.name == "identity_frames":
                self.original = result
            else:
                if fault == "duplicate":
                    result[0] = FrameSample(self.original[0].time_sec, result[0].path)
                elif fault == "missing":
                    result.pop()
                else:
                    assert cv2.imwrite(str(result[0].path), np.zeros((10, 10, 3), np.uint8))
            return result

    monkeypatch.setattr(generator, "create_temporal_profile", geometry)
    monkeypatch.setattr(generator, "generate_panel_reference", proposals)
    generated = create_profile(
        Path("private.mp4"), base, tmp_path / "candidate",
        video_service=FaultyService(frames), value_invariant_only=True, compound_spectator=True,
    )
    profile = HudTemplateProfile.load(generated.with_suffix(".templates.json"))
    diagnostics = profile.raw["automatic_identity_generation"]
    panel = diagnostics["references"]["spectator_panel"]
    assert panel["status"] == "insufficient_evidence"
    assert panel["sampling"]["accepted_count"] == 0
    assert panel["sampling"]["reason"] == (
        "panel_frame_resolution_invalid" if fault == "resolution"
        else "distinct_panel_frames_insufficient"
    )
    assert proposal_calls == [32]
    assert not diagnostics["identity_reference_ready"]
    assert "spectator_panel_detector" not in profile.raw


def test_generated_layout_consumed_without_json_edits(tmp_path, panel_images):
    layout, frames = inputs(tmp_path, panel_images)
    original = layout.read_bytes()
    out = tmp_path / "local"
    generated = create_profile(
        Path("private.mp4"), layout, out, video_service=FakeVideoService(frames)
    )
    assert generated.name == "hud_layout.json"
    profile = HudTemplateProfile.load(generated.with_suffix(".templates.json"))
    assert not profile.reader_diagnostics
    signals = profile.detect_signals(frames[1], HudLayout.load(generated))
    assert live_identity(signals, geometry_valid=True).live
    assert not live_identity(signals, geometry_valid=False).live
    assert all(
        "mask" not in profile.raw["signals"][name]
        for name in STRUCTURES
        if name != "weapon_ammo_structure"
    )
    # The new weapon mask is identity-only, never a geometry mask or asset.
    weapon_mask = profile.raw["signals"]["weapon_ammo_structure"]["mask"]
    geometry_assets = {
        spec[key]
        for spec in profile.raw["anchors"].values()
        for key in ("template", "mask")
        if key in spec
    }
    assert weapon_mask not in geometry_assets
    assert all(
        profile.raw["signals"][name]["template"].startswith("identity/") for name in STRUCTURES
    )
    stats = (out / "profile_diagnostics.json").read_text()
    assert "private.mp4" not in stats and str(tmp_path) not in stats
    assert layout.read_bytes() == original
    # A newly visible panel must not retain live identity.
    blocked = frames[1].copy()
    x1, y1, x2, y2 = (
        HudLayout.load(generated).normalized_roi("spectated_player_panel").pixel_bounds(640, 360)
    )
    cv2.putText(
        blocked, "PLAYER", (x1 + 5, y1 + 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2
    )
    assert not live_identity(
        profile.detect_signals(blocked, HudLayout.load(generated)), geometry_valid=True
    ).live
    with pytest.raises(FileExistsError):
        create_profile(Path("private.mp4"), layout, out, video_service=FakeVideoService(frames))


def test_structure_requires_disjoint_holdout_support():
    crops = []
    for index in range(32):
        image = np.zeros((120, 130, 3), np.uint8)
        if index % 2 == 0:
            cv2.rectangle(image, (4, 4), (115, 115), (220, 220, 220), 2)
        crops.append(image)
    assert structure_reference(crops) is None


def test_value_invariant_only_refuses_unconfigured_roles_without_fallback(tmp_path, panel_images):
    layout, frames = inputs(tmp_path, panel_images)
    result = create_profile(
        Path("private.mp4"), layout, tmp_path / "strict",
        video_service=FakeVideoService(frames),
        value_invariant_only=True, compound_spectator=True,
    )
    profile = HudTemplateProfile.load(result.with_suffix(".templates.json"))
    generation = profile.raw["automatic_identity_generation"]
    assert generation["identity_reference_ready"] is False
    assert generation["generation_policy"] == "value_invariant_only"
    assert generation["spectator_method"] == "compound"
    assert "spectator_icon_detector" not in profile.raw
    assert "spectator_panel_detector" in profile.raw
    for name in STRUCTURES:
        assert name not in profile.raw["signals"]
        assert generation["references"][name]["status"] == "insufficient_evidence"
        assert generation["references"][name]["reason"] == "value_invariant_structure_unconfigured"
    assert not live_identity(profile.detect_signals(frames[1], HudLayout.load(result)),
                             geometry_valid=True).live


@pytest.mark.parametrize("copy_mask", [False, True])
def test_inherited_geometry_mask_cannot_be_weapon_identity(tmp_path, panel_images, copy_mask):
    layout, frames = inputs(tmp_path, panel_images)
    base = create_profile(
        Path("private.mp4"), layout, tmp_path / "base", video_service=FakeVideoService(frames)
    )
    sidecar = base.with_suffix(".templates.json")
    raw = json.loads(sidecar.read_text())
    mask = raw["signals"]["weapon_ammo_structure"]["mask"]
    raw["anchors"]["round_timer"]["mask"] = mask
    if copy_mask:
        copy = sidecar.parent / "identity" / "copied.mask.png"
        copy.write_bytes((sidecar.parent / mask).read_bytes())
        raw["signals"]["weapon_ammo_structure"]["mask"] = "identity/copied.mask.png"
    sidecar.write_text(json.dumps(raw))
    generated = create_profile(
        Path("private.mp4"), base, tmp_path / "next", video_service=FakeVideoService(frames)
    )
    after = HudTemplateProfile.load(generated.with_suffix(".templates.json"))
    assert (
        after.raw["automatic_identity_generation"]["references"]["weapon_ammo_structure"]["status"]
        == "generated"
    )


@pytest.mark.parametrize("value", [0, 255])
def test_black_white_frames_are_not_spectator_absence(value):
    assert clear_reference([np.full((40, 60), value, np.uint8)] * 32) is None


def test_textured_panel_is_not_automatically_labelled_clear():
    frame = np.full((40, 120), 65, np.uint8)
    cv2.putText(frame, "PLAYER", (2, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.5, 255, 2)
    assert clear_reference([frame] * 32) is None


def test_missing_identity_publishes_runnable_but_unknown_profile(tmp_path, panel_images):
    layout, frames = inputs(tmp_path, panel_images)
    hud = HudLayout.load(layout)
    x1, y1, x2, y2 = hud.normalized_roi("ammo_current_weapon").pixel_bounds(640, 360)
    for frame in frames:
        frame[y1:y2, x1:x2] = 0
    generated = create_profile(
        Path("private.mp4"), layout, tmp_path / "out", video_service=FakeVideoService(frames)
    )
    profile = HudTemplateProfile.load(generated.with_suffix(".templates.json"))
    assert (
        profile.raw["automatic_identity_generation"]["references"]["weapon_ammo_structure"][
            "status"
        ]
        == "insufficient_evidence"
    )
    assert not live_identity(profile.detect_signals(frames[0], hud), geometry_valid=True).live


def test_invalid_inherited_identity_is_regenerated_and_readers_preserved(tmp_path, panel_images):
    layout, frames = inputs(tmp_path, panel_images)
    base = {
        "schema_version": "1.0",
        "readers": {"hp": {"kind": "digits"}},
        "signals": {"hp_hud_structure": {"roi": "player_hp_armor", "template": "missing.png"}},
    }
    sidecar = layout.with_suffix(".templates.json")
    sidecar.write_text(json.dumps(base))
    original = sidecar.read_bytes()
    generated = create_profile(
        Path("private.mp4"),
        layout,
        tmp_path / "日本語profile",
        video_service=FakeVideoService(frames),
    )
    profile = HudTemplateProfile.load(generated.with_suffix(".templates.json"))
    assert profile.raw["readers"] == base["readers"]
    assert (
        profile.raw["automatic_identity_generation"]["references"]["hp_hud_structure"]["status"]
        == "generated"
    )
    assert not profile.reader_diagnostics
    assert sidecar.read_bytes() == original


def test_legacy_clear_reference_cannot_override_unverified_panel(
    tmp_path, monkeypatch, panel_images
):
    from valorant_ai_coach.hud.readers import ReaderResult

    layout, frames = inputs(tmp_path, panel_images)
    generated = create_profile(
        Path("private.mp4"), layout, tmp_path / "out", video_service=FakeVideoService(frames)
    )
    profile = HudTemplateProfile.load(generated.with_suffix(".templates.json"))
    profile._panel_components = None
    # Existing configured presence detector returns ambiguous .5, not absence.
    template = profile._signal_templates["hp_hud_structure"][1]
    profile._signal_templates["spectated_player_panel"] = ("spectated_player_panel", template)
    frame = frames[0].copy()
    roi = HudLayout.load(generated).normalized_roi("spectated_player_panel")
    x1, y1, x2, y2 = roi.pixel_bounds(640, 360)
    frame[y1:y2:2, x1:x2] += 4  # Still within clear-reference tolerance, but non-flat.
    monkeypatch.setattr(
        "valorant_ai_coach.hud.templates._best_template_match",
        lambda *args: ReaderResult(None, 0.5, ("template_below_threshold",)),
    )
    signals = profile.detect_signals(frame, HudLayout.load(generated))
    assert signals["spectator_panel_absent"] is False


def test_regeneration_preserves_valid_panel_detector_without_new_positive_frames(
    tmp_path, panel_images
):
    layout, frames = inputs(tmp_path, panel_images)
    first = create_profile(
        Path("private.mp4"), layout, tmp_path / "first", video_service=FakeVideoService(frames)
    )
    before = HudTemplateProfile.load(first.with_suffix(".templates.json"))
    assert before.raw["automatic_identity_generation"]["identity_reference_ready"] is True
    x1, y1, x2, y2 = (
        HudLayout.load(first).normalized_roi("spectated_player_panel").pixel_bounds(640, 360)
    )
    negative = []
    for index, frame in enumerate(frames):
        frame = frame.copy()
        frame[y1:y2, x1:x2] = panel_images(x2 - x1, y2 - y1, index % 8)[1]
        negative.append(frame)
    source_bytes = first.with_suffix(".templates.json").read_bytes()
    second = create_profile(
        Path("private.mp4"), first, tmp_path / "second", video_service=FakeVideoService(negative)
    )
    after = HudTemplateProfile.load(second.with_suffix(".templates.json"))
    row = after.raw["automatic_identity_generation"]["references"]["spectator_panel"]
    assert row["status"] == "inherited"
    assert row["candidate_count"] == 0
    assert after.raw["automatic_identity_generation"]["identity_reference_ready"] is True
    assert np.array_equal(before._panel_components, after._panel_components)
    assert (
        after.detect_signals(negative[0], HudLayout.load(second))["spectator_panel_absent"] is True
    )
    assert after.detect_signals(frames[2], HudLayout.load(second))["spectated_player_panel"] is True
    assert first.with_suffix(".templates.json").read_bytes() == source_bytes


@pytest.mark.parametrize("copy_asset", [False, True])
def test_replaced_source_geometry_cannot_be_inherited_as_identity(
    tmp_path, panel_images, copy_asset
):
    layout, frames = inputs(tmp_path, panel_images)
    shot = (
        FakeVideoService(frames)
        .extract_frames(Path("private.mp4"), [0], tmp_path / "frame")[0]
        .path
    )
    base = create_anchor_profile(layout, shot, tmp_path / "base")
    sidecar = base.with_suffix(".templates.json")
    raw = json.loads(sidecar.read_text(encoding="utf-8"))
    old_anchor = sidecar.parent / raw["anchors"]["player_hp_armor"]["template"]
    asset = old_anchor
    if copy_asset:
        asset = sidecar.parent / "copied_anchor.png"
        asset.write_bytes(old_anchor.read_bytes())
    raw["signals"] = {
        "hp_hud_structure": {"roi": "player_hp_armor", "template": str(asset), "threshold": 0.90}
    }
    sidecar.write_text(json.dumps(raw))
    generated = create_profile(
        Path("private.mp4"), base, tmp_path / "generated", video_service=FakeVideoService(frames)
    )
    after = HudTemplateProfile.load(generated.with_suffix(".templates.json"))
    assert after.raw["automatic_identity_generation"]["geometry_mode"] == "generated"
    assert (
        after.raw["automatic_identity_generation"]["references"]["hp_hud_structure"]["status"]
        == "generated"
    )
    assert after.raw["signals"]["hp_hud_structure"]["template"].startswith("identity/")
    assert (
        after.resolve_asset(after.raw["signals"]["hp_hud_structure"]["template"]).read_bytes()
        != old_anchor.read_bytes()
    )

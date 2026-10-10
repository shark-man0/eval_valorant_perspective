import hashlib
import json
import sys
from pathlib import Path

import cv2
import numpy as np
import pytest
from test_scene_domain_bootstrap import source as source

from scripts.diagnostics import validate_scene_chain_cohort as runner
from scripts.diagnostics.scene_correspondence import sha256
from scripts.diagnostics.validate_scene_chain_cohort import (
    verify_bindings,
    verify_joint_options,
    verify_observer_profile,
    verify_ticks,
)


def test_native_coverage_rejects_skips_duplicates_and_isolated_frames():
    verify_ticks([59945, 60201, 60457])
    for ticks in ([], [59945], [59945, 60457], [59945, 59945], [60201, 59945]):
        with pytest.raises(ValueError, match="contiguous"):
            verify_ticks(ticks)


def test_file_binding_detects_mutation_and_requires_explicit_inputs(tmp_path: Path):
    source = tmp_path / "frozen.py"
    source.write_text("original")
    bindings = {str(source): sha256(source)}
    verify_bindings(bindings)
    source.write_text("changed")
    with pytest.raises(ValueError, match="changed"):
        verify_bindings(bindings)
    with pytest.raises(ValueError, match="nonempty"):
        verify_bindings({})


def test_optional_joint_audit_requires_frozen_code_and_strict_options():
    assert not verify_joint_options({}, {})
    paths = [
        Path("scripts/diagnostics") / name
        for name in ("scene_domain_ambiguity.py", "scene_joint_domains.py")
    ]
    paths.append(Path("src/valorant_ai_coach/hud/scene_domains.py"))
    bindings = {str(path): sha256(path) for path in paths}
    assert verify_joint_options({"audit_options": {"joint_domains": True}}, bindings)
    shared = "src/valorant_ai_coach/hud/scene_domains.py"
    for invalid in (None, "0" * 64):
        stale = dict(bindings)
        if invalid is None:
            stale.pop(shared)
        else:
            stale[shared] = invalid
        with pytest.raises(ValueError, match="shared scene engine"):
            verify_joint_options({"audit_options": {"joint_domains": True}}, stale)
    with pytest.raises(ValueError, match="frozen"):
        verify_joint_options({"audit_options": {"joint_domains": True}}, {})
    for options in ({"joint_domains": 1}, {"joint_domains": False}, {"threshold": 0.8}):
        with pytest.raises(ValueError, match="frozen optional"):
            verify_joint_options({"audit_options": options}, bindings)


def observer_reservation(source):
    _, profile, _ = source
    asset = profile.parent / "world.png"
    bindings = {str(p): sha256(p) for p in Path("scripts/diagnostics").glob("*.py")}
    shared = Path("src/valorant_ai_coach/hud/scene_domains.py")
    bindings[str(shared)] = sha256(shared)
    tracking = Path("src/valorant_ai_coach/hud/scene_tracking.py")
    bindings[str(tracking)] = sha256(tracking)
    episode = Path("src/valorant_ai_coach/hud/scene_episode.py")
    bindings[str(episode)] = sha256(episode)
    for name in ("scene_references.py", "scene_reference_matching.py"):
        common = Path("src/valorant_ai_coach/hud") / name
        bindings[str(common)] = sha256(common)
    bindings.update({str(profile): sha256(profile), str(asset): sha256(asset)})
    return {"observer_profile": str(profile), "excluded_native_pixel_sha256": []}, bindings


def test_observer_reservation_requires_profile_assets_code_and_decoded_exposure(source):
    freeze, bindings = observer_reservation(source)
    assert verify_observer_profile(freeze, bindings) == Path(freeze["observer_profile"])
    for omitted in (
        freeze["observer_profile"],
        str(Path(freeze["observer_profile"]).parent / "world.png"),
        "scripts/diagnostics/observed_scene_chain.py",
        "src/valorant_ai_coach/hud/scene_domains.py",
        "src/valorant_ai_coach/hud/scene_tracking.py",
        "src/valorant_ai_coach/hud/scene_episode.py",
        "src/valorant_ai_coach/hud/scene_references.py",
        "src/valorant_ai_coach/hud/scene_reference_matching.py",
    ):
        changed = dict(bindings)
        changed.pop(omitted)
        with pytest.raises(ValueError, match="frozen"):
            verify_observer_profile(freeze, changed)
    del freeze["excluded_native_pixel_sha256"]
    with pytest.raises(ValueError, match="exposure"):
        verify_observer_profile(freeze, bindings)


def test_observer_cannot_accept_hypothetical_seed_or_tracker_override(source):
    freeze, bindings = observer_reservation(source)
    for key in ("reviewed_seed_boxes_640x360", "tracker_options", "audit_options"):
        with pytest.raises(ValueError, match="configuration"):
            verify_observer_profile({**freeze, key: {}}, bindings)


@pytest.mark.parametrize("initial_match", [True, False])
@pytest.mark.parametrize("deferred", [False, True])
def test_native_runner_uses_observed_acquisition_and_never_reseeds(
    source, monkeypatch, initial_match, deferred
):
    freeze, bindings = observer_reservation(source)
    if deferred:
        freeze["observer_options"] = {"deferred_initialization": True}
    _, profile, _ = source
    native = cv2.imread(str(profile.parent / "world.png"))
    first = native if initial_match else np.zeros_like(native)
    images = [first, np.roll(native, 3, axis=1), np.roll(native, 6, axis=1)]
    freeze["excluded_native_pixel_sha256"] = [hashlib.sha256(first.tobytes()).hexdigest()]
    video = profile.parent / "source.mp4"
    video.write_bytes(b"mock decoder source")
    bindings[str(video)] = sha256(video)
    freeze.update(
        source_video=str(video),
        source_video_sha256=sha256(video),
        file_sha256=bindings,
        windows_sec=[[4.0, 4.1]],
        excluded_png_sha256=[],
    )
    reservation = profile.parent / "reservation.json"
    reservation.write_text(json.dumps(freeze))
    output = profile.parent / "report.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "cohort",
            "--reservation",
            str(reservation),
            "--output-dir",
            str(profile.parent / "decoded"),
            "--output",
            str(output),
        ],
    )
    monkeypatch.setattr(runner.shutil, "which", lambda name: name)
    monkeypatch.setattr(
        runner,
        "probe_json",
        lambda *args: {
            "streams": [
                {"width": 1920, "height": 1080, "r_frame_rate": "60/1", "time_base": "1/15360"}
            ],
            "format": {"duration": "10"},
        },
    )

    def extract(*args):
        directory = args[3]
        directory.mkdir()
        paths = []
        for index, image in enumerate(images):
            p = directory / f"frame_{index:06}.png"
            cv2.imwrite(str(p), image)
            paths.append(p)
        return paths, [61440, 61696, 61952]

    monkeypatch.setattr(runner, "extract_window", extract)
    runner.main()
    report = json.loads(output.read_text())
    window = report["windows"][0]
    assert window["supported_links_descriptive"] == (2 if initial_match else 1 if deferred else 0)
    assert window["known_native_pixel_overlaps"] == 1
    assert not report["qualification_created"]
    assert report["new_runtime_events"] == 0
    if deferred:
        assert report["observer_options"] == {"deferred_initialization": True}
        assert window["observed_seed_pts_ticks"] == [61440 if initial_match else 61696]
        assert window["pending_initialization_frames"] == (0 if initial_match else 1)
        assert "previous_source_pts_ticks" not in window["rows"][0]["image_result"]
    else:
        assert "observer_options" not in report
        assert "observed_seed_pts_ticks" not in window
    if not initial_match and not deferred:
        assert window["initialization_reason"] == "image_supported_initialization_unavailable"
        assert all(p["image_result"]["reason"] == "episode_terminated" for p in window["rows"][1:])


@pytest.mark.parametrize(
    "options",
    [
        None,
        {},
        {"deferred_initialization": 1},
        {"deferred_initialization": "true"},
        {"threshold": 0.8},
    ],
)
def test_observer_options_require_exact_frozen_boolean(options, source):
    freeze, bindings = observer_reservation(source)
    with pytest.raises(ValueError, match="boolean"):
        verify_observer_profile({**freeze, "observer_options": options}, bindings)


def test_observer_option_cannot_be_ignored_on_legacy_tracker():
    with pytest.raises(ValueError, match="boolean"):
        verify_observer_profile({"observer_options": {"deferred_initialization": True}}, {})

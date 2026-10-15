"""Synthetic transport and geometry policy, never real reader qualification."""

from copy import deepcopy
from dataclasses import replace
from fractions import Fraction

import pytest

from tests.unit.test_native_assured_start import assured
from tests.unit.test_native_calibration_prefix import case as case
from valorant_ai_coach.hud.global_lifecycle import (
    GlobalLifecycleQualification,
    global_recognizer_fingerprint,
)
from valorant_ai_coach.hud.native_assured_start import replay_assured_starts
from valorant_ai_coach.hud.native_event_merge import validated_native_boundaries
from valorant_ai_coach.hud.native_geometry_initialization import (
    NativeGeometryInitialization,
    attest_geometry_initialization,
)
from valorant_ai_coach.hud.unedited_input import UneditedInputContract
from valorant_ai_coach.video.native import NativeSourceFrame


def qualified(case, monkeypatch):
    analyzer, _, frames, contract_path, *_ = case
    q = GlobalLifecycleQualification(
        analyzer._base_fingerprint(),
        "b" * 64,
        frozenset({"timer", "purchase_phase", "ui_transition"}),
        global_recognizer_fingerprint(),
    )
    # A synthetic admission isolates the real configured geometry/value path.
    monkeypatch.setattr(
        "valorant_ai_coach.hud.native_assured_start.current_assured_qualification",
        lambda *args: q,
    )

    def run(prefix=True):
        return analyzer.observe_qualified_unedited_native_start_frames(
            frames,
            native_step_ticks=256,
            input_contract_path=contract_path,
            **({"calibration_prefix": case[1]} if prefix else {}),
        )

    return run, q


def test_qualified_prefix_is_geometry_only_and_default_cold_entry_unchanged(case, monkeypatch):
    run, q = qualified(case, monkeypatch)
    cold = run(False)
    assert cold.geometry_initialization is None
    assert not case[4]
    assert not cold.hud_events
    warm = run()
    assert case[4] == [61, 62]
    assert len(warm.source_rows) == 2
    assert warm.geometry_initialization.prefix == case[1]
    assert warm.geometry_initialization.first == case[2][0]
    assert warm.hud_events == ()
    assert all(row["system_observation"]["values"]["hp"] is None for row in warm.source_rows)
    assert all(row["source_epoch"] == case[2][0].source_epoch for row in warm.source_rows)
    assert validated_native_boundaries(warm, q, "a" * 64) == ()
    assert case[0].last_calibration_diagnostics["counts"]["effective_geometry_success"] == 2


@pytest.mark.parametrize(
    "change",
    [
        "bytes",
        "missing",
        "contract",
        "binding",
        "reference_epoch",
        "window_epoch",
        "fingerprint",
        "row_binding",
        "removed",
    ],
)
def test_reference_and_context_rechecked_even_without_events(case, monkeypatch, change):
    run, q = qualified(case, monkeypatch)
    native = run()
    init = native.geometry_initialization
    if change == "bytes":
        case[1].path.write_bytes(case[1].path.read_bytes() + b"changed")
    elif change == "missing":
        case[1].path.unlink()
    elif change == "contract":
        case[3].write_bytes(case[3].read_bytes() + b" ")
    elif change == "binding":
        native = replace(native, geometry_initialization=replace(init, context_json="{}"))
    elif change == "reference_epoch":
        native = replace(
            native,
            geometry_initialization=replace(
                init,
                prefix=replace(init.prefix, source_epoch="foreign-reference"),
            ),
        )
    elif change == "window_epoch":
        native = replace(
            native,
            geometry_initialization=replace(
                init,
                first=replace(init.first, source_epoch="foreign-window"),
            ),
        )
    elif change in {"fingerprint", "row_binding"}:
        native = deepcopy(native)
        key = "input_fingerprint" if change == "fingerprint" else "geometry_initialization_sha256"
        native.source_rows[0][key] = "c" * 64
    else:
        native = replace(native, geometry_initialization=None)
    with pytest.raises((ValueError, RuntimeError, OSError)):
        validated_native_boundaries(native, q, "a" * 64)


@pytest.mark.parametrize(
    "change",
    ["video", "timebase", "dimensions", "future", "negative", "bool_pts", "epoch", "bytes"],
)
def test_invalid_qualified_reference_never_reaches_value_reader(case, monkeypatch, change):
    run, _ = qualified(case, monkeypatch)
    analyzer, prefix, frames, contract, calls, _ = case
    changes = {
        "video": {"source_video_sha256": "d" * 64},
        "timebase": {"time_base": Fraction(1, 60)},
        "dimensions": {"width": 641},
        "future": {"pts_ticks": frames[0].pts_ticks},
        "negative": {"pts_ticks": -1},
        "bool_pts": {"pts_ticks": True},
        "epoch": {"source_epoch": ""},
    }
    if change == "bytes":
        prefix.path.write_bytes(prefix.path.read_bytes() + b"changed")
    else:
        prefix = replace(prefix, **changes[change])
    with pytest.raises((ValueError, RuntimeError)):
        analyzer.observe_qualified_unedited_native_start_frames(
            frames,
            native_step_ticks=256,
            input_contract_path=contract,
            calibration_prefix=prefix,
        )
    assert not calls


def bound_synthetic_event(case, tmp_path):
    _, _, _, original = assured(tmp_path)
    rows = deepcopy(original.source_rows)
    for row in rows:
        row["source_pts_ticks"] += 1000
        row["source_pts_sec"] = float(row["source_pts_ticks"] * Fraction(row["source_time_base"]))
        row["system_observation"]["time_sec"] = row["source_pts_sec"]
    first_row = rows[0]
    prefix = replace(
        case[1],
        pts_ticks=0,
        time_base=Fraction(first_row["source_time_base"]),
        source_video_sha256=first_row["source_video_sha256"],
    )
    first = NativeSourceFrame(
        prefix.path,
        first_row["source_pts_ticks"],
        prefix.time_base,
        first_row["source_epoch"],
        prefix.source_video_sha256,
        prefix.encoded_sha256,
        first_row["source_pixel_sha256"],
        prefix.width,
        prefix.height,
    )
    init = NativeGeometryInitialization.bind(
        prefix,
        first,
        original.qualification,
        original.unedited_input_contract,
        "e" * 64,
    )
    for row in rows:
        row["input_fingerprint"] = init.observation_fingerprint
        row["geometry_initialization_sha256"] = init.observation_fingerprint
    events, diagnostics = replay_assured_starts(
        rows,
        original.qualification,
        original.unedited_input_contract,
    )
    events = attest_geometry_initialization(
        events,
        init,
        rows,
        original.qualification,
        original.unedited_input_contract,
    )
    return replace(
        original,
        source_rows=rows,
        observations=tuple(r["system_observation"] for r in rows),
        hud_events=events,
        diagnostics=diagnostics,
        geometry_initialization=init,
    )


def test_event_provenance_binds_geometry_reference_without_replacing_boundary(case, tmp_path):
    native = bound_synthetic_event(case, tmp_path / "event")
    events = validated_native_boundaries(
        native,
        native.qualification,
        native.unedited_input_contract.source_video_sha256,
    )
    assert len(events) == 1
    assert events[0]["time_sec"] == 1.12
    proof = events[0]["attributes"]["evidence_provenance"]
    assert proof["source_epoch"] == native.source_rows[0]["source_epoch"]
    assert proof["geometry_initialization"]["reference"]["source_epoch"] == case[1].source_epoch
    assert proof["continuity_segment"] == 0
    assert proof["geometry_initialization"]["scope"] == "geometry_only_reference_v1"
    assert not any(r["source_pts_ticks"] == 0 for r in native.source_rows)
    changed = deepcopy(native)
    changed.hud_events[0]["attributes"]["evidence_provenance"]["geometry_initialization"].clear()
    with pytest.raises(ValueError, match="boundary differs"):
        validated_native_boundaries(
            changed,
            changed.qualification,
            changed.unedited_input_contract.source_video_sha256,
        )


@pytest.mark.parametrize("component", ["qualification", "profile", "code", "producer"])
def test_binding_rejects_changed_qualification_profile_code_or_producer(
    case,
    monkeypatch,
    component,
):
    run, q = qualified(case, monkeypatch)
    native = run()
    init = native.geometry_initialization
    contract = UneditedInputContract.load(case[3], source_video_sha256="a" * 64)
    changes = {
        "qualification": {"report_sha256": "f" * 64},
        "profile": {"profile_fingerprint": "f" * 64},
        "code": {"recognizer_fingerprint": "f" * 64},
    }
    q = replace(q, **changes[component]) if component != "producer" else q
    kwargs = {"producer_fingerprint": "f" * 64} if component == "producer" else {}
    with pytest.raises(ValueError):
        init.verify(q, contract, native.source_rows[0], **kwargs)


def test_prefix_cannot_repair_gap_in_current_epoch(case, monkeypatch):
    run, _ = qualified(case, monkeypatch)
    case[2][1] = replace(case[2][1], pts_ticks=case[2][1].pts_ticks + 256)
    with pytest.raises(ValueError, match="contiguous"):
        run()
    assert not case[4]


def test_current_geometry_contradiction_never_borrows_reference(case, monkeypatch):
    from valorant_ai_coach.hud.layout import NormalizedRoi

    run, _ = qualified(case, monkeypatch)
    analyzer = case[0]
    detect = analyzer.template_profile.detect_anchors

    def shifted(image, layout):
        anchors, scores, notes = detect(image, layout)
        if int(image[180, 320, 0]) != 60:
            anchors = {
                name: NormalizedRoi(roi.x + 0.06, roi.y, roi.width, roi.height)
                for name in layout.calibration_policy["required_anchors"]
                for roi in [layout.normalized_roi(name)]
            }
        return anchors, scores, notes

    monkeypatch.setattr(analyzer.template_profile, "detect_anchors", shifted)
    native = run()
    assert case[4] == []
    assert not native.hud_events
    assert all(
        r["system_observation"]["values"]["round_time_remaining_sec"] is None
        for r in native.source_rows
    )
    assert analyzer.last_calibration_diagnostics["counts"]["effective_geometry_success"] == 0


def test_bad_reference_anchors_cannot_initialize_qualified_readers(case, monkeypatch):
    from valorant_ai_coach.hud.analyzers import HudNotCalibratedError

    run, _ = qualified(case, monkeypatch)
    monkeypatch.setattr(case[0].template_profile, "detect_anchors", lambda *a: ({}, {}, ()))
    with pytest.raises(HudNotCalibratedError, match="prefix"):
        run()
    assert not case[4]


@pytest.mark.parametrize("which", ["prefix", "contract"])
def test_mutation_during_qualified_observation_withholds_entire_result(case, monkeypatch, which):
    from valorant_ai_coach.hud.readers import ReaderResult

    run, _ = qualified(case, monkeypatch)

    class MutatingTimer:
        def read(self, image, roi):
            path = case[1].path if which == "prefix" else case[3]
            path.write_bytes(path.read_bytes() + b"changed")
            return ReaderResult("0:20", 0.95, ("unit_timer",))

    case[0].readers["round_timer"] = MutatingTimer()
    with pytest.raises((ValueError, RuntimeError)):
        run()


def test_reference_never_enters_phase_or_value_scan(case, monkeypatch):
    run, _ = qualified(case, monkeypatch)
    original = case[0].template_profile.detect_signals
    phase_images = []

    def detect(image, *args, **kwargs):
        color = int(image[180, 320, 0])
        assert color != 60
        phase_images.append(color)
        return original(image, *args, **kwargs)

    monkeypatch.setattr(case[0].template_profile, "detect_signals", detect)
    native = run()
    assert phase_images == [61, 62]
    assert case[4] == [61, 62]
    assert [r["source_pts_ticks"] for r in native.source_rows] == [63017, 63273]


def test_geometry_reference_does_not_hide_current_epoch_source_cut(case, tmp_path):
    from valorant_ai_coach.hud.native_event_merge import native_source_breaks

    native = bound_synthetic_event(case, tmp_path / "event-cut")
    rows = deepcopy(native.source_rows)
    rows[-1]["source_pixel_sha256"] = rows[-2]["source_pixel_sha256"]
    events, diagnostics = replay_assured_starts(
        rows,
        native.qualification,
        native.unedited_input_contract,
    )
    events = attest_geometry_initialization(
        events,
        native.geometry_initialization,
        rows,
        native.qualification,
        native.unedited_input_contract,
    )
    native = replace(native, source_rows=rows, hud_events=events, diagnostics=diagnostics)
    cuts = native_source_breaks(native)
    assert cuts == (rows[-1]["source_pts_sec"],)
    with pytest.raises(ValueError, match="segment-local"):
        validated_native_boundaries(
            native,
            native.qualification,
            native.unedited_input_contract.source_video_sha256,
        )
    assert (
        validated_native_boundaries(
            native,
            native.qualification,
            native.unedited_input_contract.source_video_sha256,
            continuity_breaks=cuts,
        )
        == events
    )


@pytest.mark.parametrize("mutate_during_processing", [False, True])
def test_application_package_trace_and_terminal_reference_guard(
    case,
    tmp_path,
    mutate_during_processing,
):
    from tests.e2e.trace_adapter import to_e2e_trace

    root = tmp_path / "application"
    native = bound_synthetic_event(case, root)
    processor, metadata, frames, _ = assured(root)
    metadata = replace(metadata, duration_sec=2)
    frames = [replace(f, time_sec=f.time_sec + 1) for f in frames]
    if mutate_during_processing:
        observe = processor.analyzer.observe_frames

        def observe_then_mutate(*args, **kwargs):
            result = observe(*args, **kwargs)
            case[1].path.write_bytes(case[1].path.read_bytes() + b"changed")
            return result

        processor.analyzer.observe_frames = observe_then_mutate
        with pytest.raises((ValueError, RuntimeError)):
            processor.process_frames(
                metadata, "geometry", frames, require_detected_rounds=False, native_lifecycle=native
            )
    else:
        result = processor.process_frames(
            metadata, "geometry", frames, require_detected_rounds=False, native_lifecycle=native
        )
        trace = to_e2e_trace(result)
        events = [e for e in trace["events"] if e["type"] == "round_start"]
        assert len(events) == 1
        assert events[0]["time_sec"] == 1.12
        assert events[0]["attributes"] == native.hud_events[0]["attributes"]
        assert len(result.round_packages) == 1

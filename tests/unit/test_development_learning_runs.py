from dataclasses import replace

import numpy as np
import pytest

from valorant_ai_coach.visual.development_learning_dataset import (
    FrameRecord,
    SourceAcceptance,
    Split,
)
from valorant_ai_coach.visual.development_learning_runs import (
    DevelopmentFeatureCache,
    DevelopmentTrialHistory,
    append_snapshot,
)


def frame():
    return FrameRecord(
        source_sha256="a" * 64,
        acquisition_id="epoch",
        native_epoch="epoch",
        native_pts_tick=1,
        native_time_base="1/60",
        frame_sha256="b" * 64,
        pixel_sha256="c" * 64,
        frame_size_px=(64, 64),
        roi_xywh=(0.0, 0.0, 25.0, 25.0),
        extraction_fingerprint="d" * 64,
        exposure_fingerprint="e" * 64,
        leakage_group_id="match",
        split=Split.DEVELOPMENT_TRAIN,
        source_acceptance=SourceAcceptance(True, "f" * 64, "0" * 64, "f" * 64, "0" * 64),
    )


def test_append_snapshot_exact_dedup_and_physical_group_not_inferred():
    f = frame()
    rows, receipt = append_snapshot([f], [f, replace(f, source_sha256="1" * 64)])
    assert len(rows) == 2 and receipt["exact_duplicates"] == 1
    assert receipt["new_source_hashes"] == 1
    assert receipt["new_declared_physical_groups"] == 0
    with pytest.raises(ValueError, match="crosses splits"):
        append_snapshot([f], [replace(f, split=Split.DEVELOPMENT_VALIDATION)])


def test_cache_reuses_only_identical_source_pixels_extraction_profile_features_and_build(tmp_path):
    cache = DevelopmentFeatureCache(tmp_path / "cache")
    f = frame()
    kwargs = dict(
        feature_fingerprint="1" * 64,
        profile_fingerprint="2" * 64,
        map_build="unverified",
        patch_sha256="3" * 64,
    )
    calls = []

    def compute():
        calls.append(1)
        return np.array([1.0, 2.0])

    first, hit, key = cache.get_or_compute(f, **kwargs, compute=compute)
    first[:] = 0
    again, hit, other = cache.get_or_compute(f, **kwargs, compute=compute)
    assert hit and other == key and again.tolist() == [1.0, 2.0] and len(calls) == 1
    for field, value in [
        ("source_sha256", "4" * 64),
        ("native_epoch", "other"),
        ("native_pts_tick", 2),
        ("pixel_sha256", "5" * 64),
        ("roi_xywh", (1.0, 1.0, 25.0, 25.0)),
        ("exposure_fingerprint", "6" * 64),
    ]:
        _, hit, other = cache.get_or_compute(
            replace(f, **{field: value}), **kwargs, compute=compute
        )
        assert not hit and other != key
    for field, value in [
        ("feature_fingerprint", "7" * 64),
        ("profile_fingerprint", "8" * 64),
        ("patch_sha256", "9" * 64),
        ("map_build", "other"),
    ]:
        _, hit, other = cache.get_or_compute(f, **{**kwargs, field: value}, compute=compute)
        assert not hit and other != key


def test_cache_rejects_corruption_instead_of_silently_reusing_or_recomputing(tmp_path):
    cache = DevelopmentFeatureCache(tmp_path / "cache")
    kwargs = dict(
        feature_fingerprint="1" * 64,
        profile_fingerprint="2" * 64,
        map_build="unverified",
        patch_sha256="3" * 64,
    )
    _, _, key = cache.get_or_compute(frame(), **kwargs, compute=lambda: np.ones(2))
    np.savez_compressed(
        cache.root / (key + ".npz"), features=np.zeros(2), key=np.zeros(64, np.uint8)
    )
    with pytest.raises(ValueError, match="identity mismatch"):
        cache.get_or_compute(
            frame(), **kwargs, compute=lambda: pytest.fail("recomputed corruption")
        )


def metrics(**changes):
    return {
        "TP": 7,
        "FP": 3,
        "FN": 4,
        "old_correct_lost": 0,
        "known_negative_matches": 0,
        "input_fingerprint": "a" * 64,
        **changes,
    }


def trial(tmp_path):
    history = DevelopmentTrialHistory(tmp_path / "history")
    args = dict(
        snapshot_fingerprint="1" * 64,
        code_fingerprint="2" * 64,
        previous_model_fingerprint="3" * 64,
        trial_name="synthetic",
    )
    key = history.begin(**args)
    assert history.begin(**args) == key
    return history, key


@pytest.mark.parametrize(
    "candidate",
    [metrics(TP=8, FN=3, input_fingerprint="b" * 64), metrics(TP=8, FN=4), metrics(TP=8, FN=None)],
)
def test_trial_cannot_claim_gain_with_changed_inputs_or_unknown_denominator(tmp_path, candidate):
    history, key = trial(tmp_path)
    result = history.finish(
        key, candidate_model_fingerprint="4" * 64, baseline=metrics(), candidate=candidate
    )
    assert result["development_gain"] is False
    assert result["status"] == "insufficient_evidence"


def test_trial_records_non_adoption_and_does_not_overwrite_rejected_history(tmp_path):
    history, key = trial(tmp_path)
    args = dict(
        candidate_model_fingerprint="4" * 64,
        baseline=metrics(),
        candidate=metrics(TP=8, FP=4, FN=3),
    )
    result = history.finish(key, **args)
    assert result["status"] == "rejected" and result["production_adoption"] is False
    assert result["retained_default_model_fingerprint"] == "3" * 64
    assert history.finish(key, **args) == result
    with pytest.raises(ValueError, match="immutable"):
        history.finish(key, **{**args, "candidate": metrics(TP=8, FP=3, FN=3)})


def test_interrupted_trial_can_finish_as_failed_without_adopting_a_model(tmp_path):
    history, key = trial(tmp_path)
    resumed = DevelopmentTrialHistory(history.root)
    result = resumed.finish(
        key,
        candidate_model_fingerprint="4" * 64,
        baseline={},
        candidate={},
        failure="training interrupted",
    )
    assert result["status"] == "failed" and not result["development_gain"]
    assert result["formal_outputs"] == 0

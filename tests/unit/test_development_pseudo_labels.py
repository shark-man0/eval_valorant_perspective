import hashlib
from dataclasses import replace

import numpy as np
import pytest

from valorant_ai_coach.visual.development_learning_dataset import (
    FrameLabel,
    FrameRecord,
    Label,
    LabelOrigin,
    SourceAcceptance,
    Split,
)
from valorant_ai_coach.visual.development_pseudo_labels import (
    AdmissionDiagnostic,
    AppearanceVote,
    PseudoPolicy,
    PseudoState,
    admit_candidate,
    consensus_label,
    generate_candidate,
    validation_diagnostic,
)
from valorant_ai_coach.visual.development_semisupervised import fit_semisupervised_centroids


def sha(s):
    return hashlib.sha256(str(s).encode("utf-8")).hexdigest()


def frame(i=0, split=Split.DEVELOPMENT_TRAIN):
    return FrameRecord(
        sha(f"source{i}"),
        f"acq{i}",
        f"epoch{i}",
        i,
        "1/60",
        sha(f"frame{i}"),
        sha(f"pixels{i}"),
        (640, 480),
        (20.0, 20.0, 25.0, 25.0),
        sha("extract"),
        sha("exposure"),
        f"match{i}",
        split,
        SourceAcceptance(True, sha("m"), sha("a"), sha("m"), sha("a")),
    )


def policy():
    return PseudoPolicy((sha("teacher1"), sha("teacher2")))


def votes(label=Label.PLAYER, distance=0.1, margin=0.1):
    return tuple(
        AppearanceVote(label, distance, margin, fp, "shared-backbone")
        for fp in policy().expected_generators
    )


def candidate(i=10, *, split=Split.DEVELOPMENT_TRAIN, v=None):
    return generate_candidate(
        frame(i, split),
        sha(f"patch{i}"),
        votes() if v is None else v,
        policy=policy(),
        generated_at="2026-10-27T00:00:00+00:00",
    )


def diagnostic(tp=4, fp=0):
    return AdmissionDiagnostic(Label.PLAYER, tp, fp, sha("human-validation"), policy().fingerprint)


def admitted(i=10):
    return admit_candidate(candidate(i), policy=policy(), diagnostic=diagnostic())


def human_data():
    rows = [frame(i) for i in range(4)]
    labels = [
        FrameLabel(r.frame_sha256, c, LabelOrigin.HUMAN_CONFIRMED, r.roi_xywh)
        for r, c in zip(
            rows, [Label.PLAYER, Label.DEATH_MARKER, Label.UI, Label.BACKGROUND], strict=True
        )
    ]
    return np.eye(4, dtype=np.float32), rows, labels


def test_correlated_consensus_is_only_a_candidate_not_human_or_identity():
    r = candidate()
    assert r.state is PseudoState.PSEUDO_CANDIDATE
    assert len({v.correlation_group for v in r.votes}) == 1
    assert r.ownership == "UNKNOWN" and r.formal_outputs == 0
    with pytest.raises(ValueError, match="HUMAN_CONFIRMED"):
        replace(r, state=PseudoState.HUMAN_CONFIRMED).validate()


@pytest.mark.parametrize("split", [Split.DEVELOPMENT_VALIDATION, Split.DEVELOPMENT_FROZEN_TEST])
def test_evaluation_roles_cannot_receive_pseudo_labels(split):
    with pytest.raises(ValueError):
        candidate(split=split)


def test_ssl_candidate_does_not_change_role_for_semantic_training():
    r = admit_candidate(candidate(split=Split.SSL_TRAIN), policy=policy(), diagnostic=diagnostic())
    assert r.state is PseudoState.PSEUDO_CANDIDATE
    assert "semantic_training_split_disallowed" in r.reasons


@pytest.mark.parametrize("label", [Label.DEATH_MARKER, Label.UI, Label.BACKGROUND])
def test_unsupported_pseudo_classes_are_not_admitted(label):
    d = replace(diagnostic(), label=label)
    r = admit_candidate(candidate(v=votes(label)), policy=policy(), diagnostic=d)
    assert r.state is PseudoState.PSEUDO_CANDIDATE
    assert "class_excluded_from_pseudo_training" in r.reasons


@pytest.mark.parametrize("tp,fp", [(2, 0), (4, 1), (0, 0)])
def test_small_or_wrong_validation_support_blocks_admission(tp, fp):
    assert (
        admit_candidate(candidate(), policy=policy(), diagnostic=diagnostic(tp, fp)).state
        is PseudoState.PSEUDO_CANDIDATE
    )


@pytest.mark.parametrize(
    "v",
    [
        votes(distance=0.36),
        votes(margin=0.01),
        votes(Label.UNKNOWN),
        (votes()[0], replace(votes()[1], label=Label.UI)),
    ],
)
def test_ambiguous_or_unsupported_evidence_remains_unknown(v):
    r = candidate(v=v)
    assert r.state is PseudoState.UNKNOWN and r.label is Label.UNKNOWN
    assert admit_candidate(r, policy=policy(), diagnostic=diagnostic()).state is PseudoState.UNKNOWN


@pytest.mark.parametrize(
    "field,value",
    [
        ("source_sha256", sha("different")),
        ("native_pts_tick", 999),
        ("native_epoch", "other"),
        ("pixel_sha256", sha("other")),
    ],
)
def test_changed_source_native_identity_invalidates_pseudo_binding(field, value):
    r = candidate()
    with pytest.raises(ValueError, match="native patch"):
        replace(r, frame=replace(r.frame, **{field: value})).validate()


def test_model_or_policy_change_rejects_existing_candidate():
    with pytest.raises(ValueError, match="policy changed"):
        admit_candidate(
            candidate(), policy=replace(policy(), maximum_distance=0.3), diagnostic=diagnostic()
        )
    with pytest.raises(ValueError, match="distinct expected"):
        consensus_label((votes()[0], votes()[0]), policy())


def test_forged_admitted_record_cannot_bypass_distance_gate():
    r = admitted()
    forged = replace(r, votes=votes(distance=0.6))
    x, frames, labels = human_data()
    with pytest.raises(ValueError, match="fixed-policy"):
        fit_semisupervised_centroids(
            x,
            frames,
            labels,
            np.array([[1.0, 0.1, 0, 0]]),
            [forged],
            policy=policy(),
            feature_fingerprint=sha("features"),
        )


def test_validation_diagnostic_counts_errors_and_rejects_pseudo_or_train_labels():
    frames = [frame(i, Split.DEVELOPMENT_VALIDATION) for i in range(4)]
    labels = [
        FrameLabel(
            r.frame_sha256,
            Label.PLAYER if i < 3 else Label.UI,
            LabelOrigin.HUMAN_CONFIRMED,
            r.roi_xywh,
        )
        for i, r in enumerate(frames)
    ]
    d = validation_diagnostic(frames, labels, [votes()] * 4, policy=policy(), label=Label.PLAYER)
    assert (d.true_positive, d.false_positive) == (3, 1)
    with pytest.raises(ValueError, match="human-confirmed"):
        validation_diagnostic(
            frames,
            [replace(h, origin=LabelOrigin.PSEUDO) for h in labels],
            [votes()] * 4,
            policy=policy(),
            label=Label.PLAYER,
        )
    with pytest.raises(ValueError, match="development validation"):
        validation_diagnostic(
            [replace(r, split=Split.DEVELOPMENT_TRAIN) for r in frames],
            labels,
            [votes()] * 4,
            policy=policy(),
            label=Label.PLAYER,
        )


def test_semi_supervised_fit_keeps_human_negative_prototypes_and_provenance():
    x, frames, labels = human_data()
    from valorant_ai_coach.visual.development_marker_learning import fit_centroids

    baseline, _ = fit_centroids(
        x,
        frames,
        labels,
        feature_fingerprint=sha("features"),
        maximum_distance=0.35,
        minimum_margin=0.02,
    )
    model, receipt = fit_semisupervised_centroids(
        x,
        frames,
        labels,
        np.array([[1.0, 0.1, 0, 0]]),
        [admitted()],
        policy=policy(),
        feature_fingerprint=sha("features"),
    )
    for name in ["UI", "BACKGROUND", "DEATH_MARKER"]:
        np.testing.assert_array_equal(
            model.centers[list(model.labels).index(name)],
            baseline.centers[list(baseline.labels).index(name)],
        )
    assert receipt["semi_supervised_applied"] and receipt["pseudo_training_records"] == 1
    assert receipt["formal_outputs"] == 0 and receipt["ownership"] == "UNKNOWN"
    assert receipt["effective_class_mass"]["PLAYER"] <= 0.25


def test_pseudo_duplicates_and_unadmitted_records_cannot_amplify_training():
    x, frames, labels = human_data()
    first = admitted()
    other = generate_candidate(
        frame(11),
        first.patch_sha256,
        votes(),
        policy=policy(),
        generated_at="2026-10-27T00:00:00+00:00",
    )
    other = admit_candidate(other, policy=policy(), diagnostic=diagnostic())
    with pytest.raises(ValueError, match="duplicate"):
        fit_semisupervised_centroids(
            x,
            frames,
            labels,
            np.array([[1.0, 0, 0, 0]] * 2),
            [first, other],
            policy=policy(),
            feature_fingerprint=sha("features"),
        )
    with pytest.raises(ValueError, match="admitted"):
        fit_semisupervised_centroids(
            x,
            frames,
            labels,
            np.array([[1.0, 0, 0, 0]]),
            [candidate()],
            policy=policy(),
            feature_fingerprint=sha("features"),
        )


def test_no_pseudo_is_reported_as_no_applied_semi_supervised_training():
    x, frames, labels = human_data()
    _, receipt = fit_semisupervised_centroids(
        x,
        frames,
        labels,
        np.empty((0, 4)),
        [],
        policy=policy(),
        feature_fingerprint=sha("features"),
    )
    assert not receipt["semi_supervised_applied"] and receipt["pseudo_training_records"] == 0


def test_pseudo_shift_cannot_turn_an_existing_correct_human_negative_into_unknown():
    x = np.array([[1.0, 0.0], [0.977, np.sqrt(1 - 0.977**2)]])
    frames = [frame(0), frame(1)]
    labels = [
        FrameLabel(f.frame_sha256, c, LabelOrigin.HUMAN_CONFIRMED, f.roi_xywh)
        for f, c in zip(frames, [Label.PLAYER, Label.UI], strict=True)
    ]
    model, receipt = fit_semisupervised_centroids(
        x, frames, labels, x[1:], [admitted()], policy=policy(), feature_fingerprint=sha("features")
    )
    assert receipt["candidate_rolled_back"]
    assert receipt["human_negative_regression_indices"] == [1]
    assert not receipt["semi_supervised_applied"]
    assert (
        model.classify(x, feature_fingerprint=sha("features"))[1]["appearance_class_candidate"]
        == "UI"
    )

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from valorant_ai_coach.learning import portrait_identity as task
from valorant_ai_coach.learning.features import FeatureStore
from valorant_ai_coach.learning.model_registry import GatePolicy, ModelRegistry
from valorant_ai_coach.learning.models import (
    PrototypeClassifier,
    choose_margin,
    fit_ssl_projection,
    l2_normalize,
    self_train,
)
from valorant_ai_coach.learning.registry import DatasetRegistry, LeakageError


def _archive(tmp_path: Path, name: str, content: bytes) -> Path:
    path = tmp_path / f"{name}.zip"
    path.write_bytes(content)
    return path


def _sha(index: int) -> str:
    return f"{index:064x}"


def test_registry_is_incremental_deterministic_and_leak_free(tmp_path: Path) -> None:
    registry = DatasetRegistry(tmp_path / "reg.json")
    records = []
    for index in range(12):
        archive = _archive(tmp_path, f"m{index}", f"content-{index}".encode())
        record, added = registry.intake(f"m{index}", f"physical-{index}", archive,
                                        source_video_sha256=_sha(index))
        assert added and record.exposure == "DEVELOPMENT"
        records.append(record)
    again, added = registry.intake("m0", "physical-0", tmp_path / "m0.zip",
                                   source_video_sha256=_sha(0))
    assert not added and again == records[0]
    reloaded = DatasetRegistry(tmp_path / "reg.json")
    assert {r.source_id: r.split for r in reloaded.sources()} == {
        r.source_id: r.split for r in records}
    assert {r.split for r in records} <= {"TRAIN", "VALIDATION", "DEV_COMPARISON"}
    # A second recording of the same physical match keeps that match's split.
    record, _ = reloaded.intake("m0b", "physical-0", _archive(tmp_path, "m0b", b"other"),
                                source_video_sha256=_sha(100))
    assert record.split == records[0].split
    wrong = next(s for s in ("TRAIN", "VALIDATION", "DEV_COMPARISON") if s != record.split)
    with pytest.raises(LeakageError):
        reloaded.intake("m0c", "physical-0", _archive(tmp_path, "m0c", b"x"),
                        source_video_sha256=_sha(101), split=wrong)
    # The same source recording under another id (e.g. re-extracted crops) is refused.
    with pytest.raises(LeakageError):
        reloaded.intake("m1-again", "physical-x", _archive(tmp_path, "m1b", b"recut"),
                        source_video_sha256=_sha(1))
    with pytest.raises(ValueError):
        reloaded.intake("dup", "physical-99", tmp_path / "m1.zip", source_video_sha256=_sha(99))
    with pytest.raises(ValueError):
        reloaded.intake("nohash", "physical-98", _archive(tmp_path, "n", b"n"),
                        source_video_sha256="")
    first_two = reloaded.sources(limit_matches=2)
    assert {r.physical_match_id for r in first_two} == {"physical-0", "physical-1"}


def test_unexposed_recordings_form_an_independent_test(tmp_path: Path) -> None:
    registry = DatasetRegistry(tmp_path / "reg.json")
    seen, _ = registry.intake("dev", "physical-1", _archive(tmp_path, "dev", b"a"),
                              source_video_sha256=_sha(1))
    fresh, _ = registry.intake("new", "physical-2", _archive(tmp_path, "new", b"b"),
                               source_video_sha256=_sha(2), unexposed=True)
    assert fresh.split == "INDEPENDENT_TEST" and fresh.exposure == "UNEXPOSED_AT_REGISTRATION"
    with pytest.raises(LeakageError):
        registry.intake("dev2", "physical-1", _archive(tmp_path, "dev2", b"c"),
                        source_video_sha256=_sha(3), unexposed=True)
    assert seen.split != "INDEPENDENT_TEST"


def test_legacy_frozen_split_reads_as_dev_comparison(tmp_path: Path) -> None:
    path = tmp_path / "reg.json"
    path.write_text(json.dumps({
        "seed": "continual-v1",
        "ratios": {"TRAIN": 0.6, "VALIDATION": 0.2, "FROZEN_TEST": 0.2},
        "sources": [{"source_id": "a", "physical_match_id": "p", "archive": "a.zip",
                     "archive_sha256": "0" * 64, "archive_bytes": 1, "split": "FROZEN_TEST",
                     "added_at": "t", "order": 0}]}), "utf-8")
    assert DatasetRegistry(path).sources()[0].split == "DEV_COMPARISON"


def test_registry_seed_cannot_change(tmp_path: Path) -> None:
    DatasetRegistry(tmp_path / "reg.json").save()
    with pytest.raises(ValueError):
        DatasetRegistry(tmp_path / "reg.json", seed="other")


def test_model_registry_gate_reads_validation_only_and_rolls_back(tmp_path: Path) -> None:
    registry = ModelRegistry(tmp_path)
    first = registry.register("t", "f", {"w": np.zeros(3)}, {"a": 1},
                              {"validation_accuracy": 0.5, "validation_team_recall": 0.5,
                               "dev_comparison_weak_ref_consistency": 0.9}, "d1")
    assert registry.decide(first.version_id, GatePolicy())["adopt"]
    # A large DEV_COMPARISON gain does not matter: VALIDATION did not improve.
    comparison_only = registry.register(
        "t", "f", {"w": np.ones(3)}, {"a": 2},
        {"validation_accuracy": 0.5, "validation_team_recall": 0.5,
         "dev_comparison_weak_ref_consistency": 1.0}, "d2")
    assert not registry.decide(comparison_only.version_id, GatePolicy())["adopt"]
    recall_drop = registry.register("t", "f", {"w": np.full(3, 2.0)}, {"a": 3},
                                    {"validation_accuracy": 0.6,
                                     "validation_team_recall": 0.4}, "d3")
    decision = registry.decide(recall_drop.version_id, GatePolicy())
    assert not decision["adopt"] and "validation_team_recall" in decision["reason"]
    better = registry.register("t", "f", {"w": np.full(3, 3.0)}, {"a": 4},
                               {"validation_accuracy": 0.7, "validation_team_recall": 0.6}, "d4")
    assert registry.decide(better.version_id, GatePolicy())["adopt"]
    assert registry.active_id("t") == better.version_id
    assert registry.rollback("t") == first.version_id
    assert registry.versions[better.version_id].status == "ROLLED_BACK"
    assert [e["event"] for e in registry.history()].count("rollback") == 1
    assert np.array_equal(registry.load_arrays(better.version_id)["w"], np.full(3, 3.0))
    assert ModelRegistry(tmp_path).active_id("t") == first.version_id
    with pytest.raises(ValueError):
        GatePolicy(metric="dev_comparison_weak_ref_consistency")


def test_feature_store_computes_once(tmp_path: Path) -> None:
    store = FeatureStore(tmp_path)
    calls = []

    def compute() -> dict[str, object]:
        calls.append(1)
        return {"x": np.arange(4), "meta": {"video_id": "v"}}

    assert store.get_or_compute("ab" * 32, "e1", compute)["meta"] == {"video_id": "v"}
    loaded = store.get_or_compute("ab" * 32, "e1", compute)
    assert np.array_equal(loaded["x"], np.arange(4)) and loaded["meta"]["video_id"] == "v"
    assert len(calls) == 1 and store.hits == 1


def _clusters(rng: np.random.Generator, centers: np.ndarray, n: int, noise: float) -> tuple[
        np.ndarray, list[int]]:
    labels = rng.integers(0, len(centers), n)
    return centers[labels] + rng.normal(0, noise, (n, centers.shape[1])), labels.tolist()


def test_prototypes_projection_and_self_training_improve_shifted_domain() -> None:
    rng = np.random.default_rng(0)
    centers = rng.normal(0, 1, (4, 30))
    shift = rng.normal(0, 0.8, 30)  # domain shift between anchors and observations
    classes = ("a", "b", "c", "d")
    anchors = l2_normalize(centers)
    target, truth = _clusters(rng, centers + shift, 400, 0.4)
    zero = PrototypeClassifier.fit(anchors, list(classes), classes)
    zero_acc = np.mean([p == classes[t] for p, t in zip(zero.predict(l2_normalize(target))[0],
                                                       truth, strict=True)])
    projection = fit_ssl_projection(np.vstack([target, centers]), k=8)
    adapted, counts = self_train(projection(centers), list(classes), projection(target), classes,
                                 rounds=3, min_gap=0.02)
    acc = np.mean([p == classes[t] for p, t in zip(adapted.predict(projection(target))[0], truth,
                                                  strict=True)])
    assert acc >= zero_acc and sum(counts.values()) > 0
    adapted.margin = choose_margin(adapted, projection(target), [classes[t] for t in truth], 0.3)
    labels, _, _ = adapted.predict(projection(target))
    assert labels.count(None) <= 0.3 * len(labels) + 1


def test_assignment_is_one_to_one() -> None:
    scores = np.array([[0.9, 0.8, 0.1], [0.85, 0.2, 0.1]])
    assert task._assign(scores, [0, 1, 2]) == [1, 0]
    assert task._assign(scores, [0]) is None


def test_portrait_task_learns_from_cross_modal_ally_sets() -> None:
    rng = np.random.default_rng(3)
    names = tuple(f"agent{i}" for i in range(8))
    centers = rng.normal(0, 1, (8, 40))
    anchors = (np.vstack([centers + rng.normal(0, 1.2, 40) for _ in range(2)]),
               list(names) * 2)

    def match(match_id: str, ally: list[int], enemy: list[int]) -> task.MatchPortraits:
        feats, teams, secs = [], [], []
        for sec in range(30):
            for team, members in ((task.ALLY, ally), (task.ENEMY, enemy)):
                for agent in members:
                    feats.append(centers[agent] + rng.normal(0, 0.5, 40))
                    teams.append(team)
                    secs.append(sec)
        return task.MatchPortraits(match_id, np.vstack(feats), np.asarray(teams, np.int8),
                                   np.asarray(secs, np.float32),
                                   tuple(names[i] for i in ally), names[ally[0]])

    train = [match("t1", [0, 1, 2, 3], [4, 5, 6, 7]), match("t2", [4, 5, 6, 7], [0, 1, 2, 3])]
    test = [match("f1", [0, 2, 4, 6], [1, 3, 5, 7])]
    test[0].slot = np.tile(np.arange(4, dtype=np.int8), len(test[0].team) // 4)
    zero = task.train(anchors, [], {"ssl": False, "rounds": 0})
    learned = task.train(anchors, train, {"ssl": True, "ssl_dims": 16, "rounds": 2})
    before = task.evaluate(zero, test)["ally_set_consistency"]
    after = task.evaluate(learned, test)["ally_set_consistency"]
    assert learned.stats["weak_labels"] > 0
    assert after >= before
    assert after > 0.9
    json.dumps(task.evaluate(learned, test))
    labels = [{"match_id": "f1", "sec": 0.0, "team": "ally", "slot": slot, "agent": names[agent]}
              for slot, agent in enumerate([0, 2, 4, 6])]
    reviewed = task.reviewed_accuracy(learned, test, labels)
    assert reviewed["reviewed_labels"] == 4 and reviewed["reviewed_accuracy"] == 1.0


def test_exact_reference_uses_single_ally_frames_only() -> None:
    names = ("a", "b", "c")
    protos = np.eye(3)
    model = task.PortraitModel({}, np.zeros(3), np.eye(3), np.ones(3), names, protos)
    features = np.array([[1.0, 0, 0], [0, 1.0, 0], [0, 0, 1.0], [0, 1.0, 0]])
    match = task.MatchPortraits(
        "m", features, np.asarray([task.ALLY, task.ALLY, task.ALLY, task.ENEMY], np.int8),
        np.asarray([0.0, 5.0, 5.0, 10.0], np.float32), ("a", "b", "c"), "a",
        np.zeros(4, np.int8),
        ((0.0, "a", 0.95), (5.0, "b", 0.95), (10.0, "c", 0.95)))
    result = task.exact_reference_accuracy(model, [match])
    # sec 0: one ally, HUD "a" -> correct; sec 5: two allies -> skipped;
    # sec 10: no ally portrait -> skipped.
    assert result == {"exact_ref_accuracy": 1.0, "exact_ref_portraits": 1.0}

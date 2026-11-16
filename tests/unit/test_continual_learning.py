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


def test_registry_is_incremental_deterministic_and_leak_free(tmp_path: Path) -> None:
    registry = DatasetRegistry(tmp_path / "reg.json")
    records = []
    for index in range(12):
        archive = _archive(tmp_path, f"m{index}", f"content-{index}".encode("utf-8"))  # noqa: UP012
        record, added = registry.intake(f"m{index}", f"physical-{index}", archive)
        assert added
        records.append(record)
    again, added = registry.intake("m0", "physical-0", tmp_path / "m0.zip")
    assert not added and again == records[0]
    reloaded = DatasetRegistry(tmp_path / "reg.json")
    assert {r.source_id: r.split for r in reloaded.sources()} == {
        r.source_id: r.split for r in records}
    assert {r.split for r in records} <= {"TRAIN", "VALIDATION", "FROZEN_TEST"}
    # A second recording of the same physical match keeps that match's split.
    other = _archive(tmp_path, "m0b", b"other-encoding")
    record, _ = reloaded.intake("m0b", "physical-0", other)
    assert record.split == records[0].split
    wrong = next(s for s in ("TRAIN", "VALIDATION", "FROZEN_TEST") if s != record.split)
    with pytest.raises(LeakageError):
        reloaded.intake("m0c", "physical-0", _archive(tmp_path, "m0c", b"x"), split=wrong)
    with pytest.raises(ValueError):
        reloaded.intake("dup", "physical-99", tmp_path / "m1.zip")
    first_two = reloaded.sources(limit_matches=2)
    assert {r.physical_match_id for r in first_two} == {"physical-0", "physical-1"}


def test_registry_seed_cannot_change(tmp_path: Path) -> None:
    DatasetRegistry(tmp_path / "reg.json").save()
    with pytest.raises(ValueError):
        DatasetRegistry(tmp_path / "reg.json", seed="other")


def test_model_registry_gate_and_rollback(tmp_path: Path) -> None:
    registry = ModelRegistry(tmp_path)
    arrays = {"w": np.zeros(3)}
    first = registry.register("t", "f", arrays, {"a": 1},
                              {"frozen_accuracy": 0.5, "validation_accuracy": 0.5}, "d1")
    assert registry.decide(first.version_id, GatePolicy())["adopt"]
    worse = registry.register("t", "f", {"w": np.ones(3)}, {"a": 2},
                              {"frozen_accuracy": 0.45, "validation_accuracy": 0.6}, "d2")
    assert not registry.decide(worse.version_id, GatePolicy())["adopt"]
    assert registry.active_id("t") == first.version_id
    regress = registry.register("t", "f", {"w": np.full(3, 2.0)}, {"a": 3},
                                {"frozen_accuracy": 0.6, "validation_accuracy": 0.4}, "d3")
    decision = registry.decide(regress.version_id, GatePolicy())
    assert not decision["adopt"] and "validation_accuracy" in decision["reason"]
    better = registry.register("t", "f", {"w": np.full(3, 3.0)}, {"a": 4},
                               {"frozen_accuracy": 0.7, "validation_accuracy": 0.6}, "d4")
    assert registry.decide(better.version_id, GatePolicy())["adopt"]
    assert registry.active_id("t") == better.version_id
    assert registry.rollback("t") == first.version_id
    assert registry.versions[better.version_id].status == "ROLLED_BACK"
    assert [e["event"] for e in registry.history()].count("rollback") == 1
    assert np.array_equal(registry.load_arrays(better.version_id)["w"], np.full(3, 3.0))
    assert ModelRegistry(tmp_path).active_id("t") == first.version_id


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
    zero = task.train(anchors, [], {"ssl": False, "rounds": 0})
    learned = task.train(anchors, train, {"ssl": True, "ssl_dims": 16, "rounds": 2})
    before = task.evaluate(zero, test)["ally_set_consistency"]
    after = task.evaluate(learned, test)["ally_set_consistency"]
    assert learned.stats["weak_labels"] > 0
    assert after >= before
    assert after > 0.9
    json.dumps(task.evaluate(learned, test))

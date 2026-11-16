"""One continual-learning cycle: intake -> features -> train -> validate -> gate.

    python -m valorant_ai_coach.learning cycle --workspace PRIVATE_DIR --cache ASSETS \
        --manifest VIDEO_HASHES.json CROPS/*.zip
    python -m valorant_ai_coach.learning curve --workspace PRIVATE_DIR --cache ASSETS
    python -m valorant_ai_coach.learning status --workspace PRIVATE_DIR
    python -m valorant_ai_coach.learning rollback --workspace PRIVATE_DIR

Every artefact (registry, features, models, reports) lives in the private
workspace. Adding recordings re-runs only the new archives' feature extraction.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from valorant_ai_coach.knowledge import load_game_knowledge
from valorant_ai_coach.knowledge.assets import ReferenceAssets
from valorant_ai_coach.knowledge.hud_abilities import AbilityHudReader

from . import portrait_identity as task
from .features import FeatureStore
from .model_registry import GatePolicy, ModelRegistry
from .registry import DatasetRegistry

TASK = "portrait_identity"
DEFAULT_CONFIG = {"ssl": True, "ssl_dims": 64, "rounds": 2, "enemy": True,
                  "anchor_weight": 20.0}


@dataclass
class Workspace:
    root: Path

    @property
    def dataset(self) -> DatasetRegistry:
        return DatasetRegistry(self.root / "dataset_registry.json")

    @property
    def features(self) -> FeatureStore:
        return FeatureStore(self.root / "features")

    @property
    def models(self) -> ModelRegistry:
        return ModelRegistry(self.root / "models")


class Context:
    def __init__(self, workspace: Workspace, cache: Path | None) -> None:
        self.workspace = workspace
        self.knowledge = load_game_knowledge()
        self.assets = ReferenceAssets.load(cache)
        self._reader: AbilityHudReader | None = None
        self.names = tuple(agent.name for agent in self.knowledge.agents)

    @property
    def reader(self) -> AbilityHudReader:
        if self._reader is None:
            self._reader = AbilityHudReader(self.knowledge, self.assets)
        return self._reader

    def anchors(self) -> tuple[np.ndarray, list[str]]:
        return task.knowledge_anchors(self.knowledge, self.assets)

    def matches(self, split: str, limit: int | None = None) -> list[task.MatchPortraits]:
        store = self.workspace.features
        out = []
        for record in self.workspace.dataset.sources(split, limit_matches=limit):
            archive = Path(record.archive)

            def compute(archive: Path = archive) -> dict[str, Any]:
                return task.extract(archive, self.reader)

            arrays = store.get_or_compute(record.archive_sha256, task.EXTRACTOR_ID, compute)
            out.append(task.MatchPortraits.from_arrays(record.source_id, arrays, self.names))
        return out


def intake(workspace: Workspace, archives: list[Path], manifest: dict[str, Any]
           ) -> list[dict[str, Any]]:
    """Register archives using a manifest of the *source recordings*.

    ``manifest[source_id]`` gives ``sha256`` of the original video and,
    optionally, ``physical_match_id`` (default: one recording = one match) and
    ``unexposed`` (only for recordings nobody has looked at during development).
    Archives without a manifest entry are refused: leakage is checked on the
    source video, so its hash is mandatory.
    """
    registry = workspace.dataset
    added = []
    for archive in sorted(archives):
        source_id = archive.stem
        entry = manifest.get(source_id)
        if entry is None:
            raise ValueError(f"{source_id}: no source-video entry in the manifest")
        record, is_new = registry.intake(
            source_id, str(entry.get("physical_match_id", f"physical:{source_id}")), archive,
            source_video_sha256=str(entry["sha256"]), unexposed=bool(entry.get("unexposed")))
        added.append({"source_id": source_id, "split": record.split, "new": is_new})
    return added


def _prefixed(prefix: str, metrics: dict[str, float]) -> dict[str, float]:
    names = {"ally_set_consistency": "weak_ref_consistency"}
    return {f"{prefix}_{names.get(k, k)}": float(v) for k, v in metrics.items()}


def run_cycle(workspace: Workspace, context: Context, config: dict[str, Any] | None = None,
              policy: GatePolicy | None = None,
              reviewed_labels: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Train on TRAIN, decide on VALIDATION, report DEV_COMPARISON.

    INDEPENDENT_TEST is never read here (see :func:`evaluate_independent`).
    ``validation_accuracy`` is agreement with the ability-HUD weak reference;
    ``dev_comparison_reviewed_accuracy`` (when labels are given) is the
    per-portrait recognition accuracy against reviewed labels.
    """
    config = dict(DEFAULT_CONFIG if config is None else config)
    started = time.time()
    train_matches = context.matches("TRAIN")
    validation = context.matches("VALIDATION")
    comparison = context.matches("DEV_COMPARISON")
    model = task.train(context.anchors(), train_matches, config)
    val = task.evaluate(model, validation)
    metrics = {
        "validation_accuracy": val["ally_set_consistency"],
        "validation_team_recall": val["ally_team_recall"],
        "validation_exact_ref_accuracy": val["exact_ref_accuracy"],
        "validation_matches": val["evaluated_matches"],
        **_prefixed("dev_comparison", task.evaluate(model, comparison)),
        "train_matches": float(len(train_matches)),
        "weak_labels": float(model.stats["weak_labels"]),
    }
    if reviewed_labels:
        metrics.update(_prefixed("dev_comparison",
                                 task.reviewed_accuracy(model, comparison, reviewed_labels)))
    models = workspace.models
    version = models.register(TASK, "prototype_ssl" if config.get("ssl") else "prototype",
                              model.arrays(), config, metrics,
                              workspace.dataset.fingerprint("TRAIN"))
    decision = models.decide(version.version_id, policy or GatePolicy()) \
        if version.status == "CANDIDATE" else version.decision
    report = {"version_id": version.version_id, "metrics": metrics, "decision": decision,
              "active": models.active_id(TASK), "seconds": round(time.time() - started, 1),
              "feature_cache": {"hits": context.workspace.features.hits}}
    return report


def evaluate_independent(workspace: Workspace, context: Context,
                         reviewed_labels: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Score the ACTIVE model on INDEPENDENT_TEST only. Never feeds back into gating."""
    models = workspace.models
    active = models.active_id(TASK)
    if active is None:
        raise ValueError("No ACTIVE model")
    matches = context.matches("INDEPENDENT_TEST")
    if not matches:
        return {"active": active, "independent_matches": 0,
                "note": "No unexposed recordings registered yet"}
    arrays = models.load_arrays(active)
    model = task.PortraitModel(models.versions[active].config, arrays["projection_mean"],
                               arrays["projection_components"], arrays["projection_scale"],
                               tuple(str(c) for c in arrays["classes"]), arrays["prototypes"])
    result: dict[str, Any] = {"active": active,
                              **_prefixed("independent", task.evaluate(model, matches))}
    if reviewed_labels:
        result.update(_prefixed("independent",
                                task.reviewed_accuracy(model, matches, reviewed_labels)))
    return result


def learning_curve(workspace: Workspace, context: Context, sizes: list[int],
                   config: dict[str, Any] | None = None,
                   reviewed_labels: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """DEV_COMPARISON metrics as TRAIN grows (intake order), plus ablations at full size.

    For development comparison only; adoption decisions never read these rows.
    """
    config = dict(DEFAULT_CONFIG if config is None else config)
    frozen = context.matches("DEV_COMPARISON")
    labels = reviewed_labels or []

    def score(model: task.PortraitModel) -> dict[str, float]:
        out = task.evaluate(model, frozen)
        if labels:
            out.update(task.reviewed_accuracy(model, frozen, labels))
        return out
    all_train = context.matches("TRAIN")
    anchors = context.anchors()
    rows = []
    zero = task.train(anchors, [], {"ssl": False, "rounds": 0})
    rows.append({"variant": "knowledge_zero_shot", "train_matches": 0,
                 **score(zero)})
    for size in sizes:
        subset = all_train[:size]
        if len(subset) < size:
            break
        ssl_only = task.train(anchors, subset, {**config, "rounds": 0})
        full = task.train(anchors, subset, config)
        rows.append({"variant": "knowledge+ssl", "train_matches": size,
                     **score(ssl_only)})
        rows.append({"variant": "knowledge+ssl+weak_labels", "train_matches": size,
                     "weak_labels": full.stats["weak_labels"], **score(full)})
    if all_train:
        no_ssl = task.train(anchors, all_train, {**config, "ssl": False})
        rows.append({"variant": "knowledge+weak_labels(no_ssl)", "train_matches": len(all_train),
                     **score(no_ssl)})
    return rows


def save_report(workspace: Workspace, name: str, payload: Any) -> Path:
    path = workspace.root / "reports" / f"{name}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    return path

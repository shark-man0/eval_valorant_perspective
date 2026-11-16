"""Continual-learning task: agent identity of top-bar portraits.

Signals, from weakest to strongest assumption:

* external knowledge: official agent display icons give one labelled anchor
  set per agent (zero-shot, large domain gap);
* self-supervision: a PCA projection fitted on unlabeled portraits of the
  TRAIN split adapts the feature space to the HUD rendering;
* cross-modal weak labels: on TRAIN matches only, the ability HUD (an
  independent sensor read with official ability icons) reveals which agents are
  on the recorder's team. Each frame's ally portraits are assigned to that set
  with a one-to-one matching; enemy portraits are matched to the five agents the
  current model votes for over the match (agents are fixed within a match).

Evaluation on held-out matches uses the ability-HUD ally set of the *test*
match as an independent reference: the share of ally-portrait predictions that
belong to it (``ally_set_consistency``) and the overlap of the predicted ally
team with it (``ally_team_recall``). Neither is a human ground truth; both are
reported as such.
"""

from __future__ import annotations

import itertools
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from valorant_ai_coach.knowledge.catalog import GameKnowledge
from valorant_ai_coach.knowledge.hud_abilities import AbilityHudReader
from valorant_ai_coach.knowledge.top_bar import portrait_crops, portrait_feature, read_top_bar

from .archives import CropArchive
from .models import (
    PrototypeClassifier,
    fit_ssl_projection,
    identity_projection,
    l2_normalize,
)

EXTRACTOR_ID = "portrait_v1"
ALLY, ENEMY = 0, 1
MIN_VIEW_SAMPLES = 5
MIN_VIEW_SCORE = 0.6


def extract(archive: Path, reader: AbilityHudReader) -> dict[str, Any]:
    """Portrait features (float16) and the per-sample viewed HUD agent of one archive."""
    crops = CropArchive(archive)
    feats, teams, slots, secs = [], [], [], []
    viewed, viewed_score, viewed_sec = [], [], []
    for sample in crops.iter_samples(("abilities", "top_bar")):
        if "abilities" in sample.crops:
            reading = reader.read(sample.crops["abilities"])
            best = int(np.argmax(reading.agent_scores))
            viewed.append(best if reading.hud_present else -1)
            viewed_score.append(float(reading.agent_scores[best]))
            viewed_sec.append(sample.sec)
        if "top_bar" not in sample.crops:
            continue
        bar = read_top_bar(sample.crops["top_bar"])
        if not bar.consistent:
            continue
        for team, slot, portrait in portrait_crops(sample.crops["top_bar"], bar):
            if portrait.shape[:2] != (42, 42):
                continue
            feats.append(portrait_feature(portrait).astype(np.float16))
            teams.append(ALLY if team == "ally" else ENEMY)
            slots.append(slot)
            secs.append(sample.sec)
    result = {
        "features": np.vstack(feats) if feats else np.zeros((0, 1200), np.float16),
        "team": np.asarray(teams, np.int8),
        "slot": np.asarray(slots, np.int8),
        "sec": np.asarray(secs, np.float32),
        "viewed": np.asarray(viewed, np.int16),
        "viewed_score": np.asarray(viewed_score, np.float32),
        "viewed_sec": np.asarray(viewed_sec, np.float32),
        "meta": {"video_id": crops.video_id, "extractor": EXTRACTOR_ID},
    }
    crops.close()
    return result


@dataclass
class MatchPortraits:
    match_id: str
    features: NDArray[np.float64]
    team: NDArray[np.int8]
    sec: NDArray[np.float32]
    ally_set: tuple[str, ...]
    recorder: str | None

    @classmethod
    def from_arrays(cls, match_id: str, arrays: dict[str, Any], agent_names: tuple[str, ...]
                    ) -> MatchPortraits:
        viewed = np.asarray(arrays["viewed"])
        scores = np.asarray(arrays["viewed_score"])
        counts = Counter(int(v) for v, s in zip(viewed, scores, strict=True)
                         if v >= 0 and s >= MIN_VIEW_SCORE)
        ally = tuple(sorted(agent_names[i] for i, n in counts.items() if n >= MIN_VIEW_SAMPLES))
        recorder = agent_names[counts.most_common(1)[0][0]] if counts else None
        return cls(match_id, np.asarray(arrays["features"], np.float64),
                   np.asarray(arrays["team"]), np.asarray(arrays["sec"]), ally, recorder)


@dataclass
class PortraitModel:
    config: dict[str, Any]
    projection_mean: NDArray[np.float64]
    projection_components: NDArray[np.float64]
    projection_scale: NDArray[np.float64]
    classes: tuple[str, ...]
    prototypes: NDArray[np.float64]
    stats: dict[str, Any] = field(default_factory=dict)

    def embed(self, x: NDArray[np.float64]) -> NDArray[np.float64]:
        z = ((x - self.projection_mean) @ self.projection_components.T) / self.projection_scale
        return l2_normalize(z)

    def scores(self, x: NDArray[np.float64]) -> NDArray[np.float64]:
        return self.embed(x) @ self.prototypes.T

    def arrays(self) -> dict[str, NDArray[Any]]:
        return {"projection_mean": self.projection_mean,
                "projection_components": self.projection_components,
                "projection_scale": self.projection_scale, "prototypes": self.prototypes,
                "classes": np.asarray(self.classes)}


def _assign(scores: NDArray[np.float64], candidates: list[int]) -> list[int] | None:
    """One-to-one assignment of rows to candidate classes maximizing total score."""
    rows = scores.shape[0]
    if rows == 0 or rows > len(candidates):
        return None
    best, best_value = None, -np.inf
    for perm in itertools.permutations(candidates, rows):
        value = float(scores[np.arange(rows), list(perm)].sum())
        if value > best_value:
            best, best_value = list(perm), value
    return best


def _weak_labels(model: PortraitModel, match: MatchPortraits, use_enemy: bool
                 ) -> tuple[list[int], list[int]]:
    """(row indices, class indices) from one-to-one matching within each frame."""
    index = {name: i for i, name in enumerate(model.classes)}
    rows_out: list[int] = []
    labels_out: list[int] = []
    scores = model.scores(match.features)
    team_sets: dict[int, list[int]] = {}
    if len(match.ally_set) >= 4:
        team_sets[ALLY] = [index[name] for name in match.ally_set if name in index]
    if use_enemy:
        enemy_rows = np.where(match.team == ENEMY)[0]
        if len(enemy_rows):
            votes = Counter(int(i) for i in np.argmax(scores[enemy_rows], axis=1))
            team_sets[ENEMY] = [c for c, _ in votes.most_common(5)]
    for sec in np.unique(match.sec):
        for team, candidates in team_sets.items():
            rows = np.where((match.sec == sec) & (match.team == team))[0]
            assignment = _assign(scores[rows], candidates)
            if assignment is None:
                continue
            rows_out.extend(int(r) for r in rows)
            labels_out.extend(assignment)
    return rows_out, labels_out


def train(anchors: tuple[NDArray[np.float64], list[str]], matches: list[MatchPortraits],
          config: dict[str, Any]) -> PortraitModel:
    anchor_x, anchor_y = anchors
    classes = tuple(sorted(set(anchor_y)))
    unlabeled = [m.features for m in matches if len(m.features)]
    if config.get("ssl") and unlabeled:
        stacked = np.vstack(unlabeled)
        rng = np.random.default_rng(0)
        if len(stacked) > 20000:
            stacked = stacked[rng.choice(len(stacked), 20000, replace=False)]
        projection = fit_ssl_projection(stacked, int(config.get("ssl_dims", 64)),
                                        whiten=bool(config.get("ssl_whiten", False)))
    else:
        projection = identity_projection(anchor_x.shape[1])
    model = PortraitModel(config, projection.mean, projection.components, projection.scale,
                          classes, np.zeros((len(classes), projection.components.shape[0])))
    anchor_z = model.embed(anchor_x)
    model.prototypes = PrototypeClassifier.fit(anchor_z, anchor_y, classes).prototypes
    weak_total = 0
    for _ in range(int(config.get("rounds", 0))):
        z_parts, label_parts = [anchor_z], list(anchor_y)
        weights = [np.full(len(anchor_y), float(config.get("anchor_weight", 20.0)))]
        weak_total = 0
        for match in matches:
            rows, labels = _weak_labels(model, match, bool(config.get("enemy", True)))
            if not rows:
                continue
            z_parts.append(model.embed(match.features[rows]))
            label_parts.extend(classes[i] for i in labels)
            weights.append(np.ones(len(rows)))
            weak_total += len(rows)
        model.prototypes = PrototypeClassifier.fit(
            np.vstack(z_parts), label_parts, classes, np.concatenate(weights)).prototypes
    model.stats = {"train_matches": len(matches), "weak_labels": weak_total,
                   "anchors": len(anchor_y)}
    return model


def evaluate(model: PortraitModel, matches: list[MatchPortraits]) -> dict[str, float]:
    """Mean over matches with a reference ally set of >=4 agents."""
    consistency, recall, coverage = [], [], 0
    for match in matches:
        if len(match.ally_set) < 4:
            continue
        rows = np.where(match.team == ALLY)[0]
        if not len(rows):
            continue
        coverage += 1
        predicted = [model.classes[i] for i in np.argmax(model.scores(match.features[rows]),
                                                         axis=1)]
        consistency.append(float(np.mean([p in match.ally_set for p in predicted])))
        top = [name for name, _ in Counter(predicted).most_common(len(match.ally_set))]
        recall.append(len(set(top) & set(match.ally_set)) / len(match.ally_set))
    return {
        "ally_set_consistency": float(np.mean(consistency)) if consistency else 0.0,
        "ally_team_recall": float(np.mean(recall)) if recall else 0.0,
        "evaluated_matches": float(coverage),
    }


def knowledge_anchors(knowledge: GameKnowledge, assets: Any) -> tuple[NDArray[np.float64],
                                                                      list[str]]:
    from valorant_ai_coach.knowledge.top_bar import official_portrait_anchors

    return official_portrait_anchors(knowledge, assets)

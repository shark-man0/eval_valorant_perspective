"""Versioned model registry with a non-regression gate and rollback.

``ACTIVE`` means active for development consumers of this registry only. No
model here is wired into production recognizers; that needs a separate,
explicit approval.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

STATUSES = ("CANDIDATE", "ACTIVE", "RETIRED", "REJECTED", "ROLLED_BACK")


@dataclass(frozen=True)
class GatePolicy:
    """Adopt only when the VALIDATION metric improves and no guard regresses.

    Decisions read VALIDATION metrics only. DEV_COMPARISON and INDEPENDENT_TEST
    metrics are recorded for reporting and never influence adoption.
    """

    metric: str = "validation_accuracy"
    min_improvement: float = 0.005
    guard_metrics: tuple[str, ...] = ("validation_team_recall",)
    max_guard_drop: float = 0.0
    max_abstain_increase: float = 0.05

    def __post_init__(self) -> None:
        for name in (self.metric, *self.guard_metrics):
            if not name.startswith("validation_"):
                raise ValueError(f"Gate may only read VALIDATION metrics, not {name}")


@dataclass
class ModelVersion:
    version_id: str
    task: str
    family: str
    created_at: str
    data_fingerprint: str
    config: dict[str, Any]
    metrics: dict[str, float]
    status: str = "CANDIDATE"
    parent: str | None = None
    decision: dict[str, Any] = field(default_factory=dict)


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


class ModelRegistry:
    """Directory layout: ``registry.json``, ``history.jsonl``, ``models/<id>.npz``."""

    def __init__(self, root: Path) -> None:
        self.root = root
        (root / "models").mkdir(parents=True, exist_ok=True)
        self.index_path = root / "registry.json"
        self.versions: dict[str, ModelVersion] = {}
        if self.index_path.exists():
            for item in json.loads(self.index_path.read_text(encoding="utf-8"))["versions"]:
                version = ModelVersion(**item)
                self.versions[version.version_id] = version

    # Storage ----------------------------------------------------------------
    def _save(self) -> None:
        payload = {"version": "model_registry_v1",
                   "versions": [asdict(v) for v in self.versions.values()]}
        tmp = self.index_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(self.index_path)

    def _log(self, event: str, **fields: Any) -> None:
        with (self.root / "history.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"at": _now(), "event": event, **fields},
                                    ensure_ascii=False) + "\n")

    def register(self, task: str, family: str, arrays: dict[str, np.ndarray],
                 config: dict[str, Any], metrics: dict[str, float], data_fingerprint: str
                 ) -> ModelVersion:
        payload = json.dumps([task, family, config, data_fingerprint], sort_keys=True,
                             default=str).encode("utf-8")  # noqa: UP012
        digest = hashlib.sha256(payload)
        for key in sorted(arrays):
            digest.update(np.ascontiguousarray(arrays[key]).tobytes())
        version_id = f"{task}-{family}-{digest.hexdigest()[:12]}"
        if version_id in self.versions:
            return self.versions[version_id]
        np.savez_compressed(self.root / "models" / f"{version_id}.npz", **arrays)  # type: ignore[arg-type]
        version = ModelVersion(version_id, task, family, _now(), data_fingerprint, config,
                               {k: float(v) for k, v in metrics.items()},
                               parent=self.active_id(task))
        self.versions[version_id] = version
        self._save()
        self._log("register", version_id=version_id, metrics=version.metrics)
        return version

    def load_arrays(self, version_id: str) -> dict[str, np.ndarray]:
        with np.load(self.root / "models" / f"{version_id}.npz") as data:
            return {key: data[key] for key in data.files}

    # Lifecycle --------------------------------------------------------------
    def active_id(self, task: str) -> str | None:
        active = [v for v in self.versions.values() if v.task == task and v.status == "ACTIVE"]
        return active[0].version_id if active else None

    def evaluate_gate(self, candidate_id: str, policy: GatePolicy) -> dict[str, Any]:
        candidate = self.versions[candidate_id]
        active_id = self.active_id(candidate.task)
        if active_id is None:
            return {"adopt": True, "reason": "no active model", "baseline": None}
        baseline = self.versions[active_id].metrics
        metrics = candidate.metrics
        gain = metrics.get(policy.metric, float("-inf")) - baseline.get(policy.metric, 0.0)
        drops = {
            name: baseline.get(name, 0.0) - metrics.get(name, float("-inf"))
            for name in policy.guard_metrics
        }
        abstain_increase = metrics.get("validation_abstain_rate", 0.0) - baseline.get(
            "validation_abstain_rate", 0.0)
        reasons = []
        if gain < policy.min_improvement:
            reasons.append(f"{policy.metric} gain {gain:+.4f} < {policy.min_improvement}")
        for name, drop in drops.items():
            if drop > policy.max_guard_drop:
                reasons.append(f"{name} regressed by {drop:.4f}")
        if abstain_increase > policy.max_abstain_increase:
            reasons.append(f"abstain rate +{abstain_increase:.4f}")
        return {"adopt": not reasons, "reason": "; ".join(reasons) or "improved without regression",
                "baseline": active_id, "gain": gain, "guard_drops": drops}

    def decide(self, candidate_id: str, policy: GatePolicy) -> dict[str, Any]:
        decision = self.evaluate_gate(candidate_id, policy)
        candidate = self.versions[candidate_id]
        candidate.decision = decision
        if decision["adopt"]:
            previous = self.active_id(candidate.task)
            if previous:
                self.versions[previous].status = "RETIRED"
            candidate.status = "ACTIVE"
        else:
            candidate.status = "REJECTED"
        self._save()
        self._log("decide", version_id=candidate_id, **decision)
        return decision

    def rollback(self, task: str) -> str | None:
        """Re-activate the parent of the active model (or the last retired one)."""
        active_id = self.active_id(task)
        if active_id is None:
            return None
        active = self.versions[active_id]
        target = active.parent
        if target is None or target not in self.versions:
            retired = [v for v in self.versions.values()
                       if v.task == task and v.status == "RETIRED"]
            target = retired[-1].version_id if retired else None
        if target is None:
            return None
        active.status = "ROLLED_BACK"
        self.versions[target].status = "ACTIVE"
        self._save()
        self._log("rollback", task=task, from_version=active_id, to_version=target)
        return target

    def history(self) -> list[dict[str, Any]]:
        path = self.root / "history.jsonl"
        if not path.exists():
            return []
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]

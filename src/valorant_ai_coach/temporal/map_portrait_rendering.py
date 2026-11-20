"""Fit a transferable color transform from training-only minimap portrait observations."""

from __future__ import annotations

import hashlib
import io
import json
from collections import defaultdict
from collections.abc import Mapping, Sequence
from importlib import import_module
from pathlib import Path

import numpy as np
from numpy.typing import NDArray


def fit_portrait_rendering(
    references: Sequence[tuple[str, NDArray[np.uint8]]],
    observations: Sequence[tuple[str, NDArray[np.float64]]],
) -> NDArray[np.float64]:
    """Estimate one regularized color transform shared across Agent identities.

    The caller supplies weak observations from TRAIN matches in the development
    registry. Each observation contains a normalized 9 by 9 BGR patch. Use the
    closest external rendering for that Agent. Identity-specific prediction
    labels and Camera state play no part in applying the result.
    """
    templates: dict[str, list[NDArray[np.float64]]] = defaultdict(list)
    for uuid, reference in references:
        x = reference.astype(np.float64).reshape(81, 3)
        x -= x.mean(axis=0)
        templates[uuid].append(x / max(float(np.linalg.norm(x)), 1e-8))
    gram = np.eye(3)
    cross = np.eye(3)
    matched = 0
    for uuid, patch in observations:
        target = np.asarray(patch, dtype=np.float64).reshape(81, 3)
        if not np.isfinite(target).all() or uuid not in templates:
            raise ValueError("Finite training patch and known Agent required")
        target = target - target.mean(axis=0)
        target /= max(float(np.linalg.norm(target)), 1e-8)
        source = max(templates[uuid], key=lambda x: float(np.sum(x * target)))
        if np.sum(source * target) >= .65:
            gram += source.T @ source
            cross += source.T @ target
            matched += 1
    if matched < 3:
        raise ValueError("Insufficient matching training observations")
    return np.linalg.solve(gram, cross)


def render_portrait(
    image: NDArray[np.uint8], matrix: NDArray[np.float64],
) -> NDArray[np.uint8]:
    if matrix.shape != (3, 3) or not np.isfinite(matrix).all():
        raise ValueError("Finite BGR color matrix required")
    rendered = image.copy()
    colors = image[:, :, :3].astype(np.float64)
    rendered[:, :, :3] = np.clip((colors - 128.) @ matrix + 128., 0, 255).astype(np.uint8)
    return rendered


def fit_registered_rendering(
    references: Sequence[tuple[str, NDArray[np.uint8]]],
    registry_path: Path, feature_root: Path, receipts: Mapping[str, tuple[str, str]],
) -> NDArray[np.float64]:
    """Read content-pinned TRAIN feature archives from the continual learning registry.

    Receipts map the registered acquisition hash to the extractor ID and the
    feature file's digest. FeatureStore entries contain weak 9x9 observations
    and their recording Agent identity. Comparison matches never supply inputs.
    """
    registry_type = import_module("valorant_ai_coach.learning.registry").DatasetRegistry
    store_type = import_module("valorant_ai_coach.learning.features").FeatureStore
    sources = registry_type(registry_path).sources("TRAIN")
    registered = {r.archive_sha256: r for r in sources}
    if not receipts or not receipts.keys() <= registered.keys():
        raise ValueError("Every learning receipt must identify a registered TRAIN acquisition")
    store = store_type(feature_root)
    examples: list[tuple[str, NDArray[np.float64]]] = []
    for archive_sha, (extractor, expected_sha) in sorted(receipts.items()):
        path = store.path(archive_sha, extractor).resolve()
        if path.parent != feature_root.resolve():
            raise ValueError("Feature must be inside the private feature store")
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != expected_sha:
            raise ValueError("Training feature content changed")
        with np.load(io.BytesIO(data), allow_pickle=False) as rows:
            agent = json.loads(str(rows["meta_json"]))["identity"]
            weak = rows["weak"]
            if weak.ndim != 2 or weak.shape[1] != 243:
                raise ValueError("Expected normalized 9x9 BGR observations")
            examples.extend((agent, patch) for patch in weak)
    return fit_portrait_rendering(references, examples)

"""Bundle a frozen source-backed purchase-text candidate for bounded replay.

This diagnostic consumes training assets only. It never reads holdout labels,
GT, expected boundaries or expected states. Generation is not adoption.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path
from tempfile import TemporaryDirectory

import cv2
import numpy as np

from valorant_ai_coach.hud.calibrate_profile import _bundle_assets, _write_asset
from valorant_ai_coach.hud.calibrate_temporal import _check_output_privacy, _localize_assets
from valorant_ai_coach.hud.layout import HudLayout
from valorant_ai_coach.hud.semantic_text import MATCHER, SemanticTextReference
from valorant_ai_coach.hud.templates import HudTemplateProfile


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def gray(path: Path) -> np.ndarray:
    image = cv2.imdecode(np.frombuffer(path.read_bytes(), np.uint8), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise ValueError("phase source image is unreadable")
    return image


def build_profile(layout_path: Path, reference_dir: Path, archive_root: Path, output: Path) -> Path:
    """Preserve frozen bytes/ROI/threshold and bundle all existing assets."""
    layout_path = layout_path.resolve()
    reference_dir = reference_dir.resolve()
    archive_root = archive_root.resolve()
    output = output.resolve()
    if output.exists():
        raise FileExistsError("phase output directory must be new")
    _check_output_privacy(output)
    layout = HudLayout.load(layout_path)
    if layout.reference_resolution is None:
        raise ValueError("phase profile requires reference resolution")
    base = HudTemplateProfile.load(layout_path.with_suffix(".templates.json"))
    if base.reader_diagnostics:
        raise ValueError("base profile has unresolved reader diagnostics")
    if any(not base.resolve_asset(path).is_file() for path in base.asset_paths):
        raise ValueError("base profile has missing assets")
    base_fingerprint = base.fingerprint(layout_path)
    manifest_path = reference_dir / "frozen-manifest.json"
    manifest_bytes = manifest_path.read_bytes()
    manifest_hash = hashlib.sha256(manifest_bytes).hexdigest()
    manifest = json.loads(manifest_bytes)
    names = ("reference.png", "mask.png", "groups.png")
    for name in names:
        if sha256(reference_dir / name) != manifest["asset_hashes"][name]:
            raise ValueError("frozen phase asset hash mismatch")
    bounds = manifest["crop_xyxy"]
    if len(bounds) != 4 or any(type(value) is not int for value in bounds):
        raise ValueError("frozen crop requires four integer bounds")
    x1, y1, x2, y2 = bounds
    width, height = layout.reference_resolution
    left, top, right, bottom = layout.normalized_roi("center_phase_banner").pixel_bounds(
        width, height
    )
    if not left <= x1 < x2 <= right or not top <= y1 < y2 <= bottom:
        raise ValueError("frozen phase crop is outside configured banner ROI")
    training = []
    for row in manifest["training_frames"]:
        path = (archive_root / row["frame"]).resolve()
        if not path.is_relative_to(archive_root):
            raise ValueError("training path leaves archive root")
        if sha256(path) != row["frame_sha256"]:
            raise ValueError("training frame hash mismatch")
        image = gray(path)
        if image.shape != (height, width):
            raise ValueError("training resolution differs from base layout")
        training.append((row["frame_sha256"], image[y1:y2, x1:x2]))
    reference = gray(reference_dir / "reference.png")
    if reference.shape != (y2 - y1, x2 - x1):
        raise ValueError("frozen reference dimensions differ from crop")
    matcher = SemanticTextReference(
        reference, gray(reference_dir / "mask.png"), gray(reference_dir / "groups.png"),
        training, manifest["threshold"],
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=".frozen-phase-", dir=output.parent) as temp:
        stage = Path(temp) / "profile"
        stage.mkdir()
        raw = _bundle_assets(_localize_assets(base.raw, base.path.parent), stage)
        assets = stage / "phase"
        assets.mkdir()
        for name in names:
            shutil.copy2(reference_dir / name, assets / name)
        exemplars = []
        for index, (frame_hash, crop) in enumerate(training):
            name = f"training-{index}.png"
            _write_asset(assets / name, crop)
            exemplars.append({"template": f"phase/{name}", "frame_sha256": frame_hash})
        raw.setdefault("signals", {})["buy_phase_template"] = {
            "roi": "center_phase_banner", "matcher": MATCHER,
            "roi_bounds": [(x1 - left) / (right - left), (y1 - top) / (bottom - top),
                           (x2 - left) / (right - left), (y2 - top) / (bottom - top)],
            "template": "phase/reference.png", "mask": "phase/mask.png",
            "support_regions": "phase/groups.png", "threshold": matcher.threshold,
            "training": exemplars,
        }
        selected = stage / "hud_layout.json"
        shutil.copy2(layout_path, selected)
        selected.with_suffix(".templates.json").write_text(
            json.dumps(raw, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        loaded = HudTemplateProfile.load(selected.with_suffix(".templates.json"))
        if loaded.reader_diagnostics or "buy_phase_template" not in loaded._semantic_text:
            raise ValueError("generated phase reference did not load")
        if any(not loaded.resolve_asset(path).is_file() for path in loaded.asset_paths):
            raise ValueError("generated phase assets are missing")
        if (
            base.fingerprint(layout_path) != base_fingerprint
            or sha256(manifest_path) != manifest_hash
            or any(
                sha256(reference_dir / name) != manifest["asset_hashes"][name]
                or sha256(assets / name) != manifest["asset_hashes"][name]
                for name in names
            )
            or any(
                sha256(archive_root / row["frame"]) != row["frame_sha256"]
                for row in manifest["training_frames"]
            )
        ):
            raise ValueError("frozen profile inputs changed during generation")
        diagnostics = {
            "status": "diagnostic_only_not_adopted", "matcher": MATCHER,
            "base_profile_fingerprint": base_fingerprint,
            "frozen_manifest_sha256": manifest_hash,
            "frozen_asset_hashes": manifest["asset_hashes"],
            "training_frame_hashes": [value for value, _ in training],
            "training_support": matcher.training_support, "threshold": matcher.threshold,
            "dimensions": [reference.shape[1], reference.shape[0]],
            "profile_fingerprint": loaded.fingerprint(selected),
        }
        (stage / "phase_profile_diagnostics.json").write_text(
            json.dumps(diagnostics, indent=2) + "\n", encoding="utf-8"
        )
        stage.rename(output)
    return output / "hud_layout.json"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--layout", required=True, type=Path)
    parser.add_argument("--reference-dir", required=True, type=Path)
    parser.add_argument("--archive-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    print(build_profile(args.layout, args.reference_dir, args.archive_root, args.output))


if __name__ == "__main__":
    main()

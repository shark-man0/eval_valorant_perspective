"""Generate a runnable local HUD profile without frame labels or manual JSON edits.

Generated references are observations, not proof of gameplay-state accuracy.
Unavailable evidence stays disabled; it is never filled from expected events.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import cv2
import numpy as np

from valorant_ai_coach.video.service import VideoService

from .calibrate_temporal import _check_output_privacy, _localize_assets, create_temporal_profile
from .layout import HudLayout
from .templates import HudTemplateProfile

ROLES = {
    "hp_hud_structure": "player_hp_armor",
    "ability_bar_structure": "abilities",
    "weapon_ammo_structure": "ammo_current_weapon",
}


def _gray(image: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image


def _score(template: np.ndarray, image: np.ndarray) -> float:
    if template.shape != image.shape or min(float(template.std()), float(image.std())) < 5:
        return 0.0
    value = float(cv2.matchTemplate(image, template, cv2.TM_CCOEFF_NORMED)[0, 0])
    return max(0.0, min(1.0, value)) if math.isfinite(value) else 0.0


def structure_reference(
    crops: list[np.ndarray],
) -> tuple[np.ndarray, list[float], dict[str, Any]] | None:
    """Choose on training frames only; evaluate once on disjoint holdout frames.

    Tight unmasked rectangles are independent of the geometry-anchor masks.
    Long edges plus contrast reject blank areas and most random scene texture.
    """
    if len(crops) < 16 or any(c.shape != crops[0].shape for c in crops):
        return None
    gray = [_gray(c) for c in crops]
    height, width = gray[0].shape
    h, w = max(16, round(height * 0.30)), max(16, round(width * 0.20))
    if h >= height or w >= width:
        return None
    best: tuple[float, np.ndarray, list[float], list[np.ndarray], list[float]] | None = None
    for y in np.linspace(0, height - h, 5).astype(int):
        for x in np.linspace(0, width - w, 5).astype(int):
            patches = [image[y : y + h, x : x + w] for image in gray]
            training = patches[::2]
            reference = np.median(np.stack(training), axis=0).astype(np.uint8)
            edges = cv2.Canny(reference, 60, 150)
            density = float(np.count_nonzero(edges) / edges.size)
            if not 0.015 <= density <= 0.25 or float(reference.std()) < 8:
                continue
            lines = cv2.HoughLinesP(
                edges,
                1,
                np.pi / 180,
                threshold=8,
                minLineLength=max(8, min(h, w) // 3),
                maxLineGap=2,
            )
            if lines is None or len(lines) < 2:
                continue
            scores = [_score(reference, patch) for patch in training]
            support = sum(s >= 0.90 for s in scores) / len(scores)
            if support < 0.80:
                continue
            rank = support + float(np.median(scores))
            if best is None or rank > best[0]:
                best = (
                    rank,
                    reference,
                    [x / width, y / height, (x + w) / width, (y + h) / height],
                    patches,
                    scores,
                )
    if best is None:
        return None
    _, reference, bounds, patches, train_scores = best
    heldout = [_score(reference, patch) for patch in patches[1::2]]
    if sum(s >= 0.90 for s in heldout) / len(heldout) < 0.80:
        return None  # Do not select another candidate using the holdout set.
    return (
        reference,
        bounds,
        {
            "training_count": len(train_scores),
            "holdout_count": len(heldout),
            "training_accept_count": sum(s >= 0.90 for s in train_scores),
            "holdout_accept_count": sum(s >= 0.90 for s in heldout),
            "holdout_median": float(np.median(heldout)),
        },
    )


def clear_reference(crops: list[np.ndarray]) -> tuple[np.ndarray, dict[str, Any]] | None:
    """Only near-uniform, non-black/non-white complete panel ROIs qualify.

    No clustering of text/panels is labelled as spectator/live. Runtime checks
    every pixel against this reference and requires all three HUD structures.
    """
    if len(crops) < 16:
        return None
    gray = [_gray(c) for c in crops]
    train = [
        c for c in gray[::2] if 12 <= float(c.mean()) <= 245 and int(c.max()) - int(c.min()) <= 8
    ]
    if len(train) < 3:
        return None
    reference = np.median(np.stack(train), axis=0).astype(np.uint8)
    matches = [int(np.abs(c.astype(np.int16) - reference).max()) <= 8 for c in gray[1::2]]
    if sum(matches) < 3 or sum(matches) / len(matches) < 0.80:
        return None
    return reference, {
        "training_count": len(train),
        "holdout_count": len(matches),
        "holdout_accept_count": sum(matches),
    }


def _write_asset(path: Path, image: np.ndarray) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    ok, data = cv2.imencode(".png", image)
    if not ok:
        raise ValueError("reference_encode_failed")
    path.write_bytes(data.tobytes())  # Unicode-safe on Windows.
    return {
        "content_hash": hashlib.sha256(path.read_bytes()).hexdigest(),
        "dimensions": [int(image.shape[1]), int(image.shape[0])],
    }


def create_profile(
    video: Path,
    layout_path: Path,
    output_dir: Path,
    *,
    samples: int = 32,
    video_service: VideoService | None = None,
) -> Path:
    if not 16 <= samples <= 64:
        raise ValueError("samplesは16〜64で指定してください")
    output = Path(output_dir).expanduser().resolve()
    if output.exists():
        raise FileExistsError("出力先は未使用フォルダを指定してください")
    _check_output_privacy(output)
    layout_path = Path(layout_path).expanduser().resolve()
    layout = HudLayout.load(layout_path)
    if layout.layout_format != "v3" or layout.reference_resolution is None:
        raise ValueError("v3の基準解像度付きlayoutが必要です")
    service = video_service or VideoService()
    metadata = service.probe(video)
    if not math.isfinite(metadata.duration_sec) or metadata.duration_sec <= 0:
        raise ValueError("動画の時間情報が不正です")
    output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=".hud-profile-", dir=output.parent) as temp:
        work = Path(temp)
        stage = work / "profile"
        geometry_mode = "generated"
        try:
            selected = create_temporal_profile(
                video, layout_path, stage, samples=samples, video_service=service
            )
            raw = json.loads(selected.with_suffix(".templates.json").read_text(encoding="utf-8"))
        except ValueError as exc:
            if str(exc) != "有効な幾何アンカーが3個未満です":
                raise
            # Keep already configured geometry rather than inventing calibration.
            base = HudTemplateProfile.load(layout_path.with_suffix(".templates.json"))
            if len(base.raw.get("anchors", {})) < 3:
                raise ValueError("geometry_profile_unavailable") from exc
            for name, spec in base.raw["anchors"].items():
                base.load_template(name, spec["template"], spec.get("threshold", 0.90))
            raw = _localize_assets(base.raw, base.path.parent)
            geometry_mode = "inherited"
            stage.mkdir()
        paths = service.extract_frames(
            video,
            np.linspace(0, metadata.duration_sec, samples + 2)[1:-1].tolist(),
            work / "identity_frames",
            max_frames=64,
            max_dimension=None,
            metadata=metadata,
        )
        if len(paths) < 16 or len({float(p.time_sec) for p in paths}) != len(paths):
            raise ValueError("distinct_identity_frames_insufficient")
        decoded = [
            cv2.imdecode(np.frombuffer(p.path.read_bytes(), np.uint8), cv2.IMREAD_COLOR)
            for p in paths
        ]
        width, height = layout.reference_resolution
        if any(image is None or image.shape[:2] != (height, width) for image in decoded):
            raise ValueError("identity_frame_resolution_invalid")
        images = [image for image in decoded if image is not None]
        diagnostics: dict[str, Any] = {
            "version": 1,
            "sample_count": len(images),
            "geometry_mode": geometry_mode,
            "references": {},
        }
        raw.setdefault("signals", {})
        inherited = HudTemplateProfile(stage / "hud_layout.templates.json", raw)
        geometry_assets = {
            inherited.resolve_asset(spec[key]).resolve()
            for spec in raw.get("anchors", {}).values()
            if isinstance(spec, dict)
            for key in ("template", "mask")
            if isinstance(spec.get(key), str)
        }
        for name, roi_name in ROLES.items():
            if name in inherited._signal_templates:
                inherited_roi, template = inherited._signal_templates[name]
                if (
                    template.path.resolve() not in geometry_assets
                    and inherited_roi in layout.regions
                ):
                    diagnostics["references"][name] = {
                        "status": "inherited",
                        "content_hash": hashlib.sha256(template.path.read_bytes()).hexdigest(),
                        "dimensions": [int(template.image.shape[1]), int(template.image.shape[0])],
                    }
                    continue
            # Invalid/missing assets and reused geometry are not independent evidence.
            raw["signals"].pop(name, None)
            result = None
            if roi_name in layout.regions:
                x1, y1, x2, y2 = layout.normalized_roi(roi_name).pixel_bounds(width, height)
                result = structure_reference([image[y1:y2, x1:x2] for image in images])
            if result is None:
                diagnostics["references"][name] = {"status": "insufficient_evidence"}
                continue
            reference, bounds, stats = result
            asset = stage / "identity" / f"{name}.png"
            stats.update(_write_asset(asset, reference), status="generated")
            diagnostics["references"][name] = stats
            raw["signals"][name] = {
                "roi": roi_name,
                "roi_bounds": bounds,
                "template": f"identity/{name}.png",
                "threshold": 0.90,
            }
        name = "spectator_clear"
        result_clear = None
        if "spectated_player_panel" in layout.regions:
            x1, y1, x2, y2 = layout.normalized_roi("spectated_player_panel").pixel_bounds(
                width, height
            )
            result_clear = clear_reference([image[y1:y2, x1:x2] for image in images])
        if result_clear is not None:
            reference, stats = result_clear
            stats.update(
                _write_asset(stage / "identity/spectator_clear.png", reference), status="generated"
            )
            raw["spectator_clear_reference"] = {"template": "identity/spectator_clear.png"}
            diagnostics["references"][name] = stats
        else:
            if inherited._clear_reference is not None:
                asset = inherited.resolve_asset(raw["spectator_clear_reference"]["template"])
                reference = inherited._clear_reference
                diagnostics["references"][name] = {
                    "status": "inherited",
                    "content_hash": hashlib.sha256(asset.read_bytes()).hexdigest(),
                    "dimensions": [int(reference.shape[1]), int(reference.shape[0])],
                }
            else:
                raw.pop("spectator_clear_reference", None)
                diagnostics["references"][name] = {"status": "insufficient_evidence"}
        raw["automatic_identity_generation"] = diagnostics
        # Normalized entry-point names, directly accepted by -HudLayout.
        for old in (
            stage / layout_path.name,
            stage / layout_path.with_suffix(".templates.json").name,
        ):
            if old.exists() and old.name not in {"hud_layout.json", "hud_layout.templates.json"}:
                old.unlink()  # Only files generated in our disposable staging directory.
        shutil.copy2(layout_path, stage / "hud_layout.json")
        (stage / "hud_layout.templates.json").write_text(
            json.dumps(raw, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8"
        )
        (stage / "profile_diagnostics.json").write_text(
            json.dumps(diagnostics, indent=2, allow_nan=False) + "\n", encoding="utf-8"
        )
        stage.rename(output)
    return output / "hud_layout.json"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", required=True, type=Path)
    parser.add_argument("--layout", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--samples", type=int, default=32)
    args = parser.parse_args()
    try:
        print(create_profile(args.video, args.layout, args.output, samples=args.samples))
    except (OSError, ValueError, RuntimeError, cv2.error):
        parser.exit(
            2, "HUD profile生成に失敗しました。入力・依存ツール・診断条件を確認してください。\n"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

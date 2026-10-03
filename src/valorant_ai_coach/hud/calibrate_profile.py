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
from .spectator import PanelReference, generate_panel_reference, panel_components
from .templates import HudTemplateProfile
from .value_identity import MATCHER, scaffold_reference
from .weapon_consensus import MATCHER as WEAPON_MATCHER
from .weapon_consensus import persistent_reference
from .weapon_identity import weapon_reference

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
    diagnostics: dict[str, Any] | None = None,
) -> tuple[np.ndarray, list[float], dict[str, Any]] | None:
    """Mine a supported training cluster, then independently confirm its support.

    NCC >= .90 remains mandatory within a cluster. Other modes are not counted
    as failed matches. No cluster is assigned a gameplay-state label here.
    """
    diag = diagnostics if diagnostics is not None else {}
    diag.update(
        candidate_count=0,
        structural_rejected=0,
        support_rejected=0,
        holdout_rejected=0,
        training_count=len(crops[::2]),
        holdout_count=len(crops[1::2]),
    )
    if len(crops) < 16 or any(c.shape != crops[0].shape for c in crops):
        return None
    gray = [_gray(c) for c in crops]
    height, width = gray[0].shape
    h, w = max(16, round(height * 0.30)), max(16, round(width * 0.20))
    if h >= height or w >= width:
        return None
    candidates = []
    for y in np.linspace(0, height - h, 5).astype(int):
        for x in np.linspace(0, width - w, 5).astype(int):
            patches = [image[y : y + h, x : x + w] for image in gray]
            training = patches[::2]
            # Each seed defines a bounded candidate mode using training frames only.
            clusters = set()
            for seed in training:
                members = tuple(
                    i for i, patch in enumerate(training) if _score(seed, patch) >= 0.90
                )
                if len(members) >= 3:
                    clusters.add(members)
                else:
                    diag["support_rejected"] += 1
            for members in sorted(clusters):
                reference = np.median(np.stack([training[i] for i in members]), axis=0).astype(
                    np.uint8
                )
                diag["candidate_count"] += 1
                candidate = _structure_candidate(reference, training, members)
                if candidate is None:
                    diag["structural_rejected"] += 1
                    continue
                scores = [_score(reference, patch) for patch in training]
                matched = [s for s in scores if s >= 0.90]
                if (
                    len(matched) < 3
                    or sum(scores[i] >= 0.90 for i in members) / len(members) < 0.80
                ):
                    diag["support_rejected"] += 1
                    continue
                candidates.append(
                    (
                        len(matched) + float(np.median(matched)),
                        reference,
                        [x / width, y / height, (x + w) / width, (y + h) / height],
                        patches,
                        scores,
                    )
                )
    # Choose once on training only; never search holdout for a better-fitting ROI.
    if not candidates:
        return None
    _, reference, bounds, patches, train_scores = max(candidates, key=lambda item: item[0])
    heldout = [_score(reference, patch) for patch in patches[1::2]]
    train_support = sum(s >= 0.90 for s in train_scores)
    heldout_support = sum(s >= 0.90 for s in heldout)
    diag.update(training_accept_count=train_support, holdout_accept_count=heldout_support)
    # At least three independent observations per split, and comparable cluster
    # prevalence in holdout. This is not 80% of the entire mixed-state recording.
    expected = train_support / len(train_scores) * len(heldout)
    if heldout_support < 3 or heldout_support < 0.80 * expected:
        diag["holdout_rejected"] += 1
        return None
    diag["holdout_median"] = float(np.median([s for s in heldout if s >= 0.90]))
    return reference, bounds, dict(diag)


def _structure_candidate(
    reference: np.ndarray, training: list[np.ndarray], members: tuple[int, ...]
) -> bool | None:
    """Require persistent edges within the proposed mode, not a median ghost."""
    h, w = reference.shape
    edges = cv2.Canny(reference, 60, 150)
    density = float(np.count_nonzero(edges) / edges.size)
    if not 0.015 <= density <= 0.25 or float(reference.std()) < 8:
        return None
    lines = cv2.HoughLinesP(
        edges, 1, np.pi / 180, threshold=8, minLineLength=max(8, min(h, w) // 3), maxLineGap=2
    )
    if lines is None or len(lines) < 2:
        return None
    supports = []
    for i in members:
        observed = cv2.dilate(cv2.Canny(training[i], 60, 150), np.ones((3, 3), np.uint8))
        supports.append(float(np.mean(observed[edges > 0] > 0)))
    return True if min(supports) >= 0.90 else None


def clear_reference(crops: list[np.ndarray]) -> tuple[np.ndarray, dict[str, Any]] | None:
    """Legacy diagnostic helper only; not used by generation or runtime.

    Retained for comparison tests of the retired algorithm. Its result is not
    written to new profiles and cannot establish absence in HudTemplateProfile.
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
    structure_specs = json.loads(layout_path.read_text(encoding="utf-8")).get(
        "identity_structure_regions", {}
    )
    if layout.layout_format != "v3" or layout.reference_resolution is None:
        raise ValueError("v3の基準解像度付きlayoutが必要です")
    source_path = layout_path.with_suffix(".templates.json")
    source = HudTemplateProfile.load(source_path) if source_path.is_file() else None
    source_geometry_assets = _geometry_asset_paths(source) if source is not None else set()
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
            "version": 2,
            "sample_count": len(images),
            "geometry_mode": geometry_mode,
            "references": {},
        }
        raw.setdefault("signals", {})
        inherited = HudTemplateProfile(stage / "hud_layout.templates.json", raw)
        # Retain source geometry provenance even when new anchors replace it.
        geometry_assets = source_geometry_assets | _geometry_asset_paths(inherited)
        geometry_hashes = {
            hashlib.sha256(p.read_bytes()).hexdigest() for p in geometry_assets if p.is_file()
        }
        for name, roi_name in ROLES.items():
            persistent_weapon = (
                name == "weapon_ammo_structure"
                and structure_specs.get(name, {}).get("discovery") == "persistent_slots_v1"
            )
            wanted_matcher = WEAPON_MATCHER if persistent_weapon else MATCHER
            if name in inherited._signal_templates:
                inherited_roi, template = inherited._signal_templates[name]
                spec = inherited.raw["signals"][name]
                identity_assets = [template.path]
                for asset_key in ("mask", "support_regions", "allowed_regions"):
                    if asset_key in spec:
                        identity_assets.append(inherited.resolve_asset(spec[asset_key]))
                if (
                    all(
                        asset.resolve() not in geometry_assets
                        and hashlib.sha256(asset.read_bytes()).hexdigest() not in geometry_hashes
                        for asset in identity_assets
                    )
                    and (name not in structure_specs or spec.get("matcher") == wanted_matcher)
                    and inherited_roi == roi_name
                    and inherited_roi in layout.regions
                    and (
                        name != "weapon_ammo_structure"
                        or spec.get("matcher") in ("oriented_edges_v1", MATCHER, WEAPON_MATCHER)
                    )
                ):
                    diagnostics["references"][name] = {
                        "status": "inherited",
                        "content_hash": hashlib.sha256(template.path.read_bytes()).hexdigest(),
                        "dimensions": [int(template.image.shape[1]), int(template.image.shape[0])],
                    }
                    if name == "weapon_ammo_structure" and "mask" in spec:
                        diagnostics["references"][name].update(
                            matcher=spec.get("matcher", "masked_ncc"),
                            mask_presence=True,
                            mask_content_hash=hashlib.sha256(
                                inherited.resolve_asset(spec["mask"]).read_bytes()
                            ).hexdigest(),
                        )
                    continue
            # Invalid/missing assets and reused geometry are not independent evidence.
            raw["signals"].pop(name, None)
            result = None
            identity_mask = None
            identity_regions = None
            identity_allowed = None
            stats: dict[str, Any] = {}
            if roi_name in layout.regions:
                x1, y1, x2, y2 = layout.normalized_roi(roi_name).pixel_bounds(width, height)
                crops = [image[y1:y2, x1:x2] for image in images]
                if name in structure_specs:
                    neighbors = []
                    for other_name, other_roi in ROLES.items():
                        if other_name == name or other_roi not in layout.regions:
                            continue
                        nx1, ny1, nx2, ny2 = layout.normalized_roi(other_roi).pixel_bounds(
                            width, height
                        )
                        left, top, right, bottom = (
                            max(x1, nx1),
                            max(y1, ny1),
                            min(x2, nx2),
                            min(y2, ny2),
                        )
                        if left < right and top < bottom:
                            neighbors.append(
                                [
                                    (left - x1) / (x2 - x1),
                                    (top - y1) / (y2 - y1),
                                    (right - x1) / (x2 - x1),
                                    (bottom - y1) / (y2 - y1),
                                ]
                            )
                    if persistent_weapon:
                        consensus = persistent_reference(
                            crops, structure_specs[name], stats, neighbors
                        )
                        if consensus is not None:
                            reference, bounds, identity_mask, identity_regions, identity_allowed = (
                                consensus
                            )
                            result = reference, bounds, stats
                    else:
                        scaffold = scaffold_reference(
                            crops, structure_specs[name], stats, neighbors
                        )
                        if scaffold is not None:
                            reference, bounds, identity_mask, identity_regions = scaffold
                            result = reference, bounds, stats
                elif name == "weapon_ammo_structure":
                    weapon = weapon_reference(crops, stats)
                    if weapon is not None:
                        reference, bounds, identity_mask = weapon
                        result = reference, bounds, stats
                else:
                    result = structure_reference(crops, stats)
            if result is None:
                diagnostics["references"][name] = {**stats, "status": "insufficient_evidence"}
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
            if identity_mask is not None:
                mask_asset = stage / "identity" / f"{name}.mask.png"
                mask_stats = _write_asset(mask_asset, identity_mask)
                stats["mask_content_hash"] = mask_stats["content_hash"]
                stats["mask_presence"] = True
                raw["signals"][name]["mask"] = f"identity/{name}.mask.png"
                raw["signals"][name]["matcher"] = "oriented_edges_v1"
                stats["matcher"] = "oriented_edges_v1"
                if identity_regions is not None:
                    regions_asset = stage / "identity" / f"{name}.support.png"
                    region_stats = _write_asset(regions_asset, identity_regions)
                    raw["signals"][name]["support_regions"] = f"identity/{name}.support.png"
                    raw["signals"][name]["matcher"] = wanted_matcher
                    stats["matcher"] = wanted_matcher
                    if identity_allowed is not None:
                        allowed_asset = stage / "identity" / f"{name}.allowed.png"
                        allowed_stats = _write_asset(allowed_asset, identity_allowed)
                        raw["signals"][name]["allowed_regions"] = f"identity/{name}.allowed.png"
                        stats["allowed_content_hash"] = allowed_stats["content_hash"]
                    stats["support_content_hash"] = region_stats["content_hash"]
        # Never inherit or generate background/clear-image evidence.
        raw.pop("spectator_clear_reference", None)
        raw.pop("spectator_panel_detector", None)
        if "spectator_icon" in layout.regions:
            raw["spectator_icon_detector"] = {
                "version": 1,
                "roi": "spectator_icon",
                "method": "fixed_slot_structure_v1",
            }
            raw.get("signals", {}).pop("spectated_player_panel", None)
            diagnostics["references"]["spectator_panel"] = {
                "status": "generated",
                "matcher": "fixed_slot_structure_v1",
                "reference_required": False,
                "candidate_count": 0,
            }
        else:
            raw.pop("spectator_icon_detector", None)
            name = "spectator_panel"
            labels = None
            stats = {}
            if "spectated_player_panel" in layout.regions:
                x1, y1, x2, y2 = layout.normalized_roi("spectated_player_panel").pixel_bounds(
                    width, height
                )
                labels = generate_panel_reference([image[y1:y2, x1:x2] for image in images], stats)
            status = "generated"
            if labels is None and inherited._panel_components is not None:
                spec = inherited.raw.get("spectator_panel_detector", {})
                assets = [
                    inherited.resolve_asset(spec[key]).resolve()
                    for key in ("template", "support_regions", "orientation")
                    if key in spec
                ]
                roi_name = "spectated_player_panel"
                if roi_name in layout.regions and all(
                    asset not in geometry_assets
                    and hashlib.sha256(asset.read_bytes()).hexdigest() not in geometry_hashes
                    for asset in assets
                ):
                    x1, y1, x2, y2 = layout.normalized_roi(roi_name).pixel_bounds(width, height)
                    if inherited._panel_components.shape == (y2 - y1, x2 - x1):
                        labels = inherited._panel_components.copy()
                        status = "inherited"
            if labels is None and "spectated_player_panel" in inherited._signal_templates:
                roi_name, template = inherited._signal_templates["spectated_player_panel"]
                if (
                    roi_name == "spectated_player_panel"
                    and roi_name in layout.regions
                    and template.path.resolve() not in geometry_assets
                    and hashlib.sha256(template.path.read_bytes()).hexdigest()
                    not in geometry_hashes
                ):
                    x1, y1, x2, y2 = layout.normalized_roi(roi_name).pixel_bounds(width, height)
                    if template.image.shape == (y2 - y1, x2 - x1):
                        labels = panel_components(template.image)
                        status = "inherited"
            if labels is not None:
                stats.update(
                    _write_asset(stage / "identity/spectator_panel.components.png", labels),
                    status=status,
                )
                raw["spectator_panel_detector"] = {
                    "version": 1,
                    "template": "identity/spectator_panel.components.png",
                }
                if isinstance(labels, PanelReference):
                    raw["spectator_panel_detector"]["version"] = 2
                    for key, image in (
                        ("support_regions", labels.regions),
                        ("orientation", labels.orientation),
                    ):
                        asset_name = f"identity/spectator_panel.{key}.png"
                        info = _write_asset(stage / asset_name, image)
                        raw["spectator_panel_detector"][key] = asset_name
                        stats[f"{key}_content_hash"] = info["content_hash"]
                diagnostics["references"][name] = stats
            else:
                diagnostics["references"][name] = {**stats, "status": "insufficient_evidence"}
        diagnostics["identity_reference_ready"] = all(
            diagnostics["references"][role]["status"] in {"generated", "inherited"}
            for role in (*ROLES, "spectator_panel")
        )
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


def _geometry_asset_paths(profile: HudTemplateProfile) -> set[Path]:
    return {
        profile.resolve_asset(spec[key]).resolve()
        for spec in profile.raw.get("anchors", {}).values()
        if isinstance(spec, dict)
        for key in ("template", "mask")
        if isinstance(spec.get(key), str)
    }


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

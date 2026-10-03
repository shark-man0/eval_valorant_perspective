"""Create local geometry-anchor candidates from unlabelled video frames.

Temporal persistence is only a candidate generator. Runtime calibration still
has to verify any resulting geometry, and this module creates no identity data.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import cv2
import numpy as np

from valorant_ai_coach.video.service import VideoService

from .layout import HudLayout
from .templates import HudTemplateProfile

ANCHORS = ("round_timer", "top_match_bar", "player_hp_armor", "abilities")


def _localize_assets(value: Any, base: Path) -> Any:
    """Make inherited template references stable without copying user assets."""
    keys = {
        "template", "mask", "support", "evidence", "templates", "values",
        "available_template", "unavailable_template",
    }
    if isinstance(value, dict):
        return {
            key: _localize_assets(child, base) if key not in keys else _asset_value(child, base)
            for key, child in value.items()
        }
    if isinstance(value, list):
        return [_localize_assets(child, base) for child in value]
    return value


def _asset_value(value: Any, base: Path) -> Any:
    if isinstance(value, str):
        path = Path(value).expanduser()
        return str((path if path.is_absolute() else base / path).resolve())
    if isinstance(value, dict):
        return {key: _asset_value(child, base) for key, child in value.items()}
    return value


def _check_output_privacy(output: Path) -> None:
    """Within a checkout, require git to confirm the target is ignored."""
    probe = output.parent
    while not probe.exists() and probe != probe.parent:
        probe = probe.parent
    try:
        root = Path(
            subprocess.run(
                ["git", "-C", str(probe), "rev-parse", "--show-toplevel"],
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
        ).resolve()
    except (OSError, subprocess.CalledProcessError):
        if any((parent / ".git").exists() for parent in (probe, *probe.parents)):
            raise ValueError("Git ignoreを確認できないためリポジトリ内へは出力しません") from None
        return  # Outside a discoverable repository.
    try:
        output.relative_to(root)
    except ValueError:
        return
    ignored = (
        subprocess.run(
            ["git", "-C", str(root), "check-ignore", "--quiet", str(output)],
            check=False,
        ).returncode
        == 0
    )
    if not ignored:
        raise ValueError("リポジトリ内の出力先はgitでignoreされたoutputs配下にしてください")


def _candidate(frames: list[np.ndarray]) -> tuple[np.ndarray, np.ndarray, float] | None:
    if len(frames) < 8 or any(frame.shape != frames[0].shape for frame in frames):
        return None
    gray = np.stack([cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) for frame in frames])
    median = np.median(gray, axis=0).astype(np.uint8)
    variability = np.std(gray.astype(np.float32), axis=0)
    edges = np.stack([cv2.Canny(frame, 60, 150) > 0 for frame in gray])
    persistence = edges.mean(axis=0)
    mask = ((variability <= 12.0) & (persistence >= 0.65)).astype(np.uint8) * 255
    selected = median[mask > 0]
    ratio = float(selected.size / mask.size)
    if selected.size < 64 or float(selected.std()) < 1.0:
        return None
    return median, mask, ratio


def create_temporal_profile(
    video: Path,
    layout_path: Path,
    output_dir: Path,
    *,
    samples: int = 24,
    video_service: VideoService | None = None,
) -> Path:
    if not 8 <= samples <= 64:
        raise ValueError("samplesは8〜64で指定してください")
    video = Path(video).expanduser().resolve()
    layout_path = Path(layout_path).expanduser().resolve()
    output = Path(output_dir).expanduser().resolve()
    if output.exists():
        raise FileExistsError(f"出力先は新しいフォルダーを指定してください: {output}")
    _check_output_privacy(output)

    layout = HudLayout.load(layout_path)
    if layout.layout_format != "v3" or layout.reference_resolution is None:
        raise ValueError("v3レイアウトとreference_resolutionが必要です")
    service = video_service or VideoService()
    metadata = service.probe(video)
    if metadata.duration_sec <= 0:
        raise ValueError("動画の長さを取得できません")
    times = np.linspace(0, metadata.duration_sec, samples + 2)[1:-1].tolist()
    output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=".hud-temporal-", dir=output.parent) as temp:
        temp_path = Path(temp)
        frame_dir = temp_path / "frames"
        extracted = service.extract_frames(
            video,
            times,
            frame_dir,
            max_frames=64,
            max_dimension=None,
            metadata=metadata,
        )
        if len(extracted) < 8:
            raise ValueError("解析可能なフレームが8枚未満です")
        decoded = [
            cv2.imdecode(np.frombuffer(item.path.read_bytes(), np.uint8), cv2.IMREAD_COLOR)
            for item in extracted
        ]
        if any(image is None for image in decoded):
            raise ValueError("一部の抽出フレームを読み込めません")
        images = [image for image in decoded if image is not None]
        width, height = layout.reference_resolution
        if images[0].shape[:2] != (height, width):
            raise ValueError("動画の解像度とレイアウト基準解像度が一致しません")

        staging = temp_path / "profile"
        staging.mkdir()
        asset_dir = staging / "anchors"
        asset_dir.mkdir()
        valid: dict[str, dict[str, Any]] = {}
        summaries: dict[str, dict[str, Any]] = {}
        asset_digest = hashlib.sha256()
        for name in ANCHORS:
            if name not in layout.regions:
                continue
            roi = layout.normalized_roi(name)
            x1, y1, x2, y2 = roi.pixel_bounds(width, height)
            patches = [image[y1:y2, x1:x2] for image in images]
            candidate = _candidate(patches)
            if candidate is None:
                summaries[name] = {"selected_pixels": 0, "selected_ratio": 0.0, "valid": False}
                continue
            template, mask, ratio = candidate
            template_path, mask_path = asset_dir / f"{name}.png", asset_dir / f"{name}.mask.png"
            for target, pixels in ((template_path, template), (mask_path, mask)):
                ok, encoded = cv2.imencode(".png", pixels)
                if not ok:
                    raise OSError("アンカー画像を保存できません")
                target.write_bytes(encoded.tobytes())
            asset_digest.update(template_path.read_bytes())
            asset_digest.update(mask_path.read_bytes())
            search_region = [
                max(0, roi.x - 0.06),
                max(0, roi.y - 0.06),
                min(1, roi.right + 0.06),
                min(1, roi.bottom + 0.06),
            ]
            valid[name] = {
                "template": f"anchors/{name}.png",
                "mask": f"anchors/{name}.mask.png",
                "search_region": search_region,
                "threshold": 0.90,
            }
            summaries[name] = {
                "selected_pixels": int(np.count_nonzero(mask)),
                "selected_ratio": round(ratio, 6),
                "valid": True,
            }
        if len(valid) < 3:
            raise ValueError("有効な幾何アンカーが3個未満です")

        source_profile_path = layout_path.with_name(f"{layout_path.stem}.templates.json")
        inherited: dict[str, Any] = {"schema_version": "1.0", "anchors": {}, "readers": {}}
        if source_profile_path.is_file():
            inherited = HudTemplateProfile.load(source_profile_path).raw
            inherited = _localize_assets(inherited, source_profile_path.parent)
        profile = dict(inherited)
        profile["schema_version"] = "1.0"
        inherited_anchors = profile.get("anchors", {})
        for name, spec in valid.items():
            previous = (
                inherited_anchors.get(name, {}) if isinstance(inherited_anchors, dict) else {}
            )
            try:
                previous_threshold = float(previous.get("threshold", 0.90))
            except (AttributeError, TypeError, ValueError):
                raise ValueError("既存anchorのthresholdが不正です") from None
            if not math.isfinite(previous_threshold) or not 0 <= previous_threshold <= 1:
                raise ValueError("既存anchorのthresholdが不正です")
            spec["threshold"] = max(0.90, previous_threshold)
        profile["anchors"] = {**inherited_anchors, **valid}
        profile.setdefault("readers", {})
        # Geometry candidates must never manufacture identity or semantic signals.
        profile["signals"] = inherited.get("signals", {})
        stats = {
            "sample_count": len(images),
            "anchor_count": len(valid),
            "anchors": summaries,
            "generated_assets_sha256": asset_digest.hexdigest(),
        }
        profile["temporal_generation"] = stats
        layout_dest = staging / layout_path.name
        shutil.copy2(layout_path, layout_dest)
        profile_path = layout_dest.with_name(f"{layout_dest.stem}.templates.json")
        profile_path.write_text(
            json.dumps(profile, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        (staging / "temporal_stats.json").write_text(
            json.dumps(stats, indent=2) + "\n", encoding="utf-8"
        )
        staging.rename(output)
    return output / layout_path.name


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", required=True, type=Path)
    parser.add_argument("--layout", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--samples", type=int, default=24)
    args = parser.parse_args()
    try:
        print(create_temporal_profile(args.video, args.layout, args.output, samples=args.samples))
    except (OSError, ValueError, TypeError, RuntimeError) as exc:
        parser.exit(1, f"時系列アンカー候補を生成できません: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

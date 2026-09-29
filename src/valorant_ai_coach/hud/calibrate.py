"""Create an editable anchor profile from an unannotated reference screenshot.

This exports reference pixels, not a claim of validated detection accuracy.
The resulting layout must still pass runtime geometric/template checks.
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from tempfile import TemporaryDirectory

import cv2
import numpy as np

from valorant_ai_coach.resources import resource_path

from .layout import HudLayout
from .readers import load_frame
from .templates import _bounds


def create_anchor_profile(
    layout_path: Path, screenshot: Path, output_dir: Path,
    *, anchor_regions: dict[str, list[list[float]]] | None = None,
) -> Path:
    layout = HudLayout.load(layout_path)
    image = load_frame(screenshot)
    height, width = image.shape[:2]
    if layout.layout_format != "v3" or layout.reference_resolution != (width, height):
        raise ValueError("v3レイアウトの基準解像度と同じ未加工スクリーンショットが必要です")
    output_dir = output_dir.expanduser().resolve()
    if output_dir.exists():
        raise FileExistsError(f"出力先は新しいフォルダーを指定してください: {output_dir}")
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    required = (layout.calibration_policy or {}).get("required_anchors", [])
    if len(required) < 3:
        raise ValueError("レイアウトには3個以上の校正アンカーが必要です")
    if anchor_regions is not None and (
        not isinstance(anchor_regions, dict) or set(anchor_regions) - set(required)
    ):
        raise ValueError("anchor_regionsには校正アンカー名を指定してください")
    with TemporaryDirectory(prefix=".hud-calibration-", dir=output_dir.parent) as temporary:
        staging = Path(temporary) / "profile"
        staging.mkdir()
        assets = staging / "anchors"
        assets.mkdir()
        anchors = {}
        for name in required:
            roi = layout.normalized_roi(name)
            x1, y1, x2, y2 = roi.pixel_bounds(width, height)
            crop = image[y1:y2, x1:x2]
            if float(cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY).std()) < 1.0:
                raise ValueError(f"校正アンカーの画像情報が不足しています: {name}")
            asset = assets / f"{name}.png"
            if not cv2.imwrite(str(asset), crop):
                raise OSError(f"校正画像を保存できません: {asset}")
            anchors[name] = {
                "template": f"anchors/{name}.png",
                "search_region": [
                    max(0, roi.x - 0.06),
                    max(0, roi.y - 0.06),
                    min(1, roi.right + 0.06),
                    min(1, roi.bottom + 0.06),
                ],
                "threshold": 0.90,
            }
            if anchor_regions is not None and name in anchor_regions:
                mask = np.zeros(crop.shape[:2], dtype=np.uint8)
                if not isinstance(anchor_regions[name], list):
                    raise ValueError("anchor_regionsの値は矩形の配列で指定してください")
                for bounds in anchor_regions[name]:
                    left, top, right, bottom = _bounds(bounds)
                    h, w = mask.shape
                    mask[round(top * h):round(bottom * h),
                         round(left * w):round(right * w)] = 255
                selected = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)[mask > 0]
                if selected.size < 64 or float(selected.std()) < 1.0:
                    raise ValueError(f"校正マスクの画像情報が不足しています: {name}")
                mask_path = assets / f"{name}.mask.png"
                if not cv2.imwrite(str(mask_path), mask):
                    raise OSError(f"校正マスクを保存できません: {mask_path}")
                anchors[name]["mask"] = f"anchors/{name}.mask.png"
        shutil.copy2(layout_path, staging / "hud_layout.json")
        profile = {
            "schema_version": "1.0",
            "anchors": anchors,
            "readers": {},
            "notes": [
                "未加工の通常一人称スクリーンショットから抽出した参照画素です。",
                "異なる録画で検証し、数字・アイコンreaderを追加してください。",
            ],
        }
        (staging / "hud_layout.templates.json").write_text(
            json.dumps(profile, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        staging.rename(output_dir)
    return output_dir / "hud_layout.json"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("screenshot", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--layout", type=Path, default=None)
    parser.add_argument("--anchor-regions", type=Path, default=None,
                        help="JSON: anchor name -> list of normalized ROI-internal rectangles")
    args = parser.parse_args()
    try:
        result = create_anchor_profile(
            args.layout or resource_path("config/hud_layout_1080p_v3.json"),
            args.screenshot,
            args.output_dir,
            anchor_regions=(json.loads(args.anchor_regions.read_text(encoding="utf-8"))
                            if args.anchor_regions else None),
        )
    except (OSError, ValueError, TypeError) as exc:
        parser.exit(1, f"校正プロファイルを生成できません: {exc}\n")
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

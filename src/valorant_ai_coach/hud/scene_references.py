"""Shared reviewed-reference assets and image-supported source acquisition.

The portable profile remains explicitly unqualified. Asset hash, decoded pixels,
relative paths, reviewed crops and provenance are validated before use. Reference
ambiguity is withheld rather than selecting a favorable score. No source history,
world mask, lifecycle event or runtime proof is created by these classes.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, cast

import cv2

from .scene_domains import (
    Boxes,
    ImageU8,
    _spread,
    _validate,
    canonical_scene_image,
    domain_displacement_audit,
    joint_domain_audit,
)
from .scene_reference_matching import (
    measure_reference_support,
    reviewed_patches,
    search_reviewed_world,
)


def scene_asset_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class WorldLandmarkBootstrap:
    def __init__(
        self,
        profile_path: Path | str,
        *,
        profile_scope: str = "diagnostic_landmarks_only",
    ) -> None:
        path = Path(profile_path)
        profile = json.loads(path.read_bytes())
        if profile_scope not in {"diagnostic_landmarks_only", "diagnostic_reviewed_domains"}:
            raise ValueError("known diagnostic profile scope required")
        if set(profile) != {"schema_version", "scope", "references"} or (
            profile["schema_version"] != 1 or profile["scope"] != profile_scope
        ):
            raise ValueError(
                "diagnostic-only landmark profile with no runtime qualification required"
            )
        self.profile_sha256 = scene_asset_sha256(path)
        self.references: list[dict[str, Any]] = []
        identifiers = set()
        for entry in profile["references"]:
            if (
                set(entry)
                != {
                    "id",
                    "asset",
                    "asset_sha256",
                    "source_pixel_sha256",
                    "world_boxes_640x360",
                    "review_provenance",
                }
                or not isinstance(entry["review_provenance"], str)
                or not entry["review_provenance"].strip()
            ):
                raise ValueError("explicit reviewed image reference fields required")
            if not isinstance(entry["id"], str) or not entry["id"] or entry["id"] in identifiers:
                raise ValueError("unique reference identifier required")
            identifiers.add(entry["id"])
            relative = Path(entry["asset"])
            asset = (path.parent / relative).resolve()
            if relative.is_absolute() or not asset.is_relative_to(path.parent.resolve()):
                raise ValueError("profile-relative reference asset required")
            if scene_asset_sha256(asset) != entry["asset_sha256"]:
                raise ValueError("reviewed asset bytes changed")
            native = cv2.imread(str(asset))
            if (
                native is None
                or hashlib.sha256(native.tobytes()).hexdigest() != entry["source_pixel_sha256"]
            ):
                raise ValueError("reviewed asset pixels changed")
            boxes = tuple(tuple(box) for box in entry["world_boxes_640x360"])
            if any(len(box) != 4 or any(type(v) is not int for v in box) for box in boxes):
                raise ValueError("integral reviewed world boxes required")
            if len(boxes) < 3 or len(set(boxes)) != len(boxes):
                raise ValueError("three unique world regions required")
            image = canonical_scene_image(native)
            _validate(image, boxes)
            self.references.append(
                {
                    "id": entry["id"],
                    "image": image,
                    "boxes": boxes,
                    "patches": reviewed_patches(image, boxes),
                }
            )
        if not self.references:
            raise ValueError("nonempty reviewed reference bank required")

    def recognize(self, current: ImageU8) -> dict[str, Any]:
        candidates = []
        for reference in self.references:
            _validate(current, reference["boxes"])
            rejection: list[dict[str, Any]] = []
            metrics, tracks = search_reviewed_world(
                reference["image"],
                current,
                reference["boxes"],
                patches=reference["patches"],
                rejection_sink=rejection,
            )
            linked = [t for t in tracks if t["model_inlier"]]
            regions = {t["region"] for t in linked}
            coherent = (
                len(linked) >= 0.90 * len(tracks)
                and len(tracks) >= 3
                and len(regions) >= 3
                and _spread([t["reference_xy"] for t in linked])
                and _spread([t["current_xy"] for t in linked])
            )
            candidates.append(
                {
                    "reference_id": reference["id"],
                    "single_frame_landmark_quorum": coherent,
                    "metrics": metrics,
                    "linked_landmarks": linked,
                    "rejections": rejection,
                    "world_scope": "matched_reference_patches_only",
                    "whole_roi_world_attested": False,
                    "runtime_proof_authorized": False,
                }
            )
        return {
            "profile_sha256": self.profile_sha256,
            "single_frame_landmark_quorum": any(
                c["single_frame_landmark_quorum"] for c in candidates
            ),
            "references": candidates,
            "world_scope": "matched_reference_patches_only",
            "whole_roi_world_attested": False,
            "runtime_proof_authorized": False,
            "qualification_created": False,
        }


class WorldDomainBootstrap:
    def __init__(self, profile_path: Path | str) -> None:
        self.references = WorldLandmarkBootstrap(
            profile_path, profile_scope="diagnostic_reviewed_domains"
        )

    def recognize(
        self,
        current: ImageU8,
        *,
        current_search_boxes: Boxes | None = None,
    ) -> dict[str, Any]:
        proposals = []
        for reference in self.references.references:
            if current_search_boxes is None:
                metrics = measure_reference_support(reference["image"], current, reference["boxes"])
            else:
                metrics, _ = search_reviewed_world(
                    reference["image"],
                    current,
                    reference["boxes"],
                    current_boxes=current_search_boxes,
                )
            model = metrics["reference_to_current_affine"]
            coherent = (
                model is not None
                and metrics["accepted_reference_tracks"] >= 3
                and len(metrics["track_regions"]) >= 3
                and metrics["model_inliers"] >= 0.90 * metrics["accepted_reference_tracks"]
            )
            joint, domains = None, None
            if coherent:
                measurements: list[dict[str, Any]] = []
                domains = domain_displacement_audit(
                    reference["image"],
                    current,
                    reference["boxes"],
                    model,
                    offset_sink=measurements,
                    allowed_current_boxes=current_search_boxes,
                )
                joint = joint_domain_audit(reference["boxes"], model, measurements)
            proposals.append(
                {
                    "reference_id": reference["id"],
                    "source_model_coherent": coherent,
                    "reference_tracks": metrics["accepted_reference_tracks"],
                    "reference_model_inliers": metrics["model_inliers"],
                    "reference_to_current_affine": model,
                    "domains": domains,
                    "joint": joint,
                    "diagnostic_initialization_proposed": bool(
                        coherent and cast(dict[str, Any], joint)["locally_unique_joint_appearance"]
                    ),
                    "reference_is_observed_previous_frame": False,
                }
            )
        # Competing reference proposals are withheld; no score-based selection.
        supported = [p for p in proposals if p["diagnostic_initialization_proposed"]]
        result: dict[str, Any] = {
            "profile_sha256": self.references.profile_sha256,
            "proposals": proposals,
            "diagnostic_initialization_proposed": len(supported) == 1,
            "reference_ambiguity": len(supported) > 1,
            "scope": "matched reviewed reference-domain appearance; local hypothesis scope only",
            "reference_is_observed_previous_frame": False,
            "whole_roi_world_attested": False,
            "runtime_proof_authorized": False,
            "qualification_created": False,
        }
        if current_search_boxes is not None:
            result["acquisition_method"] = "unique_reciprocal_displaced_patch_search"
            result["current_search_boxes_640x360"] = [list(box) for box in current_search_boxes]
        return result

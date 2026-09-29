"""Conservative CV measurements; appearance proposals are not gameplay facts."""

from __future__ import annotations

import math
from typing import Any

import cv2
import numpy as np
from numpy.typing import NDArray

from valorant_ai_coach.video.geometry import normalized_roi_bounds

from .remote import classify_remote_view

Image = NDArray[Any]


def _roi(
    image: Image, profile: dict[str, Any], name: str
) -> tuple[Image, tuple[int, int, int, int]]:
    height, width = image.shape[:2]
    coordinates = profile.get("rois", {}).get(name, [0, 0, 1, 1])
    bounds = normalized_roi_bounds(coordinates, width, height)
    if bounds is None:
        raise ValueError(f"Invalid normalized Visual ROI: {name}")
    x1, y1, x2, y2 = bounds
    return image[y1:y2, x1:x2], (x1, y1, x2, y2)


def _components(
    image: Image,
    spec: dict[str, Any],
    *,
    excluded_regions: tuple[tuple[int, int, int, int], ...] = (),
) -> list[tuple[int, int, int, int]]:
    if not spec or "lower" not in spec or "upper" not in spec:
        return []
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, np.array(spec["lower"], np.uint8), np.array(spec["upper"], np.uint8))
    for x1, y1, x2, y2 in excluded_regions:
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(mask.shape[1], x2), min(mask.shape[0], y2)
        if x1 < x2 and y1 < y2:
            mask[y1:y2, x1:x2] = 0
    count, _, stats, _ = cv2.connectedComponentsWithStats(mask)
    minimum = int(spec.get("min_area_px", 8))
    return [
        (int(stats[i, 0]), int(stats[i, 1]), int(stats[i, 2]), int(stats[i, 3]))
        for i in range(1, count)
        if minimum <= stats[i, 4] <= image.shape[0] * image.shape[1] * 0.25
    ]


class PixelMeasurementExtractor:
    def __init__(self) -> None:
        self.previous_entities: list[dict[str, Any]] = []
        self.next_id = 0
        self.previous_position: tuple[float, float] | None = None
        self.templates: dict[str, Image] = {}
        self.previous_cover_score = 0.0
        self.normal_seen: set[str] = set()
        self.absent_since: dict[str, float] = {}

    def _template_score(
        self, image: Image, path: str | None
    ) -> tuple[float, tuple[int, int] | None]:
        if not path:
            return 0.0, None
        if path not in self.templates:
            template = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
            if template is None or float(template.std()) < 1:
                return 0.0, None
            self.templates[path] = template
        template = self.templates[path]
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        if template.shape[0] > gray.shape[0] or template.shape[1] > gray.shape[1]:
            return 0.0, None
        scores = cv2.matchTemplate(gray, template, cv2.TM_CCOEFF_NORMED)
        _, score, _, location = cv2.minMaxLoc(scores)
        return max(0.0, min(1.0, score)), (
            location[0] + template.shape[1] // 2,
            location[1] + template.shape[0] // 2,
        )

    def measure(
        self,
        frame: Image,
        previous_frame: Image | None,
        hud: dict[str, Any],
        previous_hud: dict[str, Any] | None = None,
        *,
        profile: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        profile = profile or {}
        calibration = bool(profile.get("validated", False))
        height, width = frame.shape[:2]
        values, quality = hud.get("values", {}), hud.get("quality", {})
        prior = (previous_hud or {}).get("values", {})
        dt = float(hud.get("time_sec", 0)) - float((previous_hud or hud).get("time_sec", 0))
        contiguous = (
            previous_frame is not None and previous_frame.shape == frame.shape and 0 < dt <= 0.3
        )
        if not contiguous:
            self.previous_entities, self.previous_position = [], None
        world, world_bounds = _roi(frame, profile, "world")
        gray = cv2.resize(cv2.cvtColor(world, cv2.COLOR_BGR2GRAY), (320, 180))
        camera_score = None
        stationary_confidence = 0.0
        motion_state = "unknown"
        recoil = muzzle = 0.0
        flow_confidence = 0.0
        translation_confidence = bob_confidence = 0.0
        motion_sources: list[str] = []
        if contiguous:
            assert previous_frame is not None
            old_world, _ = _roi(previous_frame, profile, "world")
            old_gray = cv2.resize(cv2.cvtColor(old_world, cv2.COLOR_BGR2GRAY), (320, 180))
            flow = cv2.calcOpticalFlowFarneback(
                old_gray, gray, np.zeros((*gray.shape, 2), np.float32), 0.5, 3, 15, 3, 5, 1.2, 0
            )
            magnitude = np.linalg.norm(flow, axis=2)
            camera_score = min(1.0, float(np.median(magnitude)) / 10)
            texture = float(cv2.Laplacian(gray, cv2.CV_32F).var())
            if texture > 30 and float(np.quantile(magnitude, 0.9)) < 0.15:
                motion_state, stationary_confidence = "stationary", 0.86
                motion_sources = ["global_optical_flow"]
            # Flow alone cannot reliably separate camera yaw from translation.
            # Non-zero motion therefore remains unknown, not automatically moving.
            flow_confidence = stationary_confidence
            weapon, _ = _roi(frame, profile, "weapon")
            old_weapon, _ = _roi(previous_frame, profile, "weapon")
            delta = cv2.absdiff(weapon, old_weapon)
            # Uncalibrated brightness/recoil are redundant *triggers*, capped below acceptance.
            recoil = min(0.64, float(delta.mean()) / 35)
            bright = cv2.cvtColor(weapon, cv2.COLOR_BGR2GRAY)
            old_bright = cv2.cvtColor(old_weapon, cv2.COLOR_BGR2GRAY)
            muzzle = min(0.64, float(np.mean((bright > 230) & (old_bright < 160))) * 15)
            if calibration and texture > 30 and dt <= 0.1 and "weapon" in profile.get("rois", {}):
                # Fit global camera similarity; widespread residual parallax plus
                # independent weapon-region bob is required. This is not preaim reconstruction.
                ys, xs = np.mgrid[8:180:12, 8:320:12]
                points = np.column_stack((xs.ravel(), ys.ravel())).astype(np.float32)
                vectors = flow[ys, xs].reshape(-1, 2)
                transform, _ = cv2.estimateAffinePartial2D(
                    points, points + vectors, method=cv2.RANSAC
                )
                if transform is not None:
                    predicted = points @ transform[:, :2].T + transform[:, 2]
                    residual = np.linalg.norm(points + vectors - predicted, axis=1)
                    shift, response = cv2.phaseCorrelate(
                        cv2.resize(old_bright, (160, 90)).astype(np.float32),
                        cv2.resize(bright, (160, 90)).astype(np.float32),
                    )
                    if (
                        float(np.mean(residual > 1)) > 0.5
                        and 0.5 < abs(shift[1]) < 8
                        and response > 0.7
                        and recoil < 0.5
                    ):
                        motion_state, flow_confidence = "moving", 0.88
                        translation_confidence = bob_confidence = 0.88
                        motion_sources = ["global_optical_flow", "weapon_bob"]
        muzzle_template, _ = self._template_score(world, profile.get("muzzle_template"))
        if calibration and contiguous and muzzle_template >= 0.9:
            assert previous_frame is not None
            old_world, _ = _roi(previous_frame, profile, "world")
            old_muzzle, _ = self._template_score(old_world, profile.get("muzzle_template"))
            if old_muzzle < 0.6:
                muzzle = muzzle_template
        ammo, old_ammo = values.get("ammo_current"), prior.get("ammo_current")
        ammo_delta = (
            ammo - old_ammo if contiguous and type(ammo) is int and type(old_ammo) is int else None
        )
        weapon_changed = bool(
            prior.get("weapon_text")
            and values.get("weapon_text")
            and prior["weapon_text"] != values["weapon_text"]
        )
        reload_detected = ammo_delta is not None and ammo_delta > 0
        hud_confidence = float(quality.get("hud_confidence", 0))
        ammo_confidence = min(
            hud_confidence, float((previous_hud or {}).get("quality", {}).get("hud_confidence", 0))
        )
        weapon_known = bool(values.get("weapon_text") and prior.get("weapon_text"))
        action_conf = max(
            muzzle, recoil, ammo_confidence if weapon_known and ammo_delta is not None else 0
        )
        crosshair_score, crosshair_point = self._template_score(
            frame, profile.get("crosshair_template")
        )
        crosshair = (
            (crosshair_point[0] / width, crosshair_point[1] / height)
            if crosshair_point and crosshair_score >= 0.9
            else (0.5, 0.5)
        )
        # A center default is a coordinate convention, not evidence of detected crosshair.
        aiming = {
            "crosshair_x_norm": crosshair[0],
            "crosshair_y_norm": crosshair[1],
            "crosshair_stable": stationary_confidence >= 0.85 if crosshair_score >= 0.9 else None,
            "confidence": crosshair_score if calibration else min(0.64, crosshair_score),
        }
        corner_score, corner = self._template_score(frame, profile.get("corner_template"))
        if (
            calibration
            and corner
            and corner_score >= 0.9
            and crosshair_score >= 0.9
            and math.dist((corner[0] / width, corner[1] / height), crosshair) <= 0.03
        ):
            aiming.update(
                reference_mode="static_corner_reference",
                confidence=min(corner_score, crosshair_score),
            )
        cover_score, _ = self._template_score(world, profile.get("cover_template"))
        revealed_score, _ = self._template_score(world, profile.get("revealed_region_template"))
        cover_transition = (
            calibration and contiguous and self.previous_cover_score >= 0.9 and cover_score < 0.4
        )
        returned_cover = (
            calibration and contiguous and self.previous_cover_score < 0.4 and cover_score >= 0.9
        )
        prior_cover = self.previous_cover_score
        self.previous_cover_score = cover_score
        entities: list[dict[str, Any]] = []
        assigned_ids: set[str] = set()
        excluded_regions = []
        for name in ("minimap", "weapon"):
            if name not in profile.get("rois", {}):
                continue
            _, (x1, y1, x2, y2) = _roi(frame, profile, name)
            wx1, wy1, wx2, wy2 = world_bounds
            overlap = (
                max(0, x1 - wx1),
                max(0, y1 - wy1),
                min(world.shape[1], x2 - wx1),
                min(world.shape[0], y2 - wy1),
            )
            if overlap[0] < overlap[2] and overlap[1] < overlap[3]:
                excluded_regions.append(overlap)
        world_x, world_y = world_bounds[:2]
        for side in ("enemy", "ally"):
            for x, y, w, h in _components(
                world,
                profile.get("outline_colors_hsv", {}).get(side, {}),
                excluded_regions=tuple(excluded_regions),
            ):
                full_x, full_y = x + world_x, y + world_y
                box = [
                    full_x / width,
                    full_y / height,
                    (full_x + w) / width,
                    (full_y + h) / height,
                ]
                center = ((box[0] + box[2]) / 2, (box[1] + box[3]) / 2)
                matches = [
                    item
                    for item in self.previous_entities
                    if item["outline_side"] == side
                    and item["detection_id"] not in assigned_ids
                    and math.dist(
                        center,
                        (
                            (item["bbox_norm"][0] + item["bbox_norm"][2]) / 2,
                            (item["bbox_norm"][1] + item["bbox_norm"][3]) / 2,
                        ),
                    )
                    < 0.04
                ]
                identifier = (
                    matches[0]["detection_id"] if len(matches) == 1 else f"entity-{self.next_id}"
                )
                self.next_id += 1
                assigned_ids.add(identifier)
                body_score, _ = self._template_score(
                    world[y : y + h, x : x + w], profile.get(f"{side}_body_template")
                )
                head_score, head = self._template_score(
                    world[y : y + h, x : x + w], profile.get(f"{side}_head_template")
                )
                conf = body_score if calibration and body_score >= 0.9 else 0.6
                entities.append(
                    {
                        "detection_id": identifier,
                        "bbox_norm": box,
                        "head_point_norm": [
                            (full_x + head[0]) / width,
                            (full_y + head[1]) / height,
                        ]
                        if head is not None and head_score >= 0.9 and calibration
                        else None,
                        "outline_side": side,
                        "confidence": conf,
                    }
                )
        self.previous_entities = entities
        minimap: dict[str, Any] = {"ally_markers": [], "enemy_markers": [], "track_confidence": 0.0}
        position = None
        if "minimap" in profile.get("rois", {}):
            crop, _ = _roi(frame, profile, "minimap")
            calibrated_map = calibration and profile.get("minimap_north_up_calibrated") is True
            marker_conf = 0.92 if calibrated_map else 0.6
            for side in ("self", "ally", "enemy"):
                specs = profile.get("minimap_colors_hsv", {}).get(side, {})
                boxes = _components(crop, specs)
                markers = [
                    {
                        "x_norm": (x + w / 2) / crop.shape[1],
                        "y_norm": (y + h / 2) / crop.shape[0],
                        "side": side,
                        "confidence": marker_conf,
                    }
                    for x, y, w, h in boxes
                ]
                if side == "self" and len(markers) == 1:
                    position = (markers[0]["x_norm"], markers[0]["y_norm"])
                    minimap.update(
                        self_x_norm=position[0],
                        self_y_norm=position[1],
                        track_confidence=marker_conf,
                    )
                elif side != "self":
                    minimap[f"{side}_markers"] = markers
        displacement = (
            math.dist(position, self.previous_position) / dt
            if (position is not None and self.previous_position is not None and contiguous)
            else None
        )
        self.previous_position = position
        # Cross-Agent fallback is built from measured template/slot evidence, not key text.
        remote_signals: dict[str, Any] = {}
        for name, signal in (
            ("normal_weapon_hud_template", "player_hud_missing"),
            ("normal_hands_template", "hands_weapon_absent_sustained"),
        ):
            if not calibration or not profile.get(name):
                continue
            score, _ = self._template_score(frame, profile[name])
            if score >= 0.9:
                self.normal_seen.add(name)
                self.absent_since.pop(name, None)
            elif name in self.normal_seen and score < 0.4:
                since = self.absent_since.setdefault(name, float(hud["time_sec"]))
                if float(hud["time_sec"]) - since >= 0.4:
                    remote_signals[signal] = 0.9
        for name, path in profile.get("remote_templates", {}).items():
            score, _ = self._template_score(frame, path)
            if score >= 0.9:
                remote_signals[name] = score
        cast_slot = None
        for item in values.get("ability_slots", []):
            before: dict[str, Any] = next(
                (
                    slot
                    for slot in prior.get("ability_slots", [])
                    if slot.get("slot") == item.get("slot")
                ),
                {},
            )
            charges, old_charges = item.get("charges"), before.get("charges")
            if (type(charges) is int and type(old_charges) is int and charges < old_charges) or (
                before.get("available") is True and item.get("available") is False
            ):
                idx = item.get("slot")
                if idx in (0, 1, 2, 3):
                    cast_slot = ("C", "Q", "E", "X")[idx]
        if cast_slot is not None:
            remote_signals["ability_control_active"] = hud_confidence
        # An ordinary ability activation alone is not a remote suspicion.
        if len(remote_signals) == 1 and "ability_control_active" in remote_signals:
            remote_signals.clear()
        remote = classify_remote_view(hud, remote_signals)
        cast_score, _ = self._template_score(world, profile.get("cast_template"))
        effect_score, _ = self._template_score(world, profile.get("world_effect_template"))
        meta = {
            "primary_state": remote["primary_state"],
            "remote_view_type": remote["remote_view_type"],
            "weapon_changed": weapon_changed,
            "reload_detected": reload_detected,
            "weapon_ready": bool(values.get("weapon_text")) and not reload_detected,
            "weapon_state_confidence": hud_confidence if weapon_known else 0,
            "ammo_confidence": ammo_confidence,
            "recoil_score": recoil,
            "muzzle_flash_score": muzzle,
            "shot_visual_score": max(recoil, muzzle),
            "micro_motion_state": motion_state,
            "micro_sample_interval_sec": dt,
            "micro_motion_confidence": flow_confidence,
            "camera_rotation_rejected": stationary_confidence >= 0.85
            or translation_confidence >= 0.85,
            "local_optical_flow_translation_confidence": translation_confidence,
            "weapon_bob_moving_confidence": bob_confidence,
            "cover_transition": cover_transition,
            "cover_transition_confidence": prior_cover if cover_transition else 0,
            "new_line_of_sight": calibration and revealed_score >= 0.9,
            "revealed_region_confidence": revealed_score if calibration else 0,
            "returned_to_cover_cv": returned_cover,
            "map_displacement_confidence": minimap["track_confidence"],
            "ability_charge_delta": -1 if cast_slot is not None else None,
            "cast_animation_score": cast_score if calibration else min(0.64, cast_score),
            "slot_index": cast_slot,
        }
        return {
            "motion": {
                "state": motion_state,
                "stationary_confidence": stationary_confidence,
                "camera_motion_score": camera_score,
                "map_displacement_norm_per_sec": displacement,
                "evidence_sources": motion_sources,
            },
            "aiming": aiming,
            "weapon_action": {
                "weapon_text": values.get("weapon_text"),
                "ammo_current": ammo,
                "ammo_delta": ammo_delta,
                "muzzle_flash_score": muzzle,
                "recoil_score": recoil,
                "confidence": action_conf,
                "shot_candidate": bool(ammo_delta is not None and ammo_delta < 0)
                or max(recoil, muzzle) >= 0.5,
            },
            "entities": {
                "visible_enemies": [item for item in entities if item["outline_side"] == "enemy"],
                "visible_allies": [item for item in entities if item["outline_side"] == "ally"],
            },
            "minimap": minimap,
            "utility": {
                "cast_candidate": cast_slot is not None,
                "slot": cast_slot,
                "world_effect_candidate": "visible_effect"
                if calibration and effect_score >= 0.9
                else None,
                "confidence": max(min(hud_confidence, cast_score), effect_score)
                if calibration
                else 0,
            },
            "quality": {
                "visual_confidence": max(
                    stationary_confidence, max((item["confidence"] for item in entities), default=0)
                ),
                "blur_score": 1 / (1 + float(cv2.Laplacian(gray, cv2.CV_32F).var()) / 100),
                "notes": [] if calibration else ["visual_profile_uncalibrated"],
            },
            "measurement_meta": meta,
        }

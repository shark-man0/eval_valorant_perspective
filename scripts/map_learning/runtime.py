"""Local experiment adapters for the two independent CNNs."""

import math
from dataclasses import replace

import cv2
import numpy as np
import torch
from models import MarkerCNN, PortraitCNN
from recording_portraits import RecordingPortraitBank, RecordingPortraitTracker

from valorant_ai_coach.temporal.map_direct_recorder import (
    DirectPeak,
    DirectRecorderTracker,
    _rim_evidence,
)
from valorant_ai_coach.temporal.replay import file_sha, read_json


def restore(model, path):
    with np.load(path, allow_pickle=False) as src:
        model.load_state_dict({key: torch.from_numpy(src[key]) for key in src.files})
    return model.eval()


def load_models(directory, knowledge, *, receipt_sha256=None):
    """Open the independent models from a private, content-bound training result."""
    receipt_path = directory / "training_summary_PRIVATE.json"
    if receipt_sha256 is not None and file_sha(receipt_path) != receipt_sha256:
        raise ValueError("Map CNN receipt hash mismatch")
    receipt = read_json(receipt_path)
    if (
        receipt.get("schema") != "map_cnn_weights_v1"
        or receipt.get("formal_outputs") != 0
        or tuple(receipt.get("agent_uuids", ())) != knowledge._uuids
    ):
        raise ValueError("Matching development Map CNN model receipt required")
    models = {}
    classes = len(knowledge._uuids) + int(receipt.get("background_class") is True)
    for name, model in (("portrait", PortraitCNN(classes)), ("marker", MarkerCNN())):
        path = directory / f"{name}_cnn_weights_PRIVATE.npz"
        if file_sha(path) != receipt["weight_sha256s"].get(name):
            raise ValueError("Map CNN weight hash mismatch")
        models[name] = restore(model, path)
    if receipt_sha256 is not None and file_sha(receipt_path) != receipt_sha256:
        raise ValueError("Map CNN receipt changed during loading")
    return models


def image_tensor(frame):
    return torch.from_numpy(np.ascontiguousarray(frame)).permute(2, 0, 1)[None].float() / 255.0


class DenseMarkerCNN:
    def __init__(self, model, threshold):
        self.model = model
        self.threshold = threshold

    @torch.inference_mode()
    def peaks(self, roi, uuid, *, scale, count=12):
        if not 0.8 <= scale <= 1.2 or min(roi.shape[:2]) < 30:
            return []
        if scale != 1:
            sized = cv2.resize(roi, None, fx=1 / scale, fy=1 / scale, interpolation=cv2.INTER_AREA)
        else:
            sized = roi
        heat = self.model(image_tensor(sized))[0, 0].sigmoid().numpy()
        # Suppress the receptive-field edge where the complete measured rim is unavailable.
        heat[:2, :] = 0
        heat[-2:, :] = 0
        heat[:, :2] = 0
        heat[:, -2:] = 0
        candidates = np.argwhere(
            (heat == cv2.dilate(heat, np.ones((7, 7), np.uint8))) & (heat >= self.threshold)
        )
        candidates = sorted(candidates, key=lambda yx: (-heat[*yx], *yx))[:count]
        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        result = []
        for y, x in candidates:
            center = (round(scale * (2 * int(x) + 9)), round(scale * (2 * int(y) + 9)))
            if not (
                12 * scale < center[0] < roi.shape[1] - 12 * scale
                and 12 * scale < center[1] < roi.shape[0] - 12 * scale
            ):
                continue
            sectors, pairs, rivals = _rim_evidence(hsv, *center, scale)
            result.append(DirectPeak(center, float(heat[y, x]), sectors, pairs, rivals))
        return result


class LearnedRecorderTracker(DirectRecorderTracker):
    def __init__(self, *args, portrait_model, refine_center=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.portrait_model = portrait_model
        self.refine_center = refine_center
        self.refined_current = False

    @torch.inference_mode()
    def _confirmed_peaks(self, image, peaks, left, top):
        chosen = self._score_peaks(image, peaks, left, top)
        self.refined_current = False
        if chosen or not self.refine_center or not peaks:
            return chosen
        scale = image.shape[1] / 1920
        offset = max(1, round(scale))
        reach = math.ceil(11 * scale) + offset
        high_x = left + max(p.center[0] for p in peaks) + reach + 1
        high_y = top + max(p.center[1] for p in peaks) + reach + 1
        hsv = cv2.cvtColor(image[top:high_y, left:high_x], cv2.COLOR_BGR2HSV)
        recovered = []
        for peak in peaks:
            alternatives = []
            for dx, dy in ((-offset, 0), (offset, 0), (0, -offset), (0, offset)):
                x, y = peak.center[0] + dx, peak.center[1] + dy
                if not 11*scale <= x < hsv.shape[1]-11*scale or not (
                    11*scale <= y < hsv.shape[0]-11*scale
                ):
                    continue
                warm, pairs, rivals = _rim_evidence(hsv, x, y, scale)
                alternatives.append(replace(
                    peak, center=(x, y), warm_sectors=warm, opposite_pairs=pairs,
                    chromatic_rivals=rivals,
                ))
            evidence = self._score_peaks(image, alternatives, left, top)
            if len(evidence) >= 2:
                index, score, margin = max(evidence, key=lambda m: (m[1], m[2], -m[0]))
                recovered.append((alternatives[index], score, margin))
        for peak, score, margin in recovered:
            chosen.append((len(peaks), score, margin))
            peaks.append(peak)
        self.refined_current = bool(recovered)
        return chosen

    def _score_peaks(self, image, peaks, left, top):
        result = []
        target = self.portrait_reader._uuids.index(self.identity.uuid)
        scale = image.shape[1] / 1920
        half = max(2, round(8 * scale))
        for i, p in enumerate(peaks):
            if p.warm_sectors < 5 or p.opposite_pairs < 1 or p.chromatic_rivals > 5:
                continue
            x, y = p.center[0] + left, p.center[1] + top
            crop = image[y - half : y + half + 1, x - half : x + half + 1]
            if crop.shape[:2] != (2 * half + 1, 2 * half + 1):
                continue
            values = (
                self.portrait_model(image_tensor(cv2.resize(crop, (17, 17))))[0]
                .softmax(dim=0)
                .numpy()
            )
            score = float(values[target])
            margin = score - float(np.delete(values, target).max())
            if score < 0.8 or margin < 0.35:
                continue
            # Preserve positive current evidence from the independent reference bank
            # while measuring whether the learned portrait separates close competitors.
            official = self.portrait_reader._portrait_scores(image, (x, y))
            if (
                official is None
                or official[target] < 0.73
                or official[target] - np.delete(official, target).max() < 0.03
            ):
                continue
            result.append((i, score, margin))
        return result


class AdaptiveRecordingTracker(LearnedRecorderTracker):
    """Keep incumbent decisions and try same-recording evidence on an unresolved sample."""

    def __init__(self, search, identity, reader, **kwargs):
        super().__init__(search, identity, reader, **kwargs)
        self.bank = RecordingPortraitBank()
        self.continuity = RecordingPortraitTracker(self.bank, identity, reader)
        self.can_seed = False

    def _observe_measured(self, image, roi, sample, frame, camera):
        self.bank.visit(sample, roi)
        pool, result = super()._observe_measured(image, roi, sample, frame, camera)
        self.can_seed = result["selection_status"] == "RESEARCH_SELECTED"
        if result["selection_reason"] != "direct_portrait_or_rim_unresolved":
            self.continuity.previous = self.previous if self.can_seed else None
            return pool, result
        recovered, agreement = self.continuity._observe_measured(image, roi, sample, frame, camera)
        return (recovered, agreement) if agreement["support_count"] else (pool, result)

    def remember_projection(self, image):
        super().remember_projection(image)
        if not self.can_seed or self.previous is None or self.refined_current:
            return
        center = self.previous.center
        scores = self.portrait_reader._portrait_scores(image, center)
        target = self.portrait_reader._uuids.index(self.identity.uuid)
        if scores is not None and scores[target] >= .76 and (
            scores[target] - np.delete(scores, target).max() >= .045
        ):
            self.bank.remember(image, self.previous.sample, center)

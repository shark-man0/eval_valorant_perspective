import hashlib

import cv2
import numpy as np

from valorant_ai_coach.temporal.evidence import freeze_native_sample
from valorant_ai_coach.temporal.map_recording_anchors import EVIDENCE, RecordingMapAnchors


def test_map_anchor_registration_uses_two_distinct_earlier_frames_on_the_same_scope():
    rng = np.random.default_rng(73)
    pattern = np.zeros((320, 320), np.uint8)
    for x, y, radius, color in rng.integers([20, 20, 3, 100], [300, 300, 10, 255], (100, 4)):
        cv2.circle(pattern, (int(x), int(y)), int(radius), int(color), -1)
    texture = cv2.cvtColor(pattern, cv2.COLOR_GRAY2BGR)
    bank = RecordingMapAnchors()

    def frame(tick, offset, *, epoch="a"):
        matrix = np.array([[1, 0, offset], [0, 1, 0]], dtype=np.float64)
        image = cv2.warpAffine(texture, matrix, (320, 320))
        sample = freeze_native_sample({
            "source_id": "test", "source_sha256": "a"*64, "acquisition_id": epoch,
            "native_epoch": epoch, "native_pts_tick": tick, "native_time_base": "1",
            "acquired_frame_sha256": "b"*64, "frame_size_px": [320, 320],
            "native_pixel_sha256": hashlib.sha256(image.tobytes()).hexdigest(),
        })
        return image, sample, np.vstack([matrix, [0, 0, 1]]).tolist()

    def strong(matrix):
        return {"map_id": "map", "inliers": 35, "fit_residual_p95_reference_px": 1.,
                "reference_to_roi_homography_candidate": matrix}

    missing = {"roi_pixel_bounds": [0, 0, 320, 320], "map_name_candidates": [],
               "reference_ranking": []}
    a, sa, ma = frame(10, 3)
    b, sb, mb = frame(20, -3)
    c, sc, _ = frame(33, 7)
    assert bank.observe(a, sa, {**missing, "map_name_candidates": [strong(ma)]},
                        "map", (163, 160))["map_name_candidates"]
    assert bank.observe(c, sc, missing, "map", (167, 160)) == missing
    # Rebuild the same chronological sequence after the first rejected attempt.
    bank.observe(a, sa, {**missing, "map_name_candidates": [strong(ma)]}, "map", (163, 160))
    bank.observe(b, sb, {**missing, "map_name_candidates": [strong(mb)]}, "map", (157, 160))
    recovered = bank.observe(c, sc, missing, "map", (167, 160))
    assert recovered["alignment_recovery"] == EVIDENCE
    assert set(recovered["registration_anchor_sample_refs"]) == {
        sa["sample_sha256"], sb["sample_sha256"],
    }
    hit, = recovered["map_name_candidates"]
    matrix = hit["reference_to_roi_homography_candidate"]
    assert np.linalg.norm(np.linalg.solve(matrix, [167, 160, 1])[:2] - [160, 160]) < 1
    newer, changed, _ = frame(45, 9, epoch="b")
    assert bank.observe(newer, changed, missing, "map", (169, 160)) == missing

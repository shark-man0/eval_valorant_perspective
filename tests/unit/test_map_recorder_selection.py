import hashlib
from copy import deepcopy

import cv2
import numpy as np

from valorant_ai_coach.temporal.evidence import freeze_native_sample
from valorant_ai_coach.temporal.map_marker_geometry import measure_marker_geometry, same_marker
from valorant_ai_coach.temporal.map_recorder_selection import MapRecorderSelector


def _image(x, y=60):
    image = np.full((120, 1920, 3), 95, dtype=np.uint8)
    image[y-6:y+7, x-6:x] = (45, 60, 95)
    image[y-6:y+7, x:x+7] = (135, 150, 168)
    rim = (165, 246, 248)
    cv2.circle(image, (x, y), 8, rim, 2)
    cv2.fillConvexPoly(image, np.array([[x+7, y-4], [x+14, y], [x+7, y+4]]), rim)
    return image


def _context(image, tick, pool, anchor=None):
    sample = freeze_native_sample({
        "source_id": "synthetic", "source_sha256": "a"*64,
        "acquisition_id": "test", "native_epoch": "test",
        "native_pts_tick": tick, "native_time_base": "1/60",
        "acquired_frame_sha256": "b"*64,
        "native_pixel_sha256": hashlib.sha256(image.tobytes()).hexdigest(),
        "frame_size_px": list(image.shape[:2][::-1]),
    })
    agents = [{"agent": "Recorder", "score": .98}, {"agent": "Other", "score": .40}]
    return {
        "sample": sample, "camera": {"value": "SELF"}, "life": {"value": "ALIVE"},
        "map": {"candidates": pool, "current_recorder_view_evidence_ids": ["current"]},
        "viewed_identity": {
            "recording_player_anchor": {"sample": anchor, "agent_candidates": agents,
                                        "evidence_ids": ["earlier"]} if anchor else None,
            "agent_signature_relation": "COMPATIBLE",
            "viewed_agent_candidates": agents,
        },
        "round_token": "round", "continuity": {"carry_allowed": True},
    }


def test_tip_uses_one_silhouette_and_separates_nearby_portraits():
    image = _image(80)
    second = _image(105)
    image[:, 95:130] = second[:, 95:130]
    cv2.circle(image, (59, 60), 3, (165, 246, 248), -1)
    pool = [{"center_frame_px": point} for point in ([80, 60], [81, 60], [105, 60], [59, 60])]
    original, duplicate, other, icon = measure_marker_geometry(image, pool)
    assert original and original.tip and np.linalg.norm(np.subtract(original.tip, (94, 60))) <= 2
    assert duplicate and same_marker(original, duplicate)
    assert other and not same_marker(other, original)
    assert icon is None


def test_selection_requires_current_pixels_and_consecutive_anchored_witnesses():
    initial = _image(78)
    first_fit, = measure_marker_geometry(initial, [{"center_frame_px": [78, 60]}])
    assert first_fit
    x, y = first_fit.center
    half = round(first_fit.radius * .7)
    gray = cv2.cvtColor(initial, cv2.COLOR_BGR2GRAY)
    reference = gray[y-half:y+half+1, x-half:x+half+1].copy()
    selector = MapRecorderSelector([("Recorder", reference), ("Other", np.fliplr(reference))])
    anchor = _context(initial, 0, [])["sample"]

    def observe(cx, tick, blocked=None):
        image = _image(cx)
        pool = [{"center_frame_px": [cx, 60]}]
        frame = _context(image, tick, pool, anchor)
        if blocked:
            domain, value = blocked
            if domain == "pool":
                frame["map"]["candidates"] = []
            elif domain == "sample":
                wrong = deepcopy(frame["sample"])
                del wrong["sample_sha256"]
                wrong["native_pts_tick"] += 1
                frame["sample"] = freeze_native_sample(wrong)
            else:
                frame[domain] = value
        return selector.observe(image, pool, _context(image, tick, pool)["sample"], frame)

    assert [observe(80+i, tick)["support_count"] for i, tick in enumerate((6, 12))] == [1, 2]
    accepted = observe(82, 18)
    assert accepted["selection_status"] == "RESEARCH_SELECTED"
    assert accepted["research_candidate_index"] == 0
    assert accepted["ownership"] == "UNKNOWN" and not accepted["position_authority"]
    assert observe(83, 24, ("camera", {"value": "SPECTATOR"}))["support_count"] == 0
    assert observe(84, 30)["support_count"] == 1
    assert observe(85, 36, ("pool", None))["selection_reason"] == "different_candidate_pool"
    assert observe(86, 42, ("sample", None))["selection_reason"] == "unmatched_native_context"
    assert observe(87, 48)["support_count"] == 1
    assert observe(88, 72)["support_count"] == 1

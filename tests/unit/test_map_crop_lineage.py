import hashlib

import numpy as np
import pytest

from scripts.map_learning.crop_lineage import CATEGORIES, SCHEMA, load_crop_lineage
from valorant_ai_coach.temporal.evidence import freeze_native_sample
from valorant_ai_coach.temporal.replay import file_sha, write_private


def test_crop_lineage_binds_each_array_row_to_its_native_source(tmp_path):
    sample = freeze_native_sample({
        "source_id": "source", "source_sha256": "a"*64, "acquisition_id": "native",
        "native_epoch": "native", "native_pts_tick": 9, "native_time_base": "1/5",
        "acquired_frame_sha256": "c"*64, "native_pixel_sha256": "d"*64, "frame_size_px": [100, 100],
    })
    key = sample["sample_sha256"]
    rows = {name: [] for name in CATEGORIES}
    arrays = {name: np.empty((0, 25, 25, 3), np.uint8) for name in CATEGORIES}
    patch = np.zeros((25, 25, 3), np.uint8)
    arrays["positive"] = patch[None, ...]
    rows["positive"] = [{
        "sample_sha256": key, "label": "recorder_weak", "center": [40, 50],
        "timeline_observation_ids": ["e"*64],
        "patch_sha256": hashlib.sha256(patch.tobytes()).hexdigest(),
    }]
    path = tmp_path / "lineage.json"
    write_private(path, {"schema": SCHEMA, "source_sha256": sample["source_sha256"],
                         "native_receipt_sha256": "b"*64, "samples": {key: sample}, "rows": rows})
    pinned = file_sha(path)
    load_crop_lineage(path, pinned, sample["source_sha256"], arrays)
    arrays["positive"][0, 0, 0, 0] = 1
    with pytest.raises(ValueError, match="crop bytes"):
        load_crop_lineage(path, pinned, sample["source_sha256"], arrays)
    with pytest.raises(ValueError, match="source mismatch"):
        load_crop_lineage(path, pinned, "f"*64, arrays)

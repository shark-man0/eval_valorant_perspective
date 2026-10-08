import hashlib
import json
import sys
from pathlib import Path

import cv2
import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.diagnostics.diagnose_roster_portraits import (  # noqa: E402
    EDGE_METHOD,
    METHOD,
    locate,
    replay,
)


def test_location_is_descriptive_not_liveness():
    ref = np.random.default_rng(8).integers(0, 255, (12, 15), dtype=np.uint8)
    search = np.full((40, 90), 60, dtype=np.uint8)
    search[7:19, 52:67] = ref
    result = locate(ref, search)
    assert result["similarity"] > .99
    assert result["offset_xy"] == [52, 7]
    assert "alive" not in result
    blank = locate(ref, np.full_like(search, 60))
    assert blank["similarity"] is None
    assert blank["offset_xy"] is None


@pytest.mark.parametrize("ref,search", [
    (np.full((3, 3), 50, np.uint8), np.zeros((6, 6), np.uint8)),
    (np.arange(100, dtype=np.uint8).reshape(10, 10), np.zeros((5, 5), np.uint8)),
])
def test_flat_reference_and_invalid_dimensions_fail_closed(ref, search):
    with pytest.raises(ValueError):
        locate(ref, search)


def fixture(tmp_path):
    training = tmp_path / "training"
    probes = tmp_path / "probes"
    training.mkdir()
    probes.mkdir()
    rows = []
    for i in range(3):
        path = training / f"{i}.jpg"
        image = np.random.default_rng(i).integers(0, 255, (60, 120), dtype=np.uint8)
        cv2.imwrite(str(path), image)
        rows.append({"frame": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    cv2.imwrite(str(probes / "probe.jpg"),
                np.random.default_rng(7).integers(0, 255, (60, 120), dtype=np.uint8))
    layout = tmp_path / "layout.json"
    layout.write_text(json.dumps({"schema_version": "1", "calibrated": True,
        "roi_coordinate_system": "normalized_0_to_1",
        "reference_resolution": {"width": 120, "height": 60},
        "regions": {"ally_roster": {"x": 0, "y": 0, "width": 1, "height": 1}}}))
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"method": METHOD, "training_frames": rows,
        "crops": {"portrait": {"side": "ally", "xyxy": [3, 5, 23, 25]}}}))
    return layout, manifest, training, probes, tmp_path / "out.json"


def test_replay_hashes_only_and_preserves_source_inputs(tmp_path):
    args = fixture(tmp_path)
    before = [p.read_bytes() for p in args[:2]]
    result = replay(*args)
    assert result["qualification_created"] is False
    assert result["continuity_attested"] is False
    assert result["liveness_counts"] is None
    assert len(result["rows"]) == 1
    assert [p.read_bytes() for p in args[:2]] == before
    assert str(tmp_path) not in args[-1].read_text()
    with pytest.raises(FileExistsError):
        replay(*args)


@pytest.mark.parametrize("failure", ["hash", "overlap", "bounds", "method"])
def test_replay_rejects_unbound_or_changed_inputs(tmp_path, failure):
    args = fixture(tmp_path)
    manifest = json.loads(args[1].read_bytes())
    if failure == "hash":
        manifest["training_frames"][0]["sha256"] = "0" * 64
    elif failure == "overlap":
        (args[3] / "probe.jpg").write_bytes((args[2] / "0.jpg").read_bytes())
    elif failure == "bounds":
        manifest["crops"]["portrait"]["xyxy"] = [0, 0, 121, 60]
    else:
        manifest["method"] = "unfrozen"
    args[1].write_text(json.dumps(manifest))
    with pytest.raises(ValueError):
        replay(*args)
    assert not args[-1].exists()


def test_edge_reference_without_training_support_cannot_probe_positive(tmp_path):
    args = fixture(tmp_path)
    manifest = json.loads(args[1].read_bytes())
    manifest["method"] = EDGE_METHOD
    manifest["control_roi"] = "ally_roster"
    args[1].write_text(json.dumps(manifest))
    # Probe contains an exact copy of reference pixels but is a distinct frame.
    image = cv2.imread(str(args[2] / "0.jpg"), cv2.IMREAD_GRAYSCALE)
    image[-1, -1] = 255 - image[-1, -1]
    cv2.imwrite(str(args[3] / "probe.jpg"), image)
    report = replay(*args)
    assert report["references"]["portrait"]["available"] is False
    location = report["rows"][0]["locations"]["portrait"]
    assert location["similarity"] is None
    assert location["reason"] == "training_reference_insufficient"
    assert location["control"]["similarity"] is None

"""Regression cases for image-ID races and encoded/decoded hash confusion."""

import hashlib
import json
import sys

import cv2
import numpy as np
import pytest

from scripts.seal_diagnostic_review import ReviewError, main, seal_review, verify_review


def source(tmp_path, uid="A", compression=0, image=None):
    if image is None:
        image = np.arange(24 * 32 * 3, dtype=np.uint8).reshape(24, 32, 3)
    ok, encoded = cv2.imencode(".png", image, [cv2.IMWRITE_PNG_COMPRESSION, compression])
    assert ok
    path = tmp_path / f"source_{uid}.png"
    path.write_bytes(encoded.tobytes())
    return {
        "id": uid,
        "path": str(path),
        "decoded_bgr_sha256": hashlib.sha256(image.tobytes()).hexdigest(),
        "png_file_sha256": hashlib.sha256(encoded.tobytes()).hexdigest(),
    }


def test_png_encodings_share_pixel_identity_and_review_keeps_full_image(tmp_path):
    a = source(tmp_path, "A", 0)
    b = source(tmp_path, "B", 9)
    assert a["png_file_sha256"] != b["png_file_sha256"]
    assert a["decoded_bgr_sha256"] == b["decoded_bgr_sha256"]
    bundle = tmp_path / "sealed"
    receipt = seal_review([a, b], bundle)
    assert (receipt["count"], receipt["unique_decoded_crops"], receipt["sheet_count"]) == (2, 1, 1)
    manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["sheets"][0]["ids"] == ["A", "B"]
    sheet = cv2.imread(str(bundle / "review_001.png"))
    image = cv2.imread(a["path"])
    assert np.array_equal(
        sheet[37:393, :460], cv2.resize(image, (460, 356), interpolation=cv2.INTER_AREA)
    )
    assert np.array_equal(sheet[37:393, 460:920], sheet[37:393, :460])


def test_source_regeneration_cannot_shift_a_completed_review(tmp_path):
    row = source(tmp_path)
    bundle = tmp_path / "sealed"
    receipt = seal_review([row], bundle)
    source(tmp_path, image=np.zeros((24, 32, 3), np.uint8))
    assert (
        verify_review(bundle, expected_manifest_sha256=receipt["manifest_file_sha256"]) == receipt
    )
    with pytest.raises(FileExistsError):
        seal_review([source(tmp_path)], bundle)


@pytest.mark.parametrize("kind", ["encoded_as_pixels", "wrong_encoded", "ambiguous_hash"])
def test_stale_or_ambiguous_hash_is_rejected_before_bundle_creation(tmp_path, kind):
    row = source(tmp_path)
    if kind == "encoded_as_pixels":
        row["decoded_bgr_sha256"] = row["png_file_sha256"]
    elif kind == "wrong_encoded":
        row["png_file_sha256"] = "0" * 64
    else:
        row["sha256"] = row.pop("decoded_bgr_sha256")
    destination = tmp_path / "sealed"
    with pytest.raises(ReviewError):
        seal_review([row], destination)
    assert not destination.exists()


@pytest.mark.parametrize("kind", ["image", "sheet", "mapping", "shape", "semantics", "non_dict"])
def test_mutation_is_rejected_before_annotation_join(tmp_path, kind):
    bundle = tmp_path / "sealed"
    seal_review([source(tmp_path)], bundle)
    path = bundle / "manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if kind == "image":
        cv2.imwrite(str(bundle / "A.png"), np.zeros((24, 32, 3), np.uint8))
    elif kind == "sheet":
        (bundle / "review_001.png").write_bytes(b"changed")
    else:
        if kind == "mapping":
            manifest["sheets"][0]["ids"] = ["B"]
        elif kind == "shape":
            manifest["images"][0]["shape_hwc"] = [32, 24, 3]
        elif kind == "semantics":
            manifest["pixel_hash_semantics"] = "encoded PNG"
        else:
            manifest["images"][0] = "invalid"
        path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ReviewError):
        verify_review(bundle)


def test_changed_manifest_with_self_consistent_new_hashes_fails_frozen_receipt(tmp_path):
    bundle = tmp_path / "sealed"
    receipt = seal_review([source(tmp_path)], bundle)
    path = bundle / "manifest.json"
    path.write_bytes(path.read_bytes() + b"\n")
    assert verify_review(bundle)["count"] == 1
    with pytest.raises(ReviewError, match="frozen review receipt"):
        verify_review(bundle, expected_manifest_sha256=receipt["manifest_file_sha256"])


@pytest.mark.parametrize("uid", ["../escape", "review_001", "REVIEW_001", "", "A" * 64])
def test_unsafe_or_reserved_image_ids_reject(tmp_path, uid):
    row = source(tmp_path)
    row["id"] = uid
    with pytest.raises(ReviewError):
        seal_review([row], tmp_path / "sealed")


def test_case_colliding_image_ids_reject_on_windows(tmp_path):
    a = source(tmp_path)
    b = dict(a, id="a")
    with pytest.raises(ReviewError):
        seal_review([a, b], tmp_path / "sealed")


def test_cli_failure_omits_private_source_path(tmp_path, monkeypatch, capsys):
    inputs = tmp_path / "inputs.json"
    row = source(tmp_path)
    row["path"] = str(tmp_path / "private_missing.png")
    inputs.write_text(json.dumps({"images": [row]}), encoding="utf-8")
    monkeypatch.setattr(
        sys,
        "argv",
        ["seal", "seal", "--inputs", str(inputs), "--destination", str(tmp_path / "sealed")],
    )
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 2
    stderr = capsys.readouterr().err
    assert "Review rejected" in stderr
    assert str(tmp_path) not in stderr and "private_missing" not in stderr

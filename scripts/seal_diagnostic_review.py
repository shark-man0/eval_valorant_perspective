"""Seal private image reviews with explicit encoded/pixel hashes. No detector input."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any

import cv2
import numpy as np

_ID = re.compile(r"[A-Za-z0-9_-]{1,64}\Z")
_HASH = re.compile(r"[a-f0-9]{64}\Z")
_PIXEL_SEMANTICS = "SHA256 contiguous decoded uint8 BGR HWC bytes"


class ReviewError(ValueError):
    """A review cannot be trusted; messages deliberately omit private paths/IDs."""


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _decode(data: bytes) -> np.ndarray:
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ReviewError("Expected PNG image")
    image = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None or image.size == 0:
        raise ReviewError("Image decode failed")
    return np.ascontiguousarray(image)


def _valid_hash(value: Any) -> bool:
    return isinstance(value, str) and _HASH.fullmatch(value) is not None


def _valid_id(value: Any) -> bool:
    return (
        isinstance(value, str)
        and _ID.fullmatch(value) is not None
        and re.fullmatch(r"review_[0-9]+", value, re.IGNORECASE) is None
        and cv2.getTextSize(value, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)[0][0] <= 444
    )


def seal_review(inputs: list[dict[str, Any]], destination: Path) -> dict[str, Any]:
    """Copy verified pixels first; create sheets from copies; publish manifest last.

    Source decoded hashes must already bind IDs to pixels. A mutable contact sheet
    is never an input. Source images are read once, so hashes and copies agree.
    Existing bundles are refused. Failure leaves no completed review manifest.
    """
    if (
        not isinstance(inputs, list)
        or not inputs
        or any(not isinstance(row, dict) for row in inputs)
    ):
        raise ReviewError("Expected nonempty image list")
    images: list[tuple[str, bytes, np.ndarray]] = []
    seen: set[str] = set()
    for row in inputs:
        if set(row) - {"id", "path", "decoded_bgr_sha256", "png_file_sha256"}:
            raise ReviewError("Unknown source field; hash semantics must be explicit")
        uid = row.get("id")
        if not _valid_id(uid) or uid.lower() in seen:
            raise ReviewError("Invalid or duplicate review ID")
        seen.add(uid.lower())
        if not isinstance(row.get("path"), str) or not _valid_hash(row.get("decoded_bgr_sha256")):
            raise ReviewError("Source path and decoded BGR hash required")
        data = Path(row["path"]).read_bytes()
        image = _decode(data)
        if _sha(image.tobytes()) != row["decoded_bgr_sha256"]:
            raise ReviewError("Source decoded BGR hash mismatch")
        if "png_file_sha256" in row and (
            not _valid_hash(row["png_file_sha256"]) or _sha(data) != row["png_file_sha256"]
        ):
            raise ReviewError("Source PNG file hash mismatch")
        images.append((uid, data, image))
    destination.mkdir(parents=True, exist_ok=False)
    entries = []
    for uid, data, image in images:
        filename = f"{uid}.png"
        (destination / filename).write_bytes(data)
        entries.append(
            {
                "id": uid,
                "filename": filename,
                "png_file_sha256": _sha(data),
                "decoded_bgr_sha256": _sha(image.tobytes()),
                "shape_hwc": list(image.shape),
            }
        )
    sheets = []
    for page in range(math.ceil(len(images) / 6)):
        tiles = []
        subset = images[page * 6 : (page + 1) * 6]
        for uid, _, image in subset:
            tile = np.zeros((393, 460, 3), dtype=np.uint8)
            tile[37:] = cv2.resize(image, (460, 356), interpolation=cv2.INTER_AREA)
            cv2.putText(tile, uid, (8, 27), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            tiles.append(tile)
        while len(tiles) < 6:
            tiles.append(np.zeros((393, 460, 3), dtype=np.uint8))
        sheet = np.vstack([np.hstack(tiles[:3]), np.hstack(tiles[3:])])
        ok, encoded = cv2.imencode(".png", sheet)
        if not ok:
            raise ReviewError("Sheet encoding failed")
        data = encoded.tobytes()
        filename = f"review_{page + 1:03}.png"
        (destination / filename).write_bytes(data)
        sheets.append(
            {"filename": filename, "png_file_sha256": _sha(data), "ids": [row[0] for row in subset]}
        )
    manifest = {
        "schema_version": 1,
        "role": "private_diagnostic_review_only",
        "pixel_hash_semantics": _PIXEL_SEMANTICS,
        "images": entries,
        "sheets": sheets,
    }
    with (destination / "manifest.json").open("x", encoding="utf-8") as stream:
        json.dump(manifest, stream, indent=2)
        stream.write("\n")
    return verify_review(destination)


def verify_review(
    destination: Path, *, expected_manifest_sha256: str | None = None
) -> dict[str, Any]:
    """Verify before viewing, and again when joining annotations to predictions."""
    manifest_bytes = (destination / "manifest.json").read_bytes()
    if expected_manifest_sha256 is not None and (
        not _valid_hash(expected_manifest_sha256)
        or _sha(manifest_bytes) != expected_manifest_sha256
    ):
        raise ReviewError("Review manifest differs from frozen review receipt")
    manifest = json.loads(manifest_bytes.decode("utf-8"))
    if not isinstance(manifest, dict):
        raise ReviewError("Invalid review manifest")
    if (
        manifest.get("schema_version") != 1
        or manifest.get("role") != "private_diagnostic_review_only"
    ):
        raise ReviewError("Unsupported review manifest")
    if manifest.get("pixel_hash_semantics") != _PIXEL_SEMANTICS:
        raise ReviewError("Unsupported pixel hash semantics")
    entries = manifest.get("images")
    sheets = manifest.get("sheets")
    if not isinstance(entries, list) or not entries or not isinstance(sheets, list):
        raise ReviewError("Incomplete review manifest")
    ids = []
    pixel_keys = set()
    for row in entries:
        if not isinstance(row, dict):
            raise ReviewError("Invalid image entry")
        uid = row.get("id")
        if not _valid_id(uid) or uid.lower() in {i.lower() for i in ids}:
            raise ReviewError("Invalid image mapping")
        if row.get("filename") != f"{uid}.png":
            raise ReviewError("Invalid image filename")
        data = (destination / row["filename"]).read_bytes()
        image = _decode(data)
        if _sha(data) != row.get("png_file_sha256"):
            raise ReviewError("Sealed PNG changed")
        if _sha(image.tobytes()) != row.get("decoded_bgr_sha256"):
            raise ReviewError("Sealed decoded pixels changed")
        if list(image.shape) != row.get("shape_hwc"):
            raise ReviewError("Sealed image shape changed")
        ids.append(uid)
        pixel_keys.add((tuple(image.shape), row["decoded_bgr_sha256"]))
    if len(sheets) != math.ceil(len(entries) / 6):
        raise ReviewError("Sheet count changed")
    sheet_ids = []
    for page, row in enumerate(sheets, 1):
        if not isinstance(row, dict):
            raise ReviewError("Invalid sheet entry")
        if row.get("filename") != f"review_{page:03}.png":
            raise ReviewError("Invalid sheet filename")
        data = (destination / row["filename"]).read_bytes()
        if _sha(data) != row.get("png_file_sha256"):
            raise ReviewError("Sealed sheet changed")
        if row.get("ids") != ids[(page - 1) * 6 : page * 6]:
            raise ReviewError("Sheet image mapping changed")
        sheet_ids.extend(row["ids"])
    if sheet_ids != ids:
        raise ReviewError("Sheet image coverage changed")
    return {
        "count": len(ids),
        "unique_decoded_crops": len(pixel_keys),
        "sheet_count": len(sheets),
        "manifest_file_sha256": _sha(manifest_bytes),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    seal = commands.add_parser("seal")
    seal.add_argument("--inputs", type=Path, required=True)
    seal.add_argument("--destination", type=Path, required=True)
    verify = commands.add_parser("verify")
    verify.add_argument("--destination", type=Path, required=True)
    verify.add_argument("--expected-manifest-sha256", required=True)
    args = parser.parse_args()
    try:
        if args.command == "seal":
            inputs = json.loads(args.inputs.read_text(encoding="utf-8"))
            if not isinstance(inputs, dict) or set(inputs) != {"images"}:
                raise ReviewError("Expected image input manifest")
            summary = seal_review(inputs["images"], args.destination)
        else:
            summary = verify_review(
                args.destination, expected_manifest_sha256=args.expected_manifest_sha256
            )
    except (ReviewError, OSError, ValueError, TypeError) as exc:
        message = str(exc) if isinstance(exc, ReviewError) else "Review input or bundle unavailable"
        parser.exit(2, f"Review rejected: {message}\n")
    print(json.dumps(summary))


if __name__ == "__main__":
    main()

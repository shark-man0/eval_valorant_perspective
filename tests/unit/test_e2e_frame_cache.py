from __future__ import annotations

# The repository root is added below so script modules can be imported in pytest.
# ruff: noqa: E402, I001

import hashlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.e2e.frame_cache import DecodedFrameCache  # noqa: E402
from valorant_ai_coach.video import FrameSample  # noqa: E402


SOURCE_HASH = hashlib.sha256(b"source video").hexdigest()
FINGERPRINT = hashlib.sha256(b"decoder configuration").hexdigest()


def test_decoder_identity_survives_cache_and_rejects_foreign_source(tmp_path):
    source = tmp_path / 'decoded.jpg'
    source.write_bytes(b'decoder output')
    image_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    frame = FrameSample(.036003, source, 553, '1/15360', SOURCE_HASH, image_hash)
    cache = DecodedFrameCache(tmp_path / 'cache', SOURCE_HASH, FINGERPRINT)
    stored = cache.put(frame)
    fetched = cache.get(frame.time_sec)
    assert fetched == stored
    assert fetched.source_pts_ticks == 553
    assert fetched.source_image_sha256 == image_hash
    foreign = FrameSample(.036003, source, 553, '1/15360', 'b' * 64, image_hash)
    with pytest.raises(ValueError, match='binding mismatch'):
        cache.put(foreign)


def test_put_and_get_preserve_exact_asset_bytes_and_exact_timestamp(tmp_path: Path) -> None:
    original_bytes = b"jpeg bytes from the decoder\x00"
    source = tmp_path / "decoded.jpg"
    source.write_bytes(original_bytes)
    cache = DecodedFrameCache(tmp_path / "cache", SOURCE_HASH, FINGERPRINT)

    written = cache.put(FrameSample(time_sec=0.3, path=source))
    fetched = cache.get(0.3)

    assert fetched == written
    assert fetched is not None
    assert fetched.time_sec.hex() == (0.3).hex()
    assert fetched.path.read_bytes() == original_bytes
    assert cache.stats.writes == 1
    assert cache.stats.hits == 1


def test_source_timestamp_and_preprocessing_fingerprint_partition_keys(tmp_path: Path) -> None:
    source = tmp_path / "frame.jpg"
    source.write_bytes(b"frame")
    cache_dir = tmp_path / "cache"
    first = DecodedFrameCache(cache_dir, SOURCE_HASH, FINGERPRINT)
    first.put(FrameSample(1.0, source))

    assert first.get(1.0000000001) is None
    assert DecodedFrameCache(cache_dir, "a" * 64, FINGERPRINT).get(1.0) is None
    other_fingerprint = hashlib.sha256(b"new preprocessing").hexdigest()
    assert DecodedFrameCache(cache_dir, SOURCE_HASH, other_fingerprint).get(1.0) is None


def test_corrupt_asset_or_metadata_is_a_safe_miss(tmp_path: Path) -> None:
    source = tmp_path / "frame.jpg"
    source.write_bytes(b"frame")
    cache = DecodedFrameCache(tmp_path / "cache", SOURCE_HASH, FINGERPRINT)
    stored = cache.put(FrameSample(2.5, source))
    stored.path.write_bytes(b"corrupted")
    assert cache.get(2.5) is None

    stored.path.write_bytes(b"frame")
    metadata_path = stored.path.parent / "metadata.json"
    metadata_path.write_text(json.dumps({"format_version": 1}), encoding="utf-8")
    assert cache.get(2.5) is None
    assert cache.stats.misses == 2


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -0.1, True])
def test_nonfinite_or_invalid_pts_is_rejected(tmp_path: Path, value: float) -> None:
    cache = DecodedFrameCache(tmp_path / "cache", SOURCE_HASH, FINGERPRINT)
    with pytest.raises(ValueError):
        cache.get(value)


@pytest.mark.parametrize("value", ["x" * 64, "g" * 64, "a" * 63])
def test_malformed_hashes_are_rejected(tmp_path: Path, value: str) -> None:
    with pytest.raises(ValueError):
        DecodedFrameCache(tmp_path / "cache", value, FINGERPRINT)


def test_symlink_cache_directory_and_source_are_rejected(tmp_path: Path) -> None:
    real_dir = tmp_path / "real"
    real_dir.mkdir()
    link = tmp_path / "cache-link"
    link.symlink_to(real_dir, target_is_directory=True)
    with pytest.raises(ValueError):
        DecodedFrameCache(link, SOURCE_HASH, FINGERPRINT)

    source = tmp_path / "frame.jpg"
    source.write_bytes(b"frame")
    source_link = tmp_path / "frame-link.jpg"
    source_link.symlink_to(source)
    cache = DecodedFrameCache(tmp_path / "clean-cache", SOURCE_HASH, FINGERPRINT)
    with pytest.raises(ValueError):
        cache.put(FrameSample(0.0, source_link))

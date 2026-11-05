"""Source provenance hashes must be complete and use bounded binary reads."""
import hashlib
from pathlib import Path

import pytest

from valorant_ai_coach.temporal.replay import file_sha


@pytest.mark.parametrize("size", [0, 1, 1024 * 1024, 3 * 1024 * 1024 + 17])
def test_source_hash_complete_with_bounded_reads(tmp_path, monkeypatch, size):
    payload = (bytes(range(256)) * ((size + 255) // 256))[:size]
    path = tmp_path / "source.bin"
    path.write_bytes(payload)
    expected = hashlib.sha256(payload).hexdigest()
    real_open = Path.open
    requests = []

    class BoundedReader:
        def __init__(self, stream):
            self.stream = stream

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return self.stream.__exit__(*args)

        def read(self, amount=-1):
            assert 0 < amount <= 1024 * 1024, "Source read must be bounded"
            requests.append(amount)
            return self.stream.read(amount)

    def tracked_open(self, mode="r", *args, **kwargs):
        assert self == path and mode == "rb"
        return BoundedReader(real_open(self, mode, *args, **kwargs))

    def reject_eager_read(self):
        pytest.fail("Do not allocate the whole source with read_bytes")

    monkeypatch.setattr(Path, "open", tracked_open)
    monkeypatch.setattr(Path, "read_bytes", reject_eager_read)
    assert file_sha(path) == expected
    assert requests


def test_source_hash_missing_file_remains_an_error(tmp_path):
    with pytest.raises(FileNotFoundError):
        file_sha(tmp_path / "missing.bin")

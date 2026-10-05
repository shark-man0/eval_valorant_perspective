from __future__ import annotations

import hashlib
import json

import pytest

from scripts.fixed_replay_manifest import (
    ManifestError,
    build_manifest,
    canonical_uniform_locators,
    manifest_hash,
    serialize_manifest,
    validate_manifest,
    write_manifest_immutable,
)

SOURCE = "a" * 64
RUN = "b" * 64


def test_canonical_uniform_is_deterministic_and_uses_earlier_tie() -> None:
    # With a 1/12 second time base, the 1/6-second target at 1/6 ties ticks 1 and 3.
    native = [
        {"pts": pts, "source_frame_index": index}
        for index, pts in enumerate((0, 1, 3, 4, 5, 6))
    ]
    selected = canonical_uniform_locators(native, "1/12")
    assert selected == [native[0], native[1], native[3], native[5]]
    assert canonical_uniform_locators(native, {"num": 2, "den": 24}) == selected


def test_manifest_serialization_and_hash_are_stable() -> None:
    args = dict(
        set_id="match_01",
        source_sha=SOURCE,
        stream_index=0,
        time_base="1/90000",
        locators=[{"pts": 0, "source_frame_index": 0, "pixel_sha256": RUN}],
        setkind="canonical_uniform",
    )
    first = build_manifest(**args)
    second = build_manifest(**args)
    serialized = serialize_manifest(first)
    assert serialized == serialize_manifest(second)
    assert manifest_hash(first) == hashlib.sha256(serialized).hexdigest()


def test_source_mismatch_and_duplicate_locators_are_rejected() -> None:
    manifest = build_manifest(
        set_id="case", source_sha=SOURCE, stream_index=0, time_base="1/30",
        locators=[{"pts": 0, "source_frame_index": 0}], setkind="canonical_uniform",
    )
    with pytest.raises(ManifestError, match="sourceSHA mismatch"):
        validate_manifest(manifest, expected_source_sha="c" * 64)
    with pytest.raises(ManifestError, match="duplicate locator"):
        build_manifest(
            set_id="case", source_sha=SOURCE, stream_index=0, time_base="1/30",
            locators=[{"pts": 1, "source_frame_index": 1}, {"pts": 1, "source_frame_index": 1}],
            setkind="canonical_uniform",
        )


@pytest.mark.parametrize(
    "records",
    [
        [{"pts": 2, "source_frame_index": 1}, {"pts": 1, "source_frame_index": 2}],
        [{"pts": True, "source_frame_index": 0}],
        [{"pts": 0, "source_frame_index": "0"}],
        [{"pts": 0, "source_frame_index": 0, "pixel_sha256": "bad"}],
    ],
)
def test_invalid_locator_order_and_types_are_rejected(records) -> None:
    with pytest.raises(ManifestError):
        build_manifest(
            set_id="case", source_sha=SOURCE, stream_index=0, time_base="1/30",
            locators=records, setkind="canonical_uniform",
        )


@pytest.mark.parametrize("time_base", ["0/30", "1/0", "1/x", {"num": True, "den": 30}])
def test_invalid_rational_time_base_is_rejected(time_base) -> None:
    with pytest.raises(ManifestError):
        build_manifest(
            set_id="case", source_sha=SOURCE, stream_index=0, time_base=time_base,
            locators=[{"pts": 0, "source_frame_index": 0}], setkind="canonical_uniform",
        )


def test_invalid_source_digest_is_rejected() -> None:
    with pytest.raises(ManifestError, match="SHA-256"):
        build_manifest(
            set_id="case", source_sha="not-a-digest", stream_index=0, time_base="1/30",
            locators=[{"pts": 0, "source_frame_index": 0}], setkind="canonical_uniform",
        )


@pytest.mark.parametrize(
    "mutation",
    [
        lambda m: m.update(unexpected=True),
        lambda m: m["frames"][0].update(expected_state="alive"),
        lambda m: m["frames"][0].update(gt_event="kill"),
        lambda m: m["provenance"].update(path="C:/private/video.mp4"),
    ],
)
def test_unknown_truth_or_private_fields_are_rejected(mutation) -> None:
    manifest = build_manifest(
        set_id="case", source_sha=SOURCE, stream_index=0, time_base="1/30",
        locators=[{"pts": 1, "source_frame_index": 0}], setkind="canonical_uniform",
    )
    mutation(manifest)
    with pytest.raises(ManifestError):
        validate_manifest(manifest)


def test_canonical_selection_rejects_non_locator_classifier_inputs() -> None:
    with pytest.raises(ManifestError, match="unknown locator fields"):
        canonical_uniform_locators(
            [{"pts": 0, "source_frame_index": 0, "detector_score": 0.99}], "1/30"
        )


def test_frozen_coverage_preserves_all_supplied_locators_and_clean_lineage() -> None:
    records = [
        {"pts": 0, "source_frame_index": 0},
        {"pts": 17, "source_frame_index": 1},
        {"pts": 60, "source_frame_index": 2},
    ]
    manifest = build_manifest(
        set_id="coverage_01", source_sha=SOURCE, stream_index=0, time_base="1/60",
        locators=records, setkind="frozen_production_coverage",
        provenance={"lineage_clean": True, "analyzer_commit": "1234567", "run_hash": RUN},
    )
    assert manifest["frames"] == records
    assert manifest["provenance"] == {
        "lineage_clean": True, "analyzer_commit": "1234567", "run_hash": RUN,
    }
    assert "path" not in json.dumps(manifest).lower()
    with pytest.raises(ManifestError, match="clean"):
        build_manifest(
            set_id="coverage_02", source_sha=SOURCE, stream_index=0, time_base="1/60",
            locators=records, setkind="frozen_production_coverage",
            provenance={"lineage_clean": False, "analyzer_commit": "1234567", "run_hash": RUN},
        )


def test_immutable_writer_refuses_existing_path(tmp_path) -> None:
    manifest = build_manifest(
        set_id="case", source_sha=SOURCE, stream_index=0, time_base="1/30",
        locators=[{"pts": 0, "source_frame_index": 0}], setkind="canonical_uniform",
    )
    target = tmp_path / "manifest.json"
    expected = hashlib.sha256(serialize_manifest(manifest)).hexdigest()
    assert write_manifest_immutable(target, manifest) == expected
    before = target.read_bytes()
    with pytest.raises(ManifestError, match="already exists"):
        write_manifest_immutable(target, manifest)
    assert target.read_bytes() == before

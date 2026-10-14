import json

import pytest
from test_numeric_blind_review import inputs

from scripts.diagnostics.freeze_numeric_review import freeze, parse_response, verify_review_assets
from scripts.diagnostics.prepare_numeric_review import prepare
from scripts.e2e.run_dataset_case import sha256_file


def test_partial_explicit_labels_never_fill_missing_values():
    result = parse_response("Frame 1,1:40,unknown,\n2,absent,,3\n", {1, 2, 3})
    assert set(result) == {1, 2}
    assert result[1]["round_timer"] == {"kind": "value", "display": "1:40"}
    assert result[1]["ally_score"] == {"kind": "unknown"}
    assert result[1]["enemy_score"] is None
    assert result[2]["round_timer"] == {"kind": "absent"}
    assert result[2]["ally_score"] is None


def test_fractional_source_display_is_preserved_not_truncated():
    result = parse_response("1,0:27.46,0,1\n", {1})
    assert result[1]["round_timer"] == {"kind": "value", "display": "0:27.46"}


@pytest.mark.parametrize("text", [
    "", "全部承認します", "1,,,", "1,1:7,2,3", "1,1714,2,3",
    "1,1:60,2,3", "1,1:40,-1,3", "1,1:40,true,3", "1,1:40,2,NaN",
    "1,1:40,2,3\n1,1:40,2,3", "99,1:40,2,3", "1,1:40,2,3,4",
])
def test_unsupplied_ambiguous_or_malformed_labels_rejected(text):
    with pytest.raises(ValueError):
        parse_response(text, {1, 2})


def test_freezer_preserves_review_and_binds_exact_supplied_response(tmp_path):
    candidate, probe = inputs(tmp_path)
    review_dir = tmp_path / "review"
    prepare(candidate, probe, review_dir)
    receipt = review_dir / "review.json"
    before = sha256_file(receipt)
    response = tmp_path / "synthetic_response.csv"
    response.write_text("1,unknown,absent,\n", encoding="utf-8")
    output = tmp_path / "labels.json"
    result = freeze(review_dir, response, "synthetic-test-record-not-real-approval", output)
    assert sha256_file(receipt) == before
    assert result["review_receipt_sha256"] == before
    assert result["response_sha256"] == sha256_file(response)
    assert result["frames"][0]["labels"]["enemy_score"] is None
    assert result["production_adoption_approved"] is False
    assert result["identity_approved"] is False and result["event_timing_approved"] is False
    assert result["continuity_approved"] is False
    assert json.loads(receipt.read_text(encoding="utf-8"))["frames"][0]["labels"] is None
    with pytest.raises(FileExistsError):
        freeze(review_dir, response, "synthetic", output)


def test_changed_reviewed_image_or_missing_provenance_fails_closed(tmp_path):
    candidate, probe = inputs(tmp_path)
    review_dir = tmp_path / "review"
    prepare(candidate, probe, review_dir)
    response = tmp_path / "synthetic_response.csv"
    response.write_text("1,unknown,unknown,unknown\n", encoding="utf-8")
    with pytest.raises(ValueError, match="provenance"):
        freeze(review_dir, response, " ", tmp_path / "labels.json")
    (review_dir / "frame_01_round_timer.png").write_bytes(b"changed")
    with pytest.raises(ValueError, match="asset changed"):
        freeze(review_dir, response, "synthetic", tmp_path / "labels.json")


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -1, True])
def test_invalid_source_time_cannot_be_frozen_as_review_provenance(tmp_path, value):
    candidate, probe = inputs(tmp_path)
    review_dir = tmp_path / "review"
    receipt = prepare(candidate, probe, review_dir)
    receipt["frames"][0]["source_frame_pts"] = value
    with pytest.raises(ValueError, match="source binding"):
        verify_review_assets(review_dir, receipt)

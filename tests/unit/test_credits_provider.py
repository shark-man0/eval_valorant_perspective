from copy import deepcopy
from types import SimpleNamespace

import numpy as np
import pytest

from valorant_ai_coach.temporal.credits_provider import (
    CreditsCandidateReader,
    CreditsSupplementObserver,
)


def profile():
    return {
        "method": "development_credits_display_v1",
        "frame_size_px": [1920, 1080],
        "roi_xywh_native": [1790, 1024, 110, 36],
        "digits_xywh_relative": [30, 10, 62, 20],
        "minimum_ocr_confidence": 0.90,
    }


def test_bounded_credits_candidate_never_claims_actor_or_calibrated_geometry():
    reader = CreditsCandidateReader(profile())
    reader.ocr = SimpleNamespace(
        read=lambda _image, _crop: SimpleNamespace(
            value="2,650", confidence=0.96, sources=("synthetic_OCR",)
        )
    )
    measurement = reader.measure(np.zeros((1080, 1920, 3), np.uint8))
    assert measurement["value"] == 2650
    assert measurement["status"] == "CANDIDATE"
    assert measurement["subject"] == "screen_credits_display; actor_ownership_unresolved"
    assert measurement["roi_geometry_qualification"] == "unqualified_fixed_profile"
    assert measurement["digit_roi_xywh_native"] == [1820, 1034, 62, 20]


@pytest.mark.parametrize(
    "text,confidence",
    [
        ("2,650", 0.89),
        ("12650", 0.99),
        ("+500", 0.99),
        ("1,23", 0.99),
        ("10,000", 0.99),
        ("n 200", 0.99),
    ],
)
def test_unresolved_or_weak_credits_abstains(text, confidence):
    reader = CreditsCandidateReader(profile())
    reader.ocr = SimpleNamespace(
        read=lambda _image, _crop: SimpleNamespace(
            value=text, confidence=confidence, sources=("synthetic_OCR",)
        )
    )
    measured = reader.measure(np.zeros((1080, 1920, 3), np.uint8))
    assert measured["status"] == "UNKNOWN" and measured["value"] is None


def test_wrong_resolution_and_invalid_profile_fail_closed():
    reader = CreditsCandidateReader(profile())
    assert reader.measure(np.zeros((720, 1280, 3), np.uint8))["reason"] == (
        "frame_geometry_unmatched"
    )
    changed = profile()
    changed["minimum_ocr_confidence"] = 0.65
    with pytest.raises(ValueError, match="Frozen"):
        CreditsCandidateReader(changed)


def test_supplement_keeps_parent_suppliers_and_adds_only_value_evidence():
    parent_result = {
        "signals": ["spectator"],
        "raw": {"current": True},
        "context": {},
        "map_candidates": [],
        "supplier_observations": [
            {
                "producer_fingerprint": "a" * 64,
                "signals": ["spectator"],
                "raw": {},
                "context": {},
                "map_candidates": [],
            }
        ],
    }
    saved = deepcopy(parent_result)
    observer = object.__new__(CreditsSupplementObserver)
    observer.parent = SimpleNamespace(inspect=lambda _: parent_result)
    observer.credits_fingerprint = "b" * 64
    observer.inspect_credits = lambda _: {
        "signals": [],
        "map_candidates": [],
        "context": {"stream_kind": "hud_values"},
        "raw": {
            "hud_value_measurements": [
                {
                    "name": "credits",
                    "value": 2650,
                    "status": "CANDIDATE",
                    "subject": "screen_credits_display; actor_ownership_unresolved",
                }
            ],
            "ownership": "UNKNOWN",
            "formal_outputs": 0,
        },
    }
    result = observer.inspect(np.zeros((1080, 1920, 3), np.uint8))
    assert parent_result == saved
    assert result["signals"] == ["spectator"]
    assert result["supplier_observations"][:-1] == parent_result["supplier_observations"]
    assert result["supplier_observations"][-1]["signals"] == []
    assert result["supplier_observations"][-1]["raw"]["ownership"] == "UNKNOWN"


def test_default_language_asset_is_bound_and_unresolvable_directory_rejected(tmp_path, monkeypatch):
    from valorant_ai_coach.temporal import credits_provider

    asset = tmp_path / "eng.traineddata"
    asset.write_bytes(b"synthetic language data")
    monkeypatch.setattr(
        credits_provider.subprocess,
        "run",
        lambda *a, **k: SimpleNamespace(
            stdout=(f'List of available languages in "{tmp_path}" (1):\neng\n'
                    .encode("utf-8")),  # noqa: UP012 - explicit Text I/O contract stderr=b""
        ),
    )
    first = credits_provider.default_language_binding("synthetic")
    asset.write_bytes(b"changed language data")
    assert first != credits_provider.default_language_binding("synthetic")
    asset.unlink()
    with pytest.raises(ValueError, match="language asset required"):
        credits_provider.default_language_binding("synthetic")

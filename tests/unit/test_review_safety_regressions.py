import numpy as np
import pytest

from valorant_ai_coach.hud.classifier import HudStateClassifier
from valorant_ai_coach.hud.layout import HudLayout
from valorant_ai_coach.hud.models import accept_hud_value
from valorant_ai_coach.hud.readers import OpenCvHudFeatureReader, ReaderResult
from valorant_ai_coach.hud.templates import NumericFieldsReader
from valorant_ai_coach.resources import resource_path
from valorant_ai_coach.video.sampling import HudFrameSampler
from valorant_ai_coach.visual import WorldViewGate


@pytest.mark.parametrize("duration", [2999, 3000, 3600])
def test_long_recording_keeps_full_cadence_in_bounded_batches(duration):
    sampler = HudFrameSampler(max_pass_a_frames=12000)
    batches = list(sampler.pass_a_batches(duration))
    assert all(0 < len(batch) <= 12000 for batch in batches)
    samples = [item for batch in batches for item in batch]
    assert len(samples) == duration * 4 + 1
    assert [item.time_sec for item in samples] == [index / 4 for index in range(len(samples))]
    assert samples[-1].time_sec == duration
    assert set(samples[0].purposes) == {"general_hud", "change_sensitive_hud"}


def test_batch_boundaries_keep_purposes_and_fractional_endpoint():
    sampler = HudFrameSampler(general_fps=3, change_fps=4, max_pass_a_frames=2)
    samples = sampler.pass_a(1.1)
    assert samples[0].time_sec == 0 and samples[-1].time_sec == 1.1
    assert len({item.time_sec for item in samples}) == len(samples)
    assert next(item for item in samples if item.time_sec == 1).purposes == (
        "change_sensitive_hud",
        "general_hud",
    )


@pytest.mark.parametrize("background", [0, 30, 140])
def test_flat_wall_or_darkness_is_not_confirmed_smoke(background):
    layout = HudLayout.load(resource_path("config/hud_layout_1080p_v3.json"))
    image = np.full((1080, 1920, 3), background, dtype=np.uint8)
    rng = np.random.default_rng(123)
    for name in OpenCvHudFeatureReader.ANCHOR_NAMES:
        x1, y1, x2, y2 = layout.normalized_roi(name).pixel_bounds(1920, 1080)
        image[y1:y2, x1:x2] = rng.integers(0, 255, (y2 - y1, x2 - x1, 3), dtype=np.uint8)
    features = OpenCvHudFeatureReader(layout).observe_sequence([image, image], times=[0, 0.25])
    signals = {**features[-1].signals, "live_first_person": True}
    assert signals["hud_anchors_stable"]
    classified = HudStateClassifier().classify(signals)
    assert "vision_obscured_smoke" not in classified.state_flags
    assert signals["smoke_confidence"] < 0.65
    # An ambiguous low-detail view must not silently become a trustworthy scene.
    assert not classified.is_player_world_view_trustworthy
    supported = HudStateClassifier().classify(
        {
            **signals,
            "smoke_template_confirmed": True,
            "smoke_template_confirmed_confidence": 0.95,
            "smoke_confidence": 0.95,
        }
    )
    assert "vision_obscured_smoke" in supported.state_flags


class FieldReader:
    def __init__(self, results):
        self.results = iter(results)

    def read(self, image, roi):
        return next(self.results)


def test_composite_digits_preserve_corroboration_and_provenance():
    image = np.zeros((20, 50, 3), dtype=np.uint8)
    reader = FieldReader(
        [
            ReaderResult("100", 0.8, ("digit_templates", "tesseract_digits"), True),
            ReaderResult("50", 0.95, ("digit_templates",)),
        ]
    )
    result = NumericFieldsReader({"hp": (0, 0, 0.5, 1), "armor": (0.5, 0, 1, 1)}, reader).read(
        image, image
    )
    assert result.cross_checked
    assert {"digit_templates", "tesseract_digits"} <= set(result.sources)
    assert accept_hud_value(
        result.value, result.confidence, cross_checked=result.cross_checked
    ) == {"hp": 100, "armor": 50}


def test_one_corroborated_field_does_not_validate_another_weak_field():
    image = np.zeros((20, 50, 3), dtype=np.uint8)
    reader = FieldReader([ReaderResult("100", 0.8, cross_checked=True), ReaderResult("50", 0.7)])
    result = NumericFieldsReader({"hp": (0, 0, 0.5, 1), "armor": (0.5, 0, 1, 1)}, reader).read(
        image, image
    )
    assert not result.cross_checked
    assert (
        accept_hud_value(result.value, result.confidence, cross_checked=result.cross_checked)
        is None
    )


def test_visual_gate_rejects_stale_observations_and_nan_timestamp():
    observations = [
        {
            "time_sec": 1,
            "primary_state": "live_first_person",
            "state_flags": [],
            "view_context": {"is_player_world_view_trustworthy": True},
        }
    ]
    assert WorldViewGate.allows_event({"type": "shot", "time_sec": 1.5}, observations)
    for time in (1.501, 60, float("nan")):
        assert not WorldViewGate.allows_event({"type": "shot", "time_sec": time}, observations)
    assert not WorldViewGate.allows_event(
        {"type": "shot", "time_sec": 1.1}, observations, max_observation_age_sec=0.05
    )

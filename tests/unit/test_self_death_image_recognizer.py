"""Exercise image recognition and temporal confirmation without formal release."""
import hashlib
from dataclasses import replace

import numpy as np
import pytest

from tests.unit.test_killfeed_subject_reader import HASH, ability_fixture, fixture, glyph_fixture
from valorant_ai_coach.experimental.self_death_image import SelfDeathImageRecognizer
from valorant_ai_coach.experimental.subject_death import SourceBinding
from valorant_ai_coach.hud.report_header import ReportHeader


def setup(*, killer=False):
    reader, ocr, base = fixture(killer=killer)
    header = np.random.default_rng(24).integers(20, 220, (12, 50), dtype=np.uint8)
    recognizer = SelfDeathImageRecognizer(reader.profile, ocr, header, (0, 45, 80, 78),
        runtime_fingerprint=HASH, dependencies_fingerprint=HASH, native_step_ticks=1)
    return recognizer, base, header


def observe(recognizer, base, header, tick, *, report=True, marker=True,
            presence=False, **source_changes):
    image = base.copy()
    if not marker:
        image[20:40, :90] = image[20:40, 170:220] = 0
    if report:
        image[50:62, 10:60] = np.repeat(header[:, :, None], 3, axis=2)
    if presence:
        model = recognizer.report_presence_header
        assert model is not None
        image[65:75, 8:68] = np.repeat(model.reference[:, :, None], 3, axis=2)
    image[79, 239] = tick  # native frames are physically distinct
    source = SourceBinding(HASH, tick, 1, 60, 'segment',
        hashlib.sha256(image.tobytes()).hexdigest(), recognizer.code_fingerprint,
        recognizer.profile_fingerprint, HASH)
    source = replace(source, **source_changes)
    return recognizer.observe(image, source)


def test_two_independent_onsets_and_native_corroboration_keep_original_time():
    recognizer, base, header = setup()
    assert observe(recognizer, base, header, 0, report=False, marker=False).status == 'unknown'
    assert observe(recognizer, base, header, 1, marker=False).status == 'unknown'
    pending = [observe(recognizer, base, header, t) for t in range(2, 5)]
    assert all(r.status == 'pending' for r in pending)
    result = observe(recognizer, base, header, 5)
    assert result.status == 'prediction'
    assert result.onset_time_sec == 1/60
    assert result.confirmation_time_sec == 5/60
    assert {s.pts_ticks for s in result.evidence_sources} >= {0, 1, 2, 5}
    assert result.support >= .9
    assert result.qualified is False and result.formal_events == ()
    assert observe(recognizer, base, header, 6).status == 'duplicate'


def test_initial_persistent_report_and_marker_are_not_a_new_death():
    recognizer, base, header = setup()
    assert all(observe(recognizer, base, header, t).status == 'unknown' for t in range(8))


@pytest.mark.parametrize('killer', [False, True])
def test_ability_episode_requires_victim_role_and_native_confirmation(killer):
    reader, base = ability_fixture(killer=killer)
    header = np.random.default_rng(24).integers(20, 220, (12, 50), dtype=np.uint8)
    model = SelfDeathImageRecognizer(reader.profile, reader.reader, header, (0, 45, 80, 78),
        runtime_fingerprint=HASH, dependencies_fingerprint=HASH, native_step_ticks=1)
    observe(model, base, header, 0, report=False, marker=False)
    rows = [observe(model, base, header, tick) for tick in range(1, 6)]
    assert sum(r.status == 'prediction' for r in rows) == (0 if killer else 1)
    assert all(r.qualified is False and r.formal_events == () for r in rows)
    if not killer:
        result = next(r for r in rows if r.status == 'prediction')
        assert result.onset_time_sec == 1/60
        assert result.confirmation_time_sec > result.onset_time_sec
        assert result.subjects[0].weapon_support is None
        assert result.support <= result.subjects[0].ability_support
        assert observe(model, base, header, 6).status == 'duplicate'


@pytest.mark.parametrize('killer', [False, True])
def test_geometry_episode_requires_victim_and_keeps_geometry_distinct_from_ncc(killer):
    reader, base = glyph_fixture(killer=killer)
    header = np.random.default_rng(24).integers(20, 220, (12, 50), dtype=np.uint8)
    recognizer = SelfDeathImageRecognizer(reader.profile, reader.reader, header, (0, 45, 80, 78),
        runtime_fingerprint=HASH, dependencies_fingerprint=HASH, native_step_ticks=1)
    observe(recognizer, base, header, 0, report=False, marker=False)
    rows = [observe(recognizer, base, header, tick) for tick in range(1, 6)]
    assert sum(r.status == 'prediction' for r in rows) == (0 if killer else 1)
    for row in rows:
        assert row.qualified is False and row.formal_events == ()
        for subject in row.subjects:
            assert subject.weapon_geometry is not None
            assert subject.weapon_support is None
    if not killer:
        result = next(r for r in rows if r.status == 'prediction')
        assert result.onset_time_sec == 1/60
        assert result.support <= min(result.report_support,
                                    *result.subjects[0].marker_support)


def test_recording_player_as_killer_cannot_generate_a_death_prediction():
    recognizer, base, header = setup(killer=True)
    observe(recognizer, base, header, 0, report=False, marker=False)
    rows = [observe(recognizer, base, header, t) for t in range(1, 8)]
    assert all(r.status == 'unknown' and r.formal_events == () for r in rows)
    assert any(s.role == 'killer' for r in rows for s in r.subjects)


def test_older_self_killer_row_does_not_veto_new_independent_self_victim_row():
    killer, ocr, killer_image = fixture(killer=True)
    _, _, victim_image = fixture()
    profile = replace(killer.profile, frame_shape=(120, 240), search_roi=(0, 0, 240, 80))
    header = np.random.default_rng(24).integers(20, 220, (12, 50), dtype=np.uint8)
    recognizer = SelfDeathImageRecognizer(profile, ocr, header, (0, 80, 80, 118),
        runtime_fingerprint=HASH, dependencies_fingerprint=HASH, native_step_ticks=1)
    rows = []
    for tick in range(6):
        image = np.zeros((120, 240, 3), dtype=np.uint8)
        image[:80] = killer_image
        if tick:
            image[50:70] = victim_image[20:40]
            image[90:102, 10:60] = np.repeat(header[:, :, None], 3, axis=2)
        image[119, 239] = tick
        source = SourceBinding(HASH, tick, 1, 60, 'segment',
            hashlib.sha256(image.tobytes()).hexdigest(), recognizer.code_fingerprint,
            recognizer.profile_fingerprint, HASH)
        rows.append(recognizer.observe(image, source))
    assert {s.role for s in rows[-1].subjects} == {'killer', 'victim'}
    assert sum(r.status == 'prediction' for r in rows) == 1
    result = next(r for r in rows if r.status == 'prediction')
    assert result.onset_time_sec == 1/60
    assert result.formal_events == () and result.qualified is False


def test_single_frame_flash_and_interrupted_corroboration_are_not_predictions():
    recognizer, base, header = setup()
    observe(recognizer, base, header, 0, report=False, marker=False)
    assert observe(recognizer, base, header, 1).status == 'pending'
    rows = [observe(recognizer, base, header, t, marker=False) for t in range(2, 9)]
    assert not any(r.status == 'prediction' for r in rows)


def test_reader_dropout_requires_entire_new_corroboration_run_at_original_onset():
    recognizer, base, header = setup()
    observe(recognizer, base, header, 0, report=False, marker=False)
    assert observe(recognizer, base, header, 1).status == 'pending'
    assert observe(recognizer, base, header, 2, marker=False).status == 'unknown'
    assert all(observe(recognizer, base, header, t).status == 'pending'
               for t in range(3, 6))
    result = observe(recognizer, base, header, 6)
    assert result.status == 'prediction'
    assert result.onset_time_sec == 1/60
    assert result.confirmation_time_sec == 6/60
    assert 2 not in {s.pts_ticks for s in result.evidence_sources}


def test_report_dropout_cannot_reuse_the_old_episode():
    recognizer, base, header = setup()
    observe(recognizer, base, header, 0, report=False, marker=False)
    observe(recognizer, base, header, 1)
    observe(recognizer, base, header, 2, report=False)
    assert all(observe(recognizer, base, header, t).status == 'unknown'
               for t in range(3, 10))


@pytest.mark.parametrize('confirmation_tick,expected', [(61, 'prediction'), (62, 'unknown')])
def test_onset_expiry_uses_exact_native_time_not_float_reconstruction(confirmation_tick, expected):
    recognizer, base, header = setup()
    observe(recognizer, base, header, 0, report=False, marker=False)
    observe(recognizer, base, header, 1)
    for tick in range(2, confirmation_tick+1):
        result = observe(recognizer, base, header, tick, marker=tick >= confirmation_tick-3)
    assert result.status == expected
    if expected == 'prediction':
        assert result.onset_time_sec == 1/60
        assert result.confirmation_time_sec == 61/60
    assert result.formal_events == ()


@pytest.mark.parametrize('failure', ['gap', 'reordered', 'segment', 'dependencies', 'code'])
def test_source_changes_drop_pending_without_joining(failure):
    recognizer, base, header = setup()
    observe(recognizer, base, header, 0, report=False, marker=False)
    assert observe(recognizer, base, header, 1).status == 'pending'
    tick = 3 if failure == 'gap' else 0 if failure == 'reordered' else 2
    changes = {'segment_id': 'other'} if failure == 'segment' else (
        {'dependencies_fingerprint': 'b'*64} if failure == 'dependencies' else
        {'code_fingerprint': 'b'*64} if failure == 'code' else {})
    result = observe(recognizer, base, header, tick, **changes)
    assert result.status == 'unknown' and result.formal_events == ()
    assert recognizer.pending is None


def test_report_toggle_does_not_rearm_after_prediction():
    recognizer, base, header = setup()
    observe(recognizer, base, header, 0, report=False, marker=False)
    rows = [observe(recognizer, base, header, t) for t in range(1, 6)]
    assert sum(r.status == 'prediction' for r in rows) == 1
    assert observe(recognizer, base, header, 6, report=False, marker=False).status == 'duplicate'
    assert observe(recognizer, base, header, 7).status == 'duplicate'


def setup_with_presence():
    previous, base, caption = setup()
    reference = np.random.default_rng(72).integers(20, 220, (10, 60), dtype=np.uint8)
    regions = np.zeros_like(reference)
    regions[:, :18] = 1
    regions[:, 40:58] = 2
    mask = (regions > 0).astype(np.uint8)*255
    model = ReportHeader(reference, mask, regions, (33, 80), .1, .90)
    recognizer = SelfDeathImageRecognizer(previous.reader.profile, previous.reader.reader,
        caption, previous.report_search_roi, runtime_fingerprint=HASH,
        dependencies_fingerprint=HASH, native_step_ticks=1, report_presence_header=model)
    assert recognizer.code_fingerprint != previous.code_fingerprint
    return recognizer, base, caption


def test_independent_present_header_can_corroborate_after_actual_self_caption_onset():
    recognizer, base, header = setup_with_presence()
    observe(recognizer, base, header, 0, report=False, marker=False)
    assert observe(recognizer, base, header, 1, presence=True).status == 'pending'
    # Caption is unrecognized, but a different current-image header is positive.
    rows = [observe(recognizer, base, header, tick, report=False, presence=True)
            for tick in range(2, 5)]
    result = rows[-1]
    assert result.status == 'prediction'
    assert result.onset_time_sec == 1/60 and result.confirmation_time_sec == 4/60
    assert result.report_support == 0
    assert result.report_presence_support >= .90 and result.support >= .90
    assert {s.pts_ticks for s in result.evidence_sources} >= {0, 1, 2, 3, 4}
    assert result.qualified is False and result.formal_events == ()


def test_generic_header_never_substitutes_for_self_referential_onset():
    recognizer, base, header = setup_with_presence()
    observe(recognizer, base, header, 0, report=False, marker=False)
    rows = [observe(recognizer, base, header, tick, report=False, presence=True)
            for tick in range(1, 8)]
    # The generic witness is not evaluated until a real self-caption onset exists.
    assert all(row.status == 'unknown' and row.report_presence_support is None for row in rows)
    assert recognizer.pending is None


def test_missing_both_report_witnesses_still_clears_pending_without_recovery():
    recognizer, base, header = setup_with_presence()
    observe(recognizer, base, header, 0, report=False, marker=False)
    observe(recognizer, base, header, 1, presence=True)
    assert observe(recognizer, base, header, 2, report=False).status == 'unknown'
    rows = [observe(recognizer, base, header, tick, presence=True) for tick in range(3, 9)]
    assert all(row.status == 'unknown' for row in rows)
    assert recognizer.pending is None


def test_presence_witness_does_not_extend_original_deadline():
    recognizer, base, header = setup_with_presence()
    observe(recognizer, base, header, 0, report=False, marker=False)
    observe(recognizer, base, header, 1, presence=True)
    for tick in range(2, 63):
        result = observe(recognizer, base, header, tick, report=False, presence=True,
                         marker=tick >= 59)
    assert result.status == 'unknown' and recognizer.pending is None


def test_presence_model_requires_source_search_geometry_and_binds_actual_assets():
    recognizer, _, header = setup_with_presence()
    with pytest.raises(ValueError, match='presence geometry'):
        SelfDeathImageRecognizer(recognizer.reader.profile, recognizer.reader.reader,
            header, (0, 44, 80, 78), runtime_fingerprint=HASH,
            dependencies_fingerprint=HASH, native_step_ticks=1,
            report_presence_header=recognizer.report_presence_header)
    with pytest.raises(ValueError):
        recognizer.report_presence_header.mask[0, 0] = 0


@pytest.mark.parametrize('failure', ['gap', 'segment', 'code'])
def test_positive_presence_witness_cannot_override_source_continuity_failure(failure):
    recognizer, base, header = setup_with_presence()
    observe(recognizer, base, header, 0, report=False, marker=False)
    observe(recognizer, base, header, 1, presence=True)
    tick = 3 if failure == 'gap' else 2
    changes = ({'segment_id': 'other'} if failure == 'segment' else
               {'code_fingerprint': 'b'*64} if failure == 'code' else {})
    result = observe(recognizer, base, header, tick, report=False, presence=True, **changes)
    assert result.status == 'unknown' and recognizer.pending is None
    assert result.formal_events == () and result.qualified is False


def test_positive_presence_witness_does_not_rearm_an_emitted_episode():
    recognizer, base, header = setup_with_presence()
    observe(recognizer, base, header, 0, report=False, marker=False)
    rows = [observe(recognizer, base, header, tick, presence=True) for tick in range(1, 5)]
    assert sum(row.status == 'prediction' for row in rows) == 1
    for tick in range(5, 10):
        row = observe(recognizer, base, header, tick, report=False, presence=True)
        assert row.status == 'duplicate' and row.formal_events == ()


def test_caption_can_move_above_presence_calibration_without_moving_that_calibration():
    original, base, caption = setup_with_presence()
    separate = SelfDeathImageRecognizer(original.reader.profile, original.reader.reader,
        caption, (0, 0, 80, 78), runtime_fingerprint=HASH,
        dependencies_fingerprint=HASH, native_step_ticks=1,
        report_presence_header=original.report_presence_header,
        report_presence_search_roi=original.report_search_roi)
    assert separate.code_fingerprint != original.code_fingerprint

    def run(model):
        results = []
        for tick in range(6):
            image = base.copy()
            if tick == 0:
                image[20:40, :90] = image[20:40, 170:220] = 0
            if tick == 1:
                image[5:17, 10:60] = np.repeat(caption[:, :, None], 3, axis=2)
            elif tick > 1:
                image[65:75, 8:68] = np.repeat(
                    model.report_presence_header.reference[:, :, None], 3, axis=2)
            image[79, 239] = tick
            binding = SourceBinding(HASH, tick, 1, 60, 'moved-caption',
                hashlib.sha256(image.tobytes()).hexdigest(), model.code_fingerprint,
                model.profile_fingerprint, HASH)
            results.append(model.observe(image, binding))
        return results

    before, after = run(original), run(separate)
    assert not any(r.status == 'prediction' for r in before)
    assert sum(r.status == 'prediction' for r in after) == 1
    assert after[1].report_match_roi == (10, 5, 60, 17)
    assert after[4].status == 'prediction' and after[4].onset_time_sec == 1/60
    assert after[4].report_support == 0 and after[4].report_match_roi is None
    assert after[4].report_presence_support >= .90
    assert all(not r.qualified and r.formal_events == () for r in after)


def test_duplicate_captions_in_wider_search_stay_ambiguous():
    original, base, caption = setup_with_presence()
    model = SelfDeathImageRecognizer(original.reader.profile, original.reader.reader,
        caption, (0, 0, 80, 78), runtime_fingerprint=HASH,
        dependencies_fingerprint=HASH, native_step_ticks=1,
        report_presence_header=original.report_presence_header,
        report_presence_search_roi=original.report_search_roi)
    image = base.copy()
    image[5:17, 10:60] = image[25:37, 10:60] = np.repeat(caption[:, :, None], 3, axis=2)
    source = SourceBinding(HASH, 0, 1, 60, 'ambiguous-caption',
        hashlib.sha256(image.tobytes()).hexdigest(), model.code_fingerprint,
        model.profile_fingerprint, HASH)
    result = model.observe(image, source)
    assert result.report_support == 0 and result.report_match_roi is None
    assert result.status == 'unknown' and result.formal_events == ()

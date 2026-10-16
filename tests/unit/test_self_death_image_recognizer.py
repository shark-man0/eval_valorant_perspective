"""Exercise image recognition and temporal confirmation without formal release."""
import hashlib
from dataclasses import replace

import numpy as np
import pytest

from tests.unit.test_killfeed_subject_reader import HASH, fixture
from valorant_ai_coach.experimental.self_death_image import SelfDeathImageRecognizer
from valorant_ai_coach.experimental.subject_death import SourceBinding


def setup(*, killer=False):
    reader, ocr, base = fixture(killer=killer)
    header = np.random.default_rng(24).integers(20, 220, (12, 50), dtype=np.uint8)
    recognizer = SelfDeathImageRecognizer(reader.profile, ocr, header, (0, 45, 80, 78),
        runtime_fingerprint=HASH, dependencies_fingerprint=HASH, native_step_ticks=1)
    return recognizer, base, header


def observe(recognizer, base, header, tick, *, report=True, marker=True, **source_changes):
    image = base.copy()
    if not marker:
        image[20:40, :90] = image[20:40, 170:220] = 0
    if report:
        image[50:62, 10:60] = np.repeat(header[:, :, None], 3, axis=2)
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


def test_recording_player_as_killer_cannot_generate_a_death_prediction():
    recognizer, base, header = setup(killer=True)
    observe(recognizer, base, header, 0, report=False, marker=False)
    rows = [observe(recognizer, base, header, t) for t in range(1, 8)]
    assert all(r.status == 'unknown' and r.formal_events == () for r in rows)
    assert any(s.role == 'killer' for r in rows for s in r.subjects)


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

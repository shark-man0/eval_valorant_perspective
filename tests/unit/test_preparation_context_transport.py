"""A short native boundary proof must not truncate its observed prep episode."""
from copy import deepcopy

import pytest

from tests.integration.test_hud_video_processor import hud_event
from tests.unit.test_global_snapshot_evidence import builder, source


def phase(time):
    row = source(time)
    row['state_flags'] = ['buy_phase_banner']
    row['values']['buy_phase_visible'] = True
    row['quality']['roi_confidence']['center_phase_banner_semantic_text'] = .95
    return row


def start():
    event = hud_event('start', 4, 'round_start')
    event['attributes'] = {'evidence_provenance': {
        'scope': 'global_system', 'source_pts_sec': 4, 'source_epoch': 'synthetic',
        'source_video_sha256': 'a' * 64, 'qualification_sha256': 'b' * 64,
        'profile_fingerprint': 'c' * 64, 'recognizer_fingerprint': 'd' * 64,
        'preparation_pts_sec': [3, 3.9],
    }}
    return event


def test_same_observed_episode_extends_context_without_changing_boundary_or_identity():
    rows = [phase(i / 10) for i in range(10, 40)]
    event = start()
    before = deepcopy((rows, event))
    assert builder()._preparation_context_start(rows, 4, start_event=event) == 1
    assert (rows, event) == before
    assert all(not r['values']['player_specific_hud_valid'] for r in rows)
    assert event['time_sec'] == 4


@pytest.mark.parametrize('blocker', ['unknown', 'weak_phase', 'missing_phase_value'])
def test_uncertain_or_unqualified_point_separates_preparation_episodes(blocker):
    rows = [phase(i / 10) for i in range(10, 40)]
    row = rows[19]  # 2.9: immediately before the native proof.
    if blocker == 'unknown':
        row['state_flags'] = []
        row['values']['buy_phase_visible'] = False
    elif blocker == 'weak_phase':
        row['quality']['roi_confidence']['center_phase_banner_semantic_text'] = .89
    else:
        row['values']['buy_phase_visible'] = False
    assert builder()._preparation_context_start(rows, 4, start_event=start()) == 3


def test_unmatched_older_episode_cannot_replace_native_context():
    rows = [phase(i / 10) for i in range(10, 29)] + [source(3.9)]
    assert builder()._preparation_context_start(rows, 4, start_event=start()) == 3


def test_native_context_is_preserved_without_sampled_phase_coverage():
    assert builder()._preparation_context_start([], 4, start_event=start()) == 3


def test_gap_and_previous_boundary_cannot_be_crossed():
    b = builder()
    assert b._preparation_context_start([phase(1), phase(2), phase(3.1), phase(3.9)],
                                        4, start_event=start()) == 3
    assert b._preparation_context_start([phase(3.6), phase(3.9)], 4,
                                        floor_sec=3.5, start_event=start()) == 3.6


def test_actual_source_break_splits_context_before_extension():
    rows = [phase(i / 10) for i in range(10, 40)]
    windows = builder()._round_windows(rows, [start()], 5, continuity_breaks=(2.9,))
    active = next(w for w in windows if w.start_event_sec == 4)
    assert active.start_sec == 2.9
    assert active.start_sec >= 2.9
    assert not any(w.start_sec < 2.9 < w.end_sec for w in windows)

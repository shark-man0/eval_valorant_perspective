import cv2
import numpy as np
import pytest

from valorant_ai_coach.visual.development_ownership import DevelopmentOwnershipEvidence


def inspect(frame, spec, engine=None):
    return (engine or DevelopmentOwnershipEvidence()).inspect(
        frame, spec, minimap_roi=[0, 0, .4, .4], source_id='synthetic',
        acquisition_id='one-window', time_sec=0, frame_index=0)


@pytest.fixture
def screen_case(tmp_path):
    frame = np.zeros((200, 400, 3), np.uint8)
    glyph = np.random.default_rng(50).integers(0, 256, (15, 51, 3), np.uint8)
    frame[140:155, 40:91] = glyph
    path = tmp_path/'glyph.png'
    cv2.imwrite(str(path), glyph)
    probe = {'claim': 'spectator_controls', 'roi': [0, .6, .4, .9],
             'template_path': str(path)}
    spec = {'mode': 'screen_context_v1', 'frame_size_px': [400, 200],
            'slot_review': 'source_reviewed_not_qualified', 'probes': [probe]}
    return frame, spec, path


def test_independent_screen_presence_blocks_but_never_assigns_recorder(screen_case):
    frame, spec, _ = screen_case
    result = inspect(frame, spec)
    assert result['block_position_candidate'] is True
    assert result['view_candidate'] == 'spectator_context'
    assert result['actor_candidate'] == 'non_recorder_view_candidate'
    assert result['ownership'] == 'UNKNOWN'
    assert result['positive_recorder_ownership_evidence'] is False
    assert result['observed_cues'][0]['independent_of_minimap_pixels'] is True


def test_shared_hud_and_duplicate_cues_are_not_identity_votes(screen_case):
    frame, spec, _ = screen_case
    spec['probes'][0]['claim'] = 'first_person_hud'
    spec['probes'] *= 3
    result = inspect(frame, spec)
    assert result['evidence_families'] == ['shared_first_person_hud']
    assert result['ownership'] == result['actor_candidate'] == 'UNKNOWN'
    assert result['positive_recorder_ownership_evidence'] is False
    assert result['block_position_candidate'] is False


def test_death_report_is_overlay_not_recorder_death(screen_case):
    frame, spec, _ = screen_case
    spec['probes'][0]['claim'] = 'death_report'
    result = inspect(frame, spec)
    assert result['view_candidate'] == 'overlay_context'
    assert result['actor_candidate'] == 'UNKNOWN'
    assert result['block_position_candidate'] is True
    assert 'death' not in result or result['death'] is None


def test_purchase_presence_blocks_live_path_without_assigning_owner(screen_case):
    frame, spec, _ = screen_case
    spec['probes'][0].update(claim='purchase_phase', feature_mode='gray_v1')
    result = inspect(frame, spec)
    assert result['view_candidate'] == 'purchase_context'
    assert result['block_position_candidate'] is True
    assert result['actor_candidate'] == result['ownership'] == 'UNKNOWN'
    assert result['positive_recorder_ownership_evidence'] is False
    frame[:] = 0
    missing = inspect(frame, spec)
    assert missing['view_candidate'] == 'UNKNOWN'
    assert missing['positive_recorder_ownership_evidence'] is False


def test_undetected_pattern_is_unknown_not_proof_of_self(screen_case):
    frame, spec, _ = screen_case
    frame[:] = 0
    result = inspect(frame, spec)
    assert result['view_candidate'] == result['ownership'] == 'UNKNOWN'
    assert result['observed_cues'][0]['status'] == 'not_detected'
    assert result['positive_recorder_ownership_evidence'] is False


def test_invalid_or_overlapping_slots_fail_closed(screen_case):
    frame, spec, _ = screen_case
    spec['probes'][0]['roi'] = [0, 0, .4, .4]
    assert inspect(frame, spec)['block_position_candidate'] is True
    spec['frame_size_px'] = [800, 400]
    assert inspect(frame, spec)['status'] == 'unavailable'


def test_changed_or_missing_reference_is_not_stale_evidence(screen_case):
    frame, spec, path = screen_case
    engine = DevelopmentOwnershipEvidence()
    before = inspect(frame, spec, engine)
    cv2.imwrite(str(path), np.random.default_rng(2).integers(0, 256, (15, 51, 3), np.uint8))
    after = inspect(frame, spec, engine)
    assert before['reference_fingerprint'] != after['reference_fingerprint']
    path.unlink()
    assert inspect(frame, spec, engine)['block_position_candidate'] is True
    assert inspect(frame, None, engine)['status'] == 'disabled'

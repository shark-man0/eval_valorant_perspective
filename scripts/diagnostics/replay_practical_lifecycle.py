"""Replay archived actual reader observations; not fresh recognition or qualification."""
from __future__ import annotations

import argparse
import hashlib
import json
from copy import deepcopy
from pathlib import Path

from valorant_ai_coach.hud.global_lifecycle import global_recognizer_fingerprint
from valorant_ai_coach.hud.models import empty_hud_values
from valorant_ai_coach.hud.native_system_input import GLOBAL_CONFIDENCES, GLOBAL_VALUES
from valorant_ai_coach.hud.practical_lifecycle import replay_practical_boundaries
from valorant_ai_coach.hud.unedited_input import UneditedInputContract


def project_archive(document):
    """Preserve PTS/pixels/values, normalizing only the local collection index."""
    rows = []
    for index, row in enumerate(document['rows']):
        observation = deepcopy(row['observation'])
        values = empty_hud_values()
        values.update({k: deepcopy(v) for k, v in observation['values'].items()
                       if k in GLOBAL_VALUES})
        observation['values'] = values
        observation['frame_index'] = index
        observation['view_context']['is_player_world_view_trustworthy'] = False
        observation['quality']['roi_confidence'] = {
            k: v for k, v in observation['quality']['roi_confidence'].items()
            if k in GLOBAL_CONFIDENCES
        }
        ui = row['native_ui_measurements']
        if not {'phase_scan_valid', 'phase_present', 'phase_confidence'} <= set(ui):
            raise ValueError('archive lacks current-frame phase presence measurement')
        evidence = {
            'assured_phase_scan_valid': ui['phase_scan_valid'],
            'assured_phase_present': ui['phase_present'],
            'assured_phase_confidence': ui['phase_confidence'],
            'assured_round_result_present': ui.get('round_result_matched') is True,
            'assured_round_result_confidence': ui.get('round_result_confidence', 0.0),
            **{k: True for k in ('content_jump', 'discontinuity') if ui.get(k) is True},
        }
        rows.append({
            'source_video_sha256': document['source_video_sha256'],
            'source_epoch': row['source_epoch'], 'source_pts_ticks': row['source_pts_ticks'],
            'source_time_base': row['source_time_base'], 'source_pts_sec': row['pts_sec'],
            'source_pixel_sha256': row['source_pixel_sha256'],
            'system_observation': observation, 'system_evidence': evidence,
        })
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--video', type=Path, required=True)
    parser.add_argument('--input-contract', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('archives', type=Path, nargs='+')
    args = parser.parse_args()
    digest = hashlib.sha256()
    with args.video.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    contract = UneditedInputContract.load(args.input_contract,
                                         source_video_sha256=digest.hexdigest())
    results = []
    for path in args.archives:
        content = path.read_bytes()
        document = json.loads(content)
        if document['source_video_sha256'] != contract.source_video_sha256:
            raise ValueError('archive belongs to another video')
        rows = project_archive(document)
        boundaries, diagnostics = replay_practical_boundaries(
            rows, contract, native_step_ticks=document['native_step_ticks'],
            profile_fingerprint=document['profile_fingerprint'],
        )
        results.append({
            'archive': str(path), 'archive_sha256': hashlib.sha256(content).hexdigest(),
            'archive_recognizer_fingerprint': document['recognizer_fingerprint'],
            'processed_observations': len(rows),
            'boundaries': [b.to_dict() for b in boundaries],
            'source_break_count': sum(d['source_break'] for d in diagnostics),
            'terminal_state': diagnostics[-1]['state'],
        })
    report = {
        'scope': 'Archived actual reader replay only; no fresh recognition or qualification',
        'source_video_sha256': contract.source_video_sha256,
        'input_contract_sha256': contract.fingerprint,
        'current_recognizer_fingerprint': global_recognizer_fingerprint(),
        'strict_e2e_reexecuted': False, 'precision_verified': False,
        'qualification_created': False, 'formal_events_released': 0,
        'results': results,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'archives': len(results), 'formal_events': 0,
                      'provisional_boundaries': sum(len(r['boundaries']) for r in results)}))


if __name__ == '__main__':
    main()

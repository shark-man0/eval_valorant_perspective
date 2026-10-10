"""Fresh source-bound UI-start diagnostics; never releases unqualified events."""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from dataclasses import asdict
from pathlib import Path

from valorant_ai_coach.hud.analyzers import RealHudAnalyzer
from valorant_ai_coach.hud.global_lifecycle import global_recognizer_fingerprint
from valorant_ai_coach.hud.native_system_input import collect_native_system_observations
from valorant_ai_coach.hud.unedited_input import UneditedInputContract
from valorant_ai_coach.hud.unedited_ui_start import UneditedUiStartTracker
from valorant_ai_coach.video import VideoService


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--video', type=Path, required=True)
    p.add_argument('--input-contract', type=Path, required=True)
    p.add_argument('--layout', type=Path, required=True)
    p.add_argument('--end', type=float, required=True)
    p.add_argument('--native-step-ticks', type=int, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    if args.output.exists():
        raise ValueError('new output required')
    digest = hashlib.sha256()
    with args.video.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    contract_bytes = args.input_contract.read_bytes()
    contract = UneditedInputContract.load(
        args.input_contract, source_video_sha256=digest.hexdigest(),
    )
    scans = []

    def sink(row):
        measured = (row.get('semantic_text_measurements') or {}).get('buy_phase_template', {})
        groups = measured.get('groups', [])
        scans.append({
            'source_pts_sec': row['source_pts_sec'],
            'source_pixel_sha256': row['source_pixel_sha256'],
            'phase_scan_valid': (row['geometry_calibrated'] is True and len(groups) >= 3
                                 and all(g['reason'] != 'shape_mismatch' for g in groups)),
            'measurement': measured,
        })

    analyzer = RealHudAnalyzer(args.layout, diagnostic_sink=sink)
    profile = analyzer.fingerprint()
    code = global_recognizer_fingerprint()
    started = time.perf_counter()
    with VideoService().native_window(
        args.video, start_sec=0, end_sec=args.end, source_video_sha256=contract.source_video_sha256,
        png_prediction='up', max_png_bytes=1_000_000_000,
    ) as frames:
        def observe(source):
            return analyzer.observe_frames(source, _build_events=False).observations

        rows = collect_native_system_observations(
            frames, native_step_ticks=args.native_step_ticks,
            observe=observe, fingerprint=analyzer.fingerprint,
        )
        if len(rows) != len(scans):
            raise ValueError('phase scan coverage mismatch')
        tracker = UneditedUiStartTracker(contract, native_step_ticks=args.native_step_ticks)
        candidates = []
        for row, scan in zip(rows, scans, strict=True):
            if (row['source_pts_sec'] != scan['source_pts_sec']
                    or row['source_pixel_sha256'] != scan['source_pixel_sha256']):
                raise ValueError('phase/system frame mismatch')
            decision = tracker.advance(row, phase_scan_valid=scan['phase_scan_valid'])
            if decision:
                candidates.append(asdict(decision))
    if (args.input_contract.read_bytes() != contract_bytes
            or profile != analyzer.fingerprint() or code != global_recognizer_fingerprint()):
        raise ValueError('terminal input/profile/code changed')
    report = {
        'scope': 'fresh native development diagnostic; no reader/UI qualification',
        'source_video_sha256': contract.source_video_sha256,
        'input_contract_sha256': contract.fingerprint,
        'profile_fingerprint': profile, 'recognizer_fingerprint': code,
        'processed_frames': len(rows), 'native_step_ticks': args.native_step_ticks,
        'window': {'start': 0, 'end': args.end},
        'phase_scan_valid_frames': sum(s['phase_scan_valid'] for s in scans),
        'rows': rows, 'phase_scans': scans, 'candidates': candidates,
        'released_events': 0, 'qualification_created': False,
        'wall_sec': time.perf_counter()-started,
        'canonical_current': None, 'canonical_delta': None,
    }
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({k: report[k] for k in (
        'processed_frames', 'phase_scan_valid_frames', 'wall_sec', 'released_events',
    )} | {'candidate_count': len(candidates)}))


if __name__ == '__main__':
    main()

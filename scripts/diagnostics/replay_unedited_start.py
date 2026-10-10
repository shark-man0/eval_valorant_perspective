"""Replay archived reader outputs under explicit assurance; not qualification."""
from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict
from pathlib import Path

import cv2

from valorant_ai_coach.hud.unedited_input import UneditedInputContract
from valorant_ai_coach.hud.unedited_ui_start import UneditedUiStartTracker


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input-contract', type=Path, required=True)
    parser.add_argument('--reader-report', type=Path, required=True)
    parser.add_argument('--image-report', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('new output required')
    bound = {p: p.read_bytes() for p in (
        args.input_contract, args.reader_report, args.image_report,
    )}
    reader = json.loads(bound[args.reader_report])
    images = json.loads(bound[args.image_report])
    contract = UneditedInputContract.load(
        args.input_contract, source_video_sha256=reader['source_video_sha256'],
    )
    if images['source_video_sha256'] != contract.source_video_sha256:
        raise ValueError('image/reader sources differ')
    image_rows = {r['source_pts_ticks']: r for w in images['windows'] for r in w['rows']}
    image_paths = {int(Path(p).stem.removeprefix('frame_')): (Path(p), sha)
                   for p, sha in images['native_png_sha256'].items()}
    tracker = UneditedUiStartTracker(contract, native_step_ticks=reader['native_step_ticks'])
    candidates = []
    verified = 0
    for row in reader['rows']:
        tick = row['source_pts_ticks']
        if tick in image_rows:
            image_row = image_rows[tick]
            path, sha = image_paths[tick]
            encoded = path.read_bytes()
            image = cv2.imread(str(path))
            if (hashlib.sha256(encoded).hexdigest() != sha or image is None
                    or hashlib.sha256(image.tobytes()).hexdigest() != row['source_pixel_sha256']
                    or row['source_pixel_sha256'] != image_row['source_pixel_sha256']):
                raise ValueError('archived reader/image binding mismatch')
            verified += 1
        # Conditional replay only: archived geometry is effective on every row.
        # This does not attest a fresh producer's phase scan availability.
        candidate = tracker.advance(row, phase_scan_valid=True)
        if candidate:
            candidates.append(asdict(candidate))
    if any(path.read_bytes() != data for path, data in bound.items()):
        raise ValueError('terminal input binding changed')
    result = {
        'scope': 'conditional archived-reader replay; not runtime qualification',
        'input_sha256': {str(p): hashlib.sha256(b).hexdigest() for p, b in bound.items()},
        'source_video_sha256': contract.source_video_sha256,
        'processed_frames': len(reader['rows']), 'verified_saved_image_overlap_frames': verified,
        'phase_scan_valid_assumption': 'conditional: fresh producer scan guard still required',
        'candidates': candidates, 'released_events': 0, 'qualification_created': False,
        'canonical_current': None, 'canonical_delta': None,
    }
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({'frames': len(reader['rows']), 'image_overlap_verified': verified,
                      'candidate_count': len(candidates), 'released_events': 0}))


if __name__ == '__main__':
    main()

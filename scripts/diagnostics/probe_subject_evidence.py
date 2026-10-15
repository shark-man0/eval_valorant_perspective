"""Private source-image/temporal probes; never authorize a formal Death event.

Use a frozen source-only plan. Evaluation labels are read AFTER recognition.
Archived HUD measurements must bind the unchanged runtime and freshly verified
native pixels; they are not reported as newly recognized HUD evidence.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import shutil
import subprocess
import time
from collections import Counter
from pathlib import Path

import cv2

from valorant_ai_coach.experimental.subject_death import (
    ProbeFrame,
    SourceBinding,
    SubjectDeathProbe,
    SubjectObservation,
    SubjectRelation,
    SubjectRole,
    probe_fingerprint,
)
from valorant_ai_coach.hud.global_lifecycle import global_recognizer_fingerprint
from valorant_ai_coach.hud.templates import TesseractTextReader
from valorant_ai_coach.video import VideoService


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''):
            digest.update(block)
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ['plan', 'video', 'evaluation-labels', 'continuous-measurements',
                 'tesseract', 'tessdata', 'output']:
        parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('preserve old evidence: use a new private output directory')
    plan = json.loads(args.plan.read_text(encoding='utf-8'))
    inputs = {str(p): sha(p) for p in [args.plan, args.continuous_measurements,
                                     args.tesseract, args.tessdata/'eng.traineddata',
                                     Path(__file__)]}
    for path, value in plan['input_sha256'].items():
        if sha(path) != value:
            raise ValueError('frozen plan input mismatch')
        inputs[path] = value
    for executable in ['ffmpeg', 'ffprobe']:
        resolved = shutil.which(executable)
        if resolved is None:
            parser.error(executable+' is required')
        inputs[resolved] = sha(resolved)
    source_sha = plan['source_sha256']
    if sha(args.video) != source_sha:
        raise ValueError('source video mismatch')
    runtime = global_recognizer_fingerprint()
    code = probe_fingerprint(runtime_fingerprint=runtime)
    config = sha(args.plan)
    deps = hashlib.sha256(json.dumps({
        'python': platform.python_version(), 'opencv': cv2.__version__,
        'executable_sha256': sha(args.tesseract),
        'eng_data_sha256': sha(args.tessdata/'eng.traineddata'),
        'decoder_binary_hashes': {name: sha(shutil.which(name))
                                  for name in ['ffmpeg', 'ffprobe']},
        'tesseract_version': subprocess.check_output(
            [str(args.tesseract), '--version'], text=True, encoding='utf-8',
        ),
    }, sort_keys=True).encode('utf-8')).hexdigest()
    args.output.mkdir(parents=True)
    rows = []
    started = time.monotonic()
    reader = TesseractTextReader(language='eng', executable=str(args.tesseract),
                                 tessdata_dir=str(args.tessdata), psm=7)
    bounds = tuple(plan['victim_ocr_bounds_px'])
    x1, y1, x2, y2 = bounds
    for number, record in enumerate(plan['review_negative_frames']):
        path = Path(record['path'])
        inputs[str(path)] = sha(path)
        image = cv2.imread(str(path))
        if (inputs[str(path)] != record['encoded_sha256'] or image is None
                or hashlib.sha256(image.tobytes()).hexdigest() != record['pixel_sha256']):
            raise ValueError('source raster mismatch')
        reading = reader.read(image, image[y1:y2, x1:x2])
        accepted = (reading.value if reading.value is not None
                    and reading.confidence >= .90 else None)
        numerator, denominator = (int(n) for n in record['source_time_base'].split('/'))
        source = SourceBinding(source_sha, record['source_pts_ticks'], numerator, denominator,
                               str(record['source_epoch']), record['pixel_sha256'],
                               code, config, deps)
        observation = SubjectObservation(
            f'victim-candidate-{number}', source, SubjectRole.VICTIM, SubjectRelation.UNKNOWN,
            (hashlib.sha256(str(accepted).encode('utf-8')).hexdigest()
             if accepted is not None else None),
            reading.confidence, 'frozen_tesseract_victim_crop_psm7', bounds,
        )
        decision = SubjectDeathProbe(native_step_ticks=256, max_corroboration_sec=1).observe(
            ProbeFrame(source, (observation,)),
        )
        rows.append({'source_pts_ticks': source.pts_ticks, 'split': record['split'],
                     'reading': accepted, 'observation': observation.to_dict(),
                     'decision': decision.to_dict()})
    # Evaluation-only labels were never supplied to a reader or the probe.
    labels = json.loads(args.evaluation_labels.read_text(encoding='utf-8'))
    inputs[str(args.evaluation_labels)] = sha(args.evaluation_labels)
    truth = {r['source_pts_ticks']: r for r in labels['rows']}
    counts = Counter()
    for row in rows:
        label = truth[row['source_pts_ticks']]
        if label['pixel_sha256'] != row['observation']['source']['pixel_sha256']:
            raise ValueError('evaluation source mismatch')
        actual, expected = row['reading'], label['expected_display']
        outcome = ('negative_rejected' if actual is None else 'negative_false_accept') if (
            expected is None
        ) else ('unknown' if actual is None else 'correct' if actual == expected else 'wrong')
        row['ocr_evaluation'] = outcome
        counts[outcome] += 1
    archived = json.loads(args.continuous_measurements.read_text(encoding='utf-8'))
    if archived['code_fingerprint'] != runtime or archived['source_sha256'] != source_sha:
        raise ValueError('archived context does not bind unchanged HUD runtime/source')
    continuous = []
    for old, window in zip(archived['results'], archived['windows'], strict=True):
        name, start, end = window
        probe = SubjectDeathProbe(native_step_ticks=256, max_corroboration_sec=1)
        previous = None
        decisions = []
        with VideoService().native_window(args.video, start_sec=start, end_sec=end,
                                          source_video_sha256=source_sha) as frames:
            if len(frames) != old['frames']:
                raise ValueError('native frame count mismatch')
            for native, measured in zip(frames, old['diagnostics'], strict=True):
                if (native.pixel_sha256 != measured['source_pixel_sha256']
                        or abs(native.time_sec-measured['source_pts_sec']) > 1e-9):
                    raise ValueError('native source/context binding mismatch')
                source = SourceBinding(source_sha, native.pts_ticks,
                                       native.time_base.numerator, native.time_base.denominator,
                                       str(native.source_epoch), native.pixel_sha256,
                                       code, config, deps)
                observations = []
                signals = measured['signals']
                for role, present, confidence, roi in [
                    (SubjectRole.REPORT, signals.get('combat_report_visible') is True,
                     signals.get('combat_report_confidence'), (1500, 300, 1920, 900)),
                    (SubjectRole.SPECTATOR,
                     measured['classified_state']['primary_state'] == 'spectator_first_person',
                     measured['classified_state']['confidence'], (0, 700, 400, 900)),
                ]:
                    if present:
                        observations.append(SubjectObservation(
                            f'{name}-{native.pts_ticks}-{role}', source, role,
                            SubjectRelation.UNKNOWN, None, confidence, 'archived_current_hud_'+role,
                            roi,
                        ))
                decisions.append(probe.observe(ProbeFrame(
                    source, tuple(observations), previous.pts_ticks if previous else None,
                    sha(args.continuous_measurements) if previous else None,
                    previous is not None and previous.pixel_sha256 == source.pixel_sha256,
                )).to_dict())
                previous = source
        continuous.append({'name': name, 'frames': len(decisions), 'decisions': decisions})
    if (global_recognizer_fingerprint() != runtime
            or probe_fingerprint(runtime_fingerprint=runtime) != code
            or sha(args.video) != source_sha
            or any(sha(path) != value for path, value in inputs.items())):
        raise ValueError('terminal source/code/asset mismatch')
    result = {'scope': 'Candidate-only experiment; no formal qualification or production adoption',
              'source_sha256': source_sha, 'probe_fingerprint': code,
              'runtime_fingerprint': runtime, 'dependencies_fingerprint': deps,
              'input_sha256': inputs, 'rows': rows, 'victim_ocr_counts': dict(counts),
              'continuous': continuous, 'formal_events': [], 'owned_facts': [],
              'self_subject_qualified_count': 0, 'new_blind_holdout': False,
              'hud_continuous_context': 'Existing unchanged-code measurements, '
              'freshly verified native pixels/PTS; not new HUD recognition',
              'wall_sec': time.monotonic()-started, 'terminal_hashes_verified': True}
    (args.output/'result.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({'victim_ocr_counts': dict(counts), 'source_review_images': len(rows),
                      'native_context_frames': sum(w['frames'] for w in continuous),
                      'formal_events': 0, 'wall_sec': result['wall_sec']}))


if __name__ == '__main__':
    main()

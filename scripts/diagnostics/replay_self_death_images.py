"""Recompute non-releasing image predictions on verified native frame caches.

One runner and runtime fingerprint cover all positive/negative input manifests.
Dataset hashes are recorded separately; labels/GT are never reader inputs.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import shutil
import subprocess
import time
from dataclasses import asdict
from fractions import Fraction
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from valorant_ai_coach.experimental.killfeed_subject import KillfeedSubjectProfile
from valorant_ai_coach.experimental.self_death_image import (
    SelfDeathImageRecognizer,
    image_runtime_fingerprint,
)
from valorant_ai_coach.experimental.subject_death import SourceBinding
from valorant_ai_coach.hud.report_header import ReportHeader
from valorant_ai_coach.hud.templates import TesseractTextReader
from valorant_ai_coach.video import VideoService
from valorant_ai_coach.video.native import NativeSourceFrame


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''):
            digest.update(block)
    return digest.hexdigest()


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(value, dict):
        raise ValueError('JSON object required')
    return value


def runtime_fingerprint() -> str:
    """Bind executable code, independently of which dataset it processes."""
    return image_runtime_fingerprint()


def load_profile(path: Path) -> tuple[KillfeedSubjectProfile, Any, tuple[int, int, int, int], Path]:
    data = _json(path)
    required = {'schema_version', 'source_sha256', 'owner_marker_review_sha256',
                'frame_shape', 'search_roi', 'name_y_offsets', 'assets_file', 'assets_sha256',
                'separator_method', 'name_gap_inset', 'marker_feature_kind',
                'report_header_search_roi'}
    version = data.get('schema_version')
    expected = required | ({'report_presence_header'}
                           if version == 'self_death_image_profile_v2' else set())
    if (set(data) != expected
            or version not in {'self_death_image_profile_v1', 'self_death_image_profile_v2'}):
        raise ValueError('runtime profile must contain only the versioned reader configuration')
    assets = (path.parent/data['assets_file']).resolve()
    if sha(assets) != data['assets_sha256']:
        raise ValueError('profile asset hash mismatch')
    with np.load(assets, allow_pickle=False) as raw:
        arrays = {key: raw[key] for key in raw.files}
    required_arrays = {'reference', 'mask0', 'mask1', 'mask2', 'gold_mask',
                       'weapon_reference', 'headshot_reference', 'report_header_reference'}
    presence_arrays = {
        'report_presence_reference', 'report_presence_mask', 'report_presence_regions',
    }
    if version == 'self_death_image_profile_v2':
        required_arrays |= presence_arrays
    if (not required_arrays <= arrays.keys()
            or arrays.keys()-required_arrays-{'additional_weapon_reference'}):
        raise ValueError('unexpected runtime profile arrays')
    if version == 'self_death_image_profile_v2':
        _report_presence_model(data, arrays)
    profile = KillfeedSubjectProfile(
        data['source_sha256'], data['owner_marker_review_sha256'], tuple(data['frame_shape']),
        tuple(data['search_roi']), arrays['reference'],
        (arrays['mask0'], arrays['mask1'], arrays['mask2']), arrays['gold_mask'],
        arrays['weapon_reference'], arrays['headshot_reference'], tuple(data['name_y_offsets']),
        (arrays['additional_weapon_reference'],) if 'additional_weapon_reference' in arrays else (),
        data['separator_method'], data['name_gap_inset'], data['marker_feature_kind'],
    )
    return (profile, arrays['report_header_reference'],
            tuple(data['report_header_search_roi']), assets)


def _report_presence_model(data: dict[str, Any], arrays: dict[str, Any]) -> ReportHeader:
    spec = data['report_presence_header']
    if not isinstance(spec, dict) or set(spec) != {'input_shape', 'reference_x', 'threshold'}:
        raise ValueError('explicit Report presence configuration required')
    model = ReportHeader(
        arrays['report_presence_reference'], arrays['report_presence_mask'],
        arrays['report_presence_regions'], tuple(spec['input_shape']),
        spec['reference_x'], spec['threshold'],
    )
    model.validate()
    return model


def load_report_presence(path: Path) -> ReportHeader | None:
    """Optional v2 witness, never a replacement self-subject onset reader."""
    _, _, _, assets = load_profile(path)
    data = _json(path)
    if data['schema_version'] == 'self_death_image_profile_v1':
        return None
    if sha(assets) != data['assets_sha256']:
        raise ValueError('profile asset hash mismatch')
    with np.load(assets, allow_pickle=False) as raw:
        arrays = {key: raw[key] for key in raw.files}
    return _report_presence_model(data, arrays)


def replay_cache(
    manifest_path: Path, recognizer: SelfDeathImageRecognizer, dependencies: str,
) -> list[dict[str, Any]]:
    """Read every cached frame, retaining source/context and reset diagnostics."""
    data = _json(manifest_path)
    if (data.get('cache_kind') != 'lossless_decoded_native_frames_v1_no_recognition'
            or data.get('source_sha256') != recognizer.reader.profile.source_sha256
            or data.get('terminal_source_hash_verified') is not True):
        raise ValueError('verified source-bound decoded-input cache required')
    windows = []
    for group in data['windows']:
        # A bounded window is its own observation context, never an assumed
        # native Round or a continuation across a missing source interval.
        detector = SelfDeathImageRecognizer(
            recognizer.reader.profile, recognizer.reader.reader, recognizer.report_reference,
            recognizer.report_search_roi, runtime_fingerprint=runtime_fingerprint(),
            dependencies_fingerprint=dependencies, native_step_ticks=recognizer.native_step_ticks,
            report_presence_header=recognizer.report_presence_header,
        )
        if detector.code_fingerprint != recognizer.code_fingerprint:
            raise ValueError('recognizer code changed between native windows')
        rows = []
        for record in group['rows']:
            for field, minimum in (('pts_ticks', 0), ('time_base_num', 1),
                                   ('time_base_den', 1), ('width', 1), ('height', 1)):
                if type(record[field]) is not int or record[field] < minimum:
                    raise ValueError('invalid native cache coordinate: '+field)
            path = Path(record['path'])
            if not path.is_absolute():
                path = manifest_path.parent/path
            frame = NativeSourceFrame(
                path, record['pts_ticks'],
                Fraction(record['time_base_num'], record['time_base_den']),
                record['source_epoch'], data['source_sha256'], record['encoded_sha256'],
                record['pixel_sha256'], record['width'], record['height'],
            )
            image = frame.read_image()
            source = SourceBinding(
                frame.source_video_sha256, frame.pts_ticks, frame.time_base.numerator,
                frame.time_base.denominator, frame.source_epoch, frame.pixel_sha256,
                detector.code_fingerprint, detector.profile_fingerprint, dependencies,
            )
            reading = detector.observe(image, source)
            if reading.qualified or reading.formal_events:
                raise RuntimeError('diagnostic reader unexpectedly released an event')
            rows.append(asdict(reading))
        if len(rows) < 2:
            raise ValueError('native replay requires at least two source frames per window')
        windows.append({'window': group['window'], 'frames': len(rows), 'rows': rows,
                        'prediction_count': sum(row['status'] == 'prediction' for row in rows),
                        'source_blocked_frames': sum(
                            row['reason'] == 'source_invalid_or_discontinuous' for row in rows),
                        'qualified': False, 'formal_events': []})
    if sum(window['frames'] for window in windows) != data['frames']:
        raise ValueError('cache frame count mismatch')
    return windows


def _peak_rss_bytes() -> int | None:
    try:
        import resource
    except ImportError:
        return None
    rss = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    return rss if platform.system() == 'Darwin' else rss*1024


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('source', 'profile', 'owner-review', 'tesseract', 'engine-binary',
                 'tessdata', 'output'):
        parser.add_argument('--'+name, type=Path, required=True)
    parser.add_argument('--cache-manifest', type=Path, action='append', required=True)
    parser.add_argument('--dependency-root', type=Path, action='append', default=[])
    parser.add_argument('--native-step-ticks', type=int, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('preserve old results: output must not exist')
    started = time.monotonic()
    profile, report, search, assets = load_profile(args.profile)
    presence_header = load_report_presence(args.profile)
    if sha(args.source) != profile.source_sha256:
        raise ValueError('source video hash mismatch')
    if sha(args.owner_review) != profile.owner_marker_review_sha256:
        raise ValueError('owner semantics review hash mismatch')
    metadata = VideoService().probe(args.source)
    if (metadata.height, metadata.width) != profile.frame_shape:
        raise ValueError('profile/source geometry mismatch')
    inputs = {str(path.resolve()): sha(path) for path in (
        args.profile, assets, args.owner_review, Path(__file__), *args.cache_manifest,
    )}
    for manifest in args.cache_manifest:
        for group in _json(manifest)['windows']:
            for record in group['rows']:
                path = Path(record['path'])
                if not path.is_absolute():
                    path = manifest.parent/path
                inputs[str(path.resolve())] = record['encoded_sha256']
    tool_files = [args.tesseract, args.engine_binary, args.tessdata/'eng.traineddata']
    for name in ('ffprobe', 'ffmpeg'):
        resolved = shutil.which(name)
        if resolved is None:
            raise ValueError(name+' is required for source provenance')
        tool_files.append(Path(resolved))
    for root in args.dependency_root:
        if not root.is_dir():
            raise ValueError('dependency root must exist')
        tool_files.extend(path for path in root.rglob('*') if path.is_file())
    for package in (cv2, np):
        if package.__file__ is not None:
            tool_files.append(Path(package.__file__))
            tool_files.extend(path for path in Path(package.__file__).parent.rglob('*')
                              if path.suffix in {'.so', '.pyd', '.dll'} and path.is_file())
    dependency_files = {str(path.resolve()): sha(path) for path in tool_files}
    dependencies = {
        'files': dependency_files, 'python': platform.python_version(),
        'opencv': cv2.__version__, 'opencv_threads': cv2.getNumThreads(), 'numpy': np.__version__,
        'ocr_language': 'eng', 'ocr_psm': 7,
        'tesseract_version': subprocess.check_output(
            [str(args.tesseract), '--version'], text=True, encoding='utf-8'),
    }
    deps = hashlib.sha256(json.dumps(dependencies, sort_keys=True).encode('utf-8')).hexdigest()
    runtime = runtime_fingerprint()
    reader = TesseractTextReader(language='eng', executable=str(args.tesseract),
                                tessdata_dir=str(args.tessdata), psm=7)
    detector = SelfDeathImageRecognizer(
        profile, reader, report, search, runtime_fingerprint=runtime,
        dependencies_fingerprint=deps, native_step_ticks=args.native_step_ticks,
        report_presence_header=presence_header,
    )
    image_started = time.monotonic()
    windows = []
    for manifest in args.cache_manifest:
        windows.extend(replay_cache(manifest, detector, deps))
    recognition_sec = time.monotonic()-image_started
    terminal_detector = SelfDeathImageRecognizer(
        profile, reader, report, search, runtime_fingerprint=runtime_fingerprint(),
        dependencies_fingerprint=deps, native_step_ticks=args.native_step_ticks,
        report_presence_header=presence_header,
    )
    if (sha(args.source) != profile.source_sha256 or runtime_fingerprint() != runtime
            or terminal_detector.code_fingerprint != detector.code_fingerprint
            or any(sha(Path(path)) != value for path, value in
                   {**inputs, **dependency_files}.items())):
        raise ValueError('source, configuration, code or dependency changed during replay')
    frames = sum(window['frames'] for window in windows)
    result = {
        'scope': 'Non-releasing native image replay; not canonical E2E or qualification.',
        'mode': 'self_death_native_replay', 'source_sha256': profile.source_sha256,
        'input_hashes': inputs, 'dependencies': dependencies, 'runtime_fingerprint': runtime,
        'code_fingerprint': detector.code_fingerprint, 'profile_fingerprint': profile.fingerprint(),
        'dependencies_fingerprint': deps, 'native_step_ticks': args.native_step_ticks,
        'windows': windows, 'processed_frames': frames, 'recognition_sec': recognition_sec,
        'wall_sec': time.monotonic()-started, 'recognition_frames_per_sec': frames/recognition_sec,
        'python_peak_rss_bytes': _peak_rss_bytes(),
        'terminal_hashes_passed': True, 'qualified': False, 'formal_events': [],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2, allow_nan=False)
    print(json.dumps({key: result[key] for key in (
        'mode', 'processed_frames', 'recognition_sec', 'wall_sec', 'python_peak_rss_bytes',
    )}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

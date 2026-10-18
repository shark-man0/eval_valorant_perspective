"""Replay original field observations through the episode join, without OCR/GT.

Outputs contain private observed text; keep them in the private outputs tree.
This verifies archived cache/artifact hashes, not a fresh full-video decode or
independent qualification. Original recognizer fingerprints are never replaced.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

import cv2

import valorant_ai_coach.experimental.death_episode_fields as transport_module
from valorant_ai_coach.experimental.death_episode_fields import (
    DeathEpisodeFieldCollector,
    ReportCandidateFrame,
)
from valorant_ai_coach.experimental.killfeed_subject import (
    KillfeedSubjectReading,
    WeaponGlyphGeometry,
)
from valorant_ai_coach.experimental.self_death_image import SelfDeathImageReading
from valorant_ai_coach.experimental.subject_death import SourceBinding
from valorant_ai_coach.observability.profiling import _peak_rss_bytes


def digest(path: Path) -> str:
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def load_reading(row: dict[str, Any]) -> SelfDeathImageReading:
    data = dict(row)
    data['source'] = SourceBinding(**data['source'])
    data['evidence_sources'] = tuple(SourceBinding(**s) for s in data['evidence_sources'])
    if data.get('report_match_roi') is not None:
        data['report_match_roi'] = tuple(data['report_match_roi'])
    subjects = []
    for original in data['subjects']:
        item = dict(original)
        item['source'] = SourceBinding(**item['source'])
        for key in ('marker_roi', 'weapon_roi', 'ability_roi', 'name_roi', 'marker_support'):
            if item.get(key) is not None:
                item[key] = tuple(item[key])
        if item.get('weapon_geometry') is not None:
            geometry = dict(item['weapon_geometry'])
            geometry['roi'] = tuple(geometry['roi'])
            item['weapon_geometry'] = WeaponGlyphGeometry(**geometry)
        subjects.append(KillfeedSubjectReading(**item))
    data['subjects'] = tuple(subjects)
    return SelfDeathImageReading(**data)


def physical(source: SourceBinding) -> tuple[Any, ...]:
    return (source.video_sha256, source.segment_id, source.pts_ticks,
            source.time_base_num, source.time_base_den, source.pixel_sha256)


def replay(image_path: Path, report_path: Path, manifest_path: Path,
           image_plan_path: Path) -> dict[str, Any]:
    started = time.monotonic()
    assert transport_module.__file__ is not None
    transport_path = Path(transport_module.__file__)
    paths = (image_path, report_path, manifest_path, image_plan_path,
             Path(__file__), transport_path)
    inputs = {str(p): digest(p) for p in paths}
    image, report, manifest, plan = [json.loads(p.read_text(encoding='utf-8')) for p in paths[:4]]
    if (image['terminal_hashes_passed'] is not True
            or manifest['terminal_source_hash_verified'] is not True
            or image['source_sha256'] != manifest['source_sha256']):
        raise ValueError('original verified image replay and source cache required')
    for mapping in (image['input_hashes'], report['input_sha256'], plan['code_sha256']):
        for path, expected in mapping.items():
            if path in inputs and inputs[path] != expected:
                raise ValueError('conflicting original input digests')
            inputs[path] = expected
    for path, expected in inputs.items():
        if digest(Path(path)) != expected:
            raise ValueError(f'original input changed: {path}')
    cache = {}
    for group in manifest['windows']:
        for frame in group['rows']:
            key = (manifest['source_sha256'], frame['source_epoch'], frame['pts_ticks'],
                   frame['time_base_num'], frame['time_base_den'], frame['pixel_sha256'])
            cache[key] = frame
    reports: dict[tuple[Any, ...], ReportCandidateFrame] = {}
    for row in report['rows']:
        source = SourceBinding(**row['source'])
        # Other source videos in a shared field probe are never joined here.
        if source.video_sha256 != image['source_sha256'] or not row['candidate_fields']:
            continue
        candidate = ReportCandidateFrame.from_fields(source, tuple(report['fields_roi']),
                                                       row['candidate_fields'])
        key = physical(source)
        if key in reports and reports[key] != candidate:
            raise ValueError('conflicting original Report records')
        reports[key] = candidate
    summaries = []
    association_sec = 0.0
    checked_pixels: set[tuple[str, str]] = set()
    for index, window in enumerate(image['windows']):
        collector = DeathEpisodeFieldCollector(image['native_step_ticks'])
        episodes = []
        for raw in window['rows']:
            row = load_reading(raw)
            source = row.source
            if (source.code_fingerprint != image['code_fingerprint']
                    or source.profile_fingerprint != image['profile_fingerprint']
                    or source.dependencies_fingerprint != image['dependencies_fingerprint']):
                raise ValueError('row producer differs from original replay')
            frame = cache[physical(source)]
            pixel_key = (frame['path'], frame['pixel_sha256'])
            if pixel_key not in checked_pixels:
                path = Path(frame['path'])
                if digest(path) != frame['encoded_sha256']:
                    raise ValueError('encoded native frame changed')
                pixels = cv2.imread(str(path))
                if (pixels is None
                        or hashlib.sha256(pixels.tobytes()).hexdigest() != source.pixel_sha256):
                    raise ValueError('decoded cache pixels differ from original source')
                checked_pixels.add(pixel_key)
            association_started = time.monotonic()
            result = collector.observe(row, reports.get(physical(source)))
            association_sec += time.monotonic()-association_started
            if result is not None:
                episodes.append(asdict(result))
        summaries.append({'window_index': index, 'frames': len(window['rows']),
                          'episodes': episodes, 'blocker': collector.last_blocker})
    for path, expected in inputs.items():
        if digest(Path(path)) != expected:
            raise ValueError(f'terminal input changed: {path}')
    return {'schema_version': 'death_episode_field_replay_v1',
            'scope': 'exposed archived observation transport; no independent qualification',
            'original_input_hashes': inputs, 'transport_code_sha256': inputs[str(transport_path)],
            'original_image_code_fingerprint': image['code_fingerprint'],
            'original_report_code_fingerprint': report['recognizer_fingerprint'],
            'windows': summaries, 'verified_cache_frames': len(checked_pixels),
            'wall_sec': time.monotonic()-started, 'association_sec': association_sec,
            'python_peak_rss_bytes': _peak_rss_bytes(), 'terminal_hashes_passed': True,
            'qualified': False, 'formal_events': 0, 'canonical_evaluated': False}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('image-replay', 'report-replay', 'cache-manifest', 'image-plan', 'output'):
        parser.add_argument('--'+name, required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('preserve previous results; use a new output path')
    result = replay(args.image_replay, args.report_replay, args.cache_manifest, args.image_plan)
    with args.output.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, indent=2, ensure_ascii=False, allow_nan=False)
    print(json.dumps({'frames': result['verified_cache_frames'], 'wall_sec': result['wall_sec'],
                      'formal_events': 0, 'canonical_evaluated': False}))


if __name__ == '__main__':
    main()

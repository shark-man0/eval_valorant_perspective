"""Whole-source Practical collector and native global Package diagnostics.

Uses the common production entrance once, with no GT or sampler substitutions.
This intentionally does not run visual/player analysis or canonical assertions.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from scripts.e2e.practical_export import export_package_boundaries
from valorant_ai_coach.application.hud_video_processor import (
    HudVideoProcessor,
    NativeLifecycleOptions,
)
from valorant_ai_coach.diagnostics.runtime_timing import RuntimeTimingCollector, timing_stage
from valorant_ai_coach.events import EventSourceContract
from valorant_ai_coach.hud.analyzers import RealHudAnalyzer
from valorant_ai_coach.hud.practical_lifecycle import PracticalLifecycleAnalysis
from valorant_ai_coach.resources import resource_path
from valorant_ai_coach.rounds import RoundPackageBuilder
from valorant_ai_coach.schema_validation import SchemaValidator
from valorant_ai_coach.video import VideoService
from valorant_ai_coach.visual.analyzer import NullVisualAnalyzer


def write_json(path: Path, value: object) -> None:
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write('\n')


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--video', type=Path, required=True)
    parser.add_argument('--layout', type=Path, required=True)
    parser.add_argument('--templates', type=Path, required=True)
    parser.add_argument('--input-contract', type=Path, required=True)
    parser.add_argument('--output-directory', type=Path, required=True)
    parser.add_argument('--match-id', required=True)
    args = parser.parse_args()
    args.output_directory.mkdir(parents=True, exist_ok=False)
    collector = RuntimeTimingCollector()
    with collector:
        service = VideoService()
        with timing_stage('metadata_open'):
            metadata = service.probe(args.video)
        analyzer = RealHudAnalyzer(args.layout, template_profile_path=args.templates)
        contract = EventSourceContract.load(resource_path('config/event_source_contract_v1.json'))
        validator = SchemaValidator()
        builder = RoundPackageBuilder(contract=contract, validator=validator)
        processor = HudVideoProcessor(video=service, analyzer=analyzer,
                                      visual_analyzer=NullVisualAnalyzer(contract),
                                      package_builder=builder, validator=validator)
        analysis = processor.collect_native_lifecycle(
            metadata, NativeLifecycleOptions(
                max_png_bytes=8 * 1024**3, storage_mode='replay',
                unedited_input_contract_path=args.input_contract,
            ), boundary_mode='practical',
        )
        if not isinstance(analysis, PracticalLifecycleAnalysis):
            raise TypeError('Practical production result required')
        # Persist verified source observations first, even if Package diagnostics
        # subsequently expose a downstream defect. Never publish partial readers.
        write_json(args.output_directory / 'native_analysis.json', {
            'scope': __doc__, 'source_video_sha256': analysis.input_contract.source_video_sha256,
            'input_contract_sha256': analysis.input_contract.fingerprint,
            'profile_fingerprint': analysis.profile_fingerprint,
            'recognizer_fingerprint': analysis.recognizer_fingerprint,
            'native_step_ticks': analysis.native_step_ticks,
            'source_rows': analysis.source_rows,
            'boundaries': [boundary.to_dict() for boundary in analysis.boundaries],
            'diagnostics': analysis.diagnostics,
            'qualification_file_sha256': analysis.qualification_file_sha256,
        })
        boundaries, cuts = processor._practical_boundaries(metadata, 'practical', analysis)
        native = processor._confirmed_overlay(None, analysis)
        events = processor._native_boundaries(metadata, native) if native else ()
        observations = [row['system_observation'] for row in analysis.source_rows]
        with timing_stage('round_package_build'):
            packages = builder.build(
                match_id=args.match_id, video_metadata=metadata,
                hud_observations=observations, hud_events=events,
                boundary_mode='practical', provisional_boundaries=boundaries,
                continuity_breaks=cuts, require_detected_rounds=False,
            )
        write_json(args.output_directory / 'global_packages.json', {'round_packages': packages})
        exported = export_package_boundaries(list(packages))
        write_json(args.output_directory / 'boundary_export.json', exported)
        summary = {
            'scope': 'Whole native global collection/Packages; not canonical or player analysis',
            'processed_frames': len(observations),
            'source_range_sec': [observations[0]['time_sec'], observations[-1]['time_sec']],
            'primary_states': dict(Counter(row['primary_state'] for row in observations)),
            'provisional_boundaries': [boundary.to_dict() for boundary in boundaries],
            'formal_boundary_count': len(events), 'source_break_count': len(cuts),
            'package_count': len(packages), 'partitions': exported['partitions'],
            'canonical_e2e_reexecuted': False, 'precision_verified': False,
            'qualification_created': False,
        }
    summary['runtime'] = collector.snapshot()
    write_json(args.output_directory / 'summary.json', summary)
    print(json.dumps({key: summary[key] for key in
                      ('processed_frames', 'formal_boundary_count', 'package_count')},
                     ensure_ascii=False))


if __name__ == '__main__':
    main()

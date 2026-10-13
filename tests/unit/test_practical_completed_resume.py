"""Completed uncertain jobs restore durable inputs without rerunning recognition."""
from copy import deepcopy
from dataclasses import replace

import pytest

from tests.integration.test_hud_pipeline_wiring import setup_pipeline
from tests.unit.test_round_package_builder import practical_build as practical_build
from tests.unit.test_round_package_builder import practical_candidate
from tests.unit.test_unedited_ui_start import make_contract
from valorant_ai_coach.application.hud_video_processor import (
    HudVideoProcessingResult,
    NativeLifecycleOptions,
)


def prepare(tmp_path, monkeypatch, practical_build):
    services, source, processor = setup_pipeline(tmp_path, monkeypatch)
    pipeline = services.pipeline
    contract_path, _ = make_contract(tmp_path, pipeline._full_source_sha256(source))
    pipeline.round_boundary_mode = 'practical'
    pipeline.native_lifecycle_options = NativeLifecycleOptions(
        1024, unedited_input_contract_path=contract_path,
    )
    packages = practical_build(boundary_mode='practical', provisional_boundaries=[
        practical_candidate('round_start', 2, 2.5),
        practical_candidate('round_end', 5, 5.8),
        practical_candidate('round_start', 6, 6.4),
    ])
    calls = []

    def process(**kwargs):
        calls.append('recognition')
        supplied = deepcopy(packages)
        for package in supplied:
            package['match_id'] = kwargs['match_id']
            package['source_video']['path'] = str(source)
        return HudVideoProcessingResult(tuple(supplied), (), (), (), (), 0)

    monkeypatch.setattr(processor, 'process', process)
    initial = pipeline.analyze_video(source, match_id='resume-practical')
    assert initial.errors == ()
    assert not any(r.output['evaluations'] for r in initial.rounds)
    return services, source, calls


def test_completed_practical_resume_avoids_recognition_and_preserves_packages(
    tmp_path, monkeypatch, practical_build,
):
    services, source, calls = prepare(tmp_path, monkeypatch, practical_build)
    stored = services.repository.list_round_packages('resume-practical')
    original_report = (services.pipeline.data_dir / 'matches/resume-practical/hud-analysis.json')
    report_bytes = original_report.read_bytes()
    result = services.pipeline.resume_analysis('resume-practical', video_path=source)
    assert result.errors == ()
    assert calls == ['recognition']
    assert all(r.output['analysis_id'].startswith('RESTORED-') for r in result.rounds)
    assert not any(r.output['evaluations'] for r in result.rounds)
    assert services.repository.list_round_packages('resume-practical') == stored
    assert original_report.read_bytes() == report_bytes


@pytest.mark.parametrize('change', ['missing', 'package', 'incomplete', 'strict'])
def test_completed_package_admission_rejects_changed_or_incomplete_inputs(
    tmp_path, monkeypatch, practical_build, change,
):
    services, source, _ = prepare(tmp_path, monkeypatch, practical_build)
    pipeline = services.pipeline
    checkpoint = services.repository.get_job_checkpoint('resume-practical')['checkpoint']
    completed = checkpoint['completed_rounds']
    expected = checkpoint['saved_round_package_fingerprints']
    packages = services.repository.list_round_packages('resume-practical')
    if change == 'missing':
        monkeypatch.setattr(services.repository, 'list_round_packages', lambda _: packages[1:])
    elif change == 'package':
        packages[0]['source_video']['width'] += 1
        monkeypatch.setattr(services.repository, 'list_round_packages', lambda _: packages)
    elif change == 'incomplete':
        completed = completed[:-1]
    else:
        pipeline.round_boundary_mode = 'strict'
    assert pipeline._completed_practical_packages('resume-practical', source,
                                                  completed, expected) is None


def test_source_contract_detects_middle_change_even_when_bounded_fingerprint_matches(
    tmp_path, monkeypatch, practical_build,
):
    # Equal size and restored mtime deliberately reproduce the bounded resume
    # fingerprint's blind spot. Full SHA remains mandatory for source assurance.
    import os

    services, source, _ = prepare(tmp_path, monkeypatch, practical_build)
    source.write_bytes(b'a' * (3 * 1024 * 1024))
    pipeline = services.pipeline
    contract_path, _ = make_contract(tmp_path, pipeline._full_source_sha256(source))
    pipeline.native_lifecycle_options = replace(pipeline.native_lifecycle_options,
                                                unedited_input_contract_path=contract_path)
    before = pipeline._source_fingerprint(source)
    stat = source.stat()
    with source.open('r+b') as stream:
        stream.seek(1024 * 1024 + 10)
        stream.write(b'b')
    os.utime(source, ns=(stat.st_atime_ns, stat.st_mtime_ns))
    assert pipeline._source_fingerprint(source) == before
    checkpoint = services.repository.get_job_checkpoint('resume-practical')['checkpoint']
    with pytest.raises(ValueError, match='matching'):
        pipeline._completed_practical_packages('resume-practical', source,
                                               checkpoint['completed_rounds'],
                                               checkpoint['saved_round_package_fingerprints'])


def test_legacy_practical_checkpoint_retains_fresh_processing_fallback(
    tmp_path, monkeypatch, practical_build,
):
    services, source, calls = prepare(tmp_path, monkeypatch, practical_build)
    row = services.repository.get_job_checkpoint('resume-practical')
    checkpoint = row['checkpoint']
    checkpoint.pop('saved_round_package_fingerprints')
    services.repository.save_job_checkpoint('resume-practical', 'completed', checkpoint)
    result = services.pipeline.resume_analysis('resume-practical', video_path=source)
    assert result.errors == ()
    assert calls == ['recognition', 'recognition']


def test_source_change_during_cached_restore_fails_terminal_verification(
    tmp_path, monkeypatch, practical_build,
):
    services, source, calls = prepare(tmp_path, monkeypatch, practical_build)

    def change_source(_fraction, message):
        if message == '保存済み暫定区間を検証しました（採点保留）':
            source.write_bytes(b'changed after full source attestation')

    with pytest.raises(RuntimeError, match='復元中'):
        services.pipeline.resume_analysis('resume-practical', video_path=source,
                                          progress_cb=change_source)
    assert calls == ['recognition']
    assert services.repository.get_match('resume-practical')['status'] == 'failed'


def test_package_change_during_cached_restore_fails_terminal_verification(
    tmp_path, monkeypatch, practical_build,
):
    services, source, calls = prepare(tmp_path, monkeypatch, practical_build)

    def change_package(_fraction, message):
        if message == '保存済み暫定区間を検証しました（採点保留）':
            package = services.repository.list_round_packages('resume-practical')[0]
            package['source_video']['width'] += 1
            services.repository.save_round_package(package)

    with pytest.raises(RuntimeError, match='復元中'):
        services.pipeline.resume_analysis('resume-practical', video_path=source,
                                          progress_cb=change_package)
    assert calls == ['recognition']

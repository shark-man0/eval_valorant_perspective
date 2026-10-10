"""Practical settings, persistence identity and observed-value UI transport."""
from dataclasses import replace

import pytest

from valorant_ai_coach.bootstrap import build_services
from valorant_ai_coach.settings import AppSettings, SettingsStore
from valorant_ai_coach.ui.backend import BackendFacade


def test_practical_opt_in_persists_and_reaches_composition_root(tmp_path):
    path = tmp_path / 'contract.json'
    path.write_text('{"assurance_provenance":"synthetic input identity"}')
    selected = AppSettings(data_dir=tmp_path, hud_mode='real',
                           round_boundary_mode='practical',
                           unedited_input_contract_path=str(path), native_png_budget_mb=128)
    store = SettingsStore(tmp_path / 'settings.json')
    store.save(selected)
    assert store.load() == selected
    services = build_services(store)
    pipeline = services.pipeline
    assert pipeline.round_boundary_mode == 'practical'
    assert pipeline.native_lifecycle_options.unedited_input_contract_path == path
    assert pipeline.native_lifecycle_options.max_png_bytes == 128 * 1024 * 1024
    before = pipeline._config_fingerprint()
    match = {'source_video_path': str(tmp_path / 'source.mp4')}
    checkpoint = {'source_fingerprint': 'unchanged-source', 'config_fingerprint': before}
    pipeline._validate_resume_fingerprints(match, checkpoint, tmp_path / 'source.mp4',
                                           'unchanged-source', before)
    path.write_text('{"assurance_provenance":"different synthetic input identity"}')
    assert pipeline._config_fingerprint() != before
    with pytest.raises(RuntimeError, match='解析設定'):
        pipeline._validate_resume_fingerprints(
            match, checkpoint, tmp_path / 'source.mp4', 'unchanged-source',
            pipeline._config_fingerprint(),
        )
    strict = build_services(store, settings=replace(selected, round_boundary_mode='strict'))
    assert strict.pipeline.native_lifecycle_options is None
    assert strict.pipeline._config_fingerprint() != before
    with pytest.raises(RuntimeError, match='解析設定'):
        strict.pipeline._validate_resume_fingerprints(
            match, checkpoint, tmp_path / 'source.mp4', 'unchanged-source',
            strict.pipeline._config_fingerprint(),
        )


@pytest.mark.parametrize('changes', [
    {'round_boundary_mode': 'auto'},
    {'round_boundary_mode': 'practical'},
    {'round_boundary_mode': 'practical', 'unedited_input_contract_path': 'input.json'},
    {'native_png_budget_mb': True}, {'native_png_budget_mb': 0},
])
def test_practical_requires_explicit_valid_contract_and_real_input(changes):
    with pytest.raises(ValueError):
        AppSettings(**changes)


def test_ui_partition_view_keeps_unknown_and_preserves_only_observed_values():
    package = {
        'round_no': 2, 'round_window': {'start_sec': 3., 'end_sec': 8.},
        'events': [],
        'round_lifecycle': {'start': {'status': 'provisional'}, 'end': {'status': 'unknown'}},
        'state_snapshots': [{'time_sec': 4., 'round_time_remaining_display': '1:39',
                             'hp': None, 'score_ally': 0, 'score_enemy': 1}],
    }
    view = BackendFacade._round_partition_view(package)
    assert view.start_status == 'provisional' and view.end_status == 'unknown'
    assert view.observations[0].hp is None
    assert view.observations[0].timer_display == '1:39'
    assert view.observations[0].score_ally == 0
    package.pop('round_lifecycle')
    legacy = BackendFacade._round_partition_view(package)
    assert legacy.start_status == legacy.end_status == 'unknown'


def test_practical_native_collection_uses_shared_decoder_and_terminal_verification(
    tmp_path, monkeypatch,
):
    import hashlib
    from contextlib import contextmanager
    from dataclasses import replace
    from fractions import Fraction
    from types import SimpleNamespace

    from tests.unit.test_native_event_merge import qualified_processor
    from tests.unit.test_unedited_ui_end import fixture
    from tests.unit.test_unedited_ui_start import make_contract
    from valorant_ai_coach.application.hud_video_processor import NativeLifecycleOptions
    from valorant_ai_coach.video.native import NativeSourceFrame

    prefix = tmp_path / 'reader'
    prefix.mkdir()
    rows, _ = fixture(prefix, next_round=True)
    processor, metadata, _, _ = qualified_processor(tmp_path)
    metadata = replace(metadata, duration_sec=2.0)
    source_hash = hashlib.sha256(metadata.path.read_bytes()).hexdigest()
    contract_path, _ = make_contract(prefix, source_hash)
    frames = tuple(NativeSourceFrame(
        tmp_path / f'{index}.png', row['source_pts_ticks'], Fraction(row['source_time_base']),
        row['source_epoch'], source_hash, 'a' * 64, row['source_pixel_sha256'],
        metadata.width, metadata.height,
    ) for index, row in enumerate(rows))
    monkeypatch.setattr(NativeSourceFrame, 'read_image', lambda self: None)
    calls = []

    @contextmanager
    def decode(_path, **kwargs):
        calls.append(kwargs)
        yield frames
        calls.append('terminal')

    def observe(source, _metadata, *, _build_events):
        assert tuple(source) == frames and _build_events is False
        scans = []
        for row in rows:
            phase = row['system_observation']['values']['buy_phase_visible']
            scans.append({'phase_scan_valid': True, 'phase_present': phase,
                          'phase_confidence': .95 if phase else 0,
                          'round_result_matched': row['system_evidence'].get(
                              'assured_round_result_present', False),
                          'round_result_confidence': row['system_evidence'].get(
                              'assured_round_result_confidence', 0)})
        return SimpleNamespace(observations=[r['system_observation'] for r in rows],
                               native_ui_measurements=scans)

    processor.video.native_window = decode
    processor.analyzer = SimpleNamespace(
        _native_profile_readers=True, _native_loaded_base_fingerprint='a' * 64,
        _base_fingerprint=lambda: 'a' * 64, fingerprint=lambda: 'a' * 64,
        observe_frames=observe,
    )
    analysis = processor.collect_native_lifecycle(
        metadata, NativeLifecycleOptions(1234, unedited_input_contract_path=contract_path),
        boundary_mode='practical',
    )
    assert [b.kind for b in analysis.boundaries] == ['round_start', 'round_end', 'round_start']
    assert all(b.boundary_status == 'provisional' for b in analysis.boundaries)
    assert calls[0]['start_sec'] == 0 and calls[0]['end_sec'] is None
    assert calls[0]['source_video_sha256'] == source_hash and calls[-1] == 'terminal'

import json
from types import SimpleNamespace

import cv2
import numpy as np
import pytest

from scripts.diagnostics import prepare_banner_held_review as subject
from scripts.diagnostics.prepare_banner_held_review import indices
from scripts.e2e.run_dataset_case import sha256_file


def test_selection_is_fixed_uniform_original_order_not_prediction_rank():
    assert indices(40, 6) == [0, 7, 15, 23, 31, 39]
    assert indices(6, 6) == list(range(6))


@pytest.mark.parametrize('length,count', [(2, 2), (257, 6), (6, 7), (6, True), (True, 3)])
def test_selection_rejects_insufficient_or_unbounded_inventory(length, count):
    with pytest.raises(ValueError):
        indices(length, count)


@pytest.fixture
def inputs(tmp_path, monkeypatch):
    pool = tmp_path / 'pool_frames'
    pool.mkdir()
    rows, bindings = [], {}
    for i in range(6):
        path = pool / f'frame_{i}.jpg'
        assert cv2.imwrite(str(path), np.full((24, 24, 3), 60 + i, np.uint8))
        digest = sha256_file(path)
        bindings[str(path)] = digest
        rows.append({'sha256': digest, 'source_video_sha256': 'a' * 64,
                     'source_pts_ticks': (i + 1) * 60, 'source_time_base': '1/60',
                     'source_frame_pts': i + 1})
    selection, layout = tmp_path / 'selection.json', tmp_path / 'layout.json'
    selection.write_text(json.dumps({'pool_records': rows}), encoding='utf-8')
    layout.write_text('{}', encoding='utf-8')
    bindings.update({str(selection): sha256_file(selection), str(layout): sha256_file(layout)})
    report = tmp_path / 'report.json'
    report.write_text(json.dumps({
        'kind': 'unlabeled_banner_discovery_not_qualification',
        'training_candidate_audit': True, 'held_predictions_measured': False,
        'semantic_labels_assigned': False, 'production_adopted': False,
        'source_sha256': 'a' * 64, 'training_hashes': ['b' * 64, 'c' * 64, 'd' * 64],
        'held_hashes': [row['sha256'] for row in rows], 'source_inputs_sha256': bindings,
    }), encoding='utf-8')
    partition = tmp_path / 'partition.json'
    partition.write_text(json.dumps({
        'kind': 'development_holdout_partition_not_gt', 'source_video_sha256': 'a' * 64,
        'development': {'start_sec_inclusive': 0, 'end_sec_exclusive': 720},
        'holdout': {'start_sec_inclusive': 720, 'end_sec_exclusive': 2200},
    }), encoding='utf-8')
    monkeypatch.setattr(subject, '_check_output_privacy', lambda _: None)
    roi = SimpleNamespace(pixel_bounds=lambda *_: (0, 0, 24, 12))
    monkeypatch.setattr(subject, 'HudLayout', SimpleNamespace(load=lambda _: SimpleNamespace(
        reference_resolution=(24, 24), normalized_roi=lambda _: roi)))
    return report, selection, layout, partition, tmp_path / 'review'


def test_blind_review_preserves_sources_and_has_no_model_predictions(inputs):
    before = {path: path.read_bytes() for path in inputs[:4]}
    result = subject.prepare(*inputs)
    assert len(result['frames']) == 6
    assert all(row['label'] is None for row in result['frames'])
    assert result['model_outputs_exposed'] is False
    assert result['qualification_created'] is False
    assert result['production_adopted'] is False
    assert all(path.read_bytes() == data for path, data in before.items())
    page = (inputs[-1] / 'index.html').read_text(encoding='utf-8')
    assert 'held_accept' not in page and 'confidence' not in page
    with pytest.raises(FileExistsError):
        subject.prepare(*inputs)


@pytest.mark.parametrize('change', ['overlap', 'holdout', 'asset', 'predictions'])
def test_invalid_review_inputs_fail_without_assigning_labels(inputs, change):
    report_path, selection_path, *_ = inputs
    report = json.loads(report_path.read_text(encoding='utf-8'))
    if change == 'overlap':
        report['training_hashes'][0] = report['held_hashes'][0]
    elif change == 'predictions':
        report['held_predictions_measured'] = True
    elif change == 'asset':
        asset = report_path.parent / 'pool_frames' / 'frame_0.jpg'
        path = str(asset)
        assert asset.is_file() and path in report['source_inputs_sha256']
        report['source_inputs_sha256'][path] = 'e' * 64
    else:
        selection = json.loads(selection_path.read_text(encoding='utf-8'))
        selection['pool_records'][0].update(source_pts_ticks=720 * 60, source_frame_pts=720)
        selection_path.write_text(json.dumps(selection), encoding='utf-8')
        report['source_inputs_sha256'][str(selection_path)] = sha256_file(selection_path)
    report_path.write_text(json.dumps(report), encoding='utf-8')
    with pytest.raises(ValueError):
        subject.prepare(*inputs)
    assert not inputs[-1].exists()

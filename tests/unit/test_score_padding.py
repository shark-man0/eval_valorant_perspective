import hashlib
import json
from types import SimpleNamespace

import cv2
import numpy as np
import pytest

from scripts.diagnostics import measure_score_padding as subject


def test_padding_is_fixed_blank_does_not_mutate_crop_or_choose_winner(monkeypatch):
    monkeypatch.setattr(subject, 'propose', lambda *_args, **_kwargs: (2, 2, 8, 8))
    roi = np.full((10, 10), 230, dtype=np.uint8)
    original = roi.copy()
    images = []

    class Reader:
        def read(self, image, _roi):
            images.append(image.copy())
            return SimpleNamespace(value='1', confidence=.95 if len(images) == 1 else .89)

    result = subject.measure_crop(roi, Reader())
    assert result['baseline']['accepted'] is True
    assert result['padded']['accepted'] is False
    assert images[0].shape == (6, 6)
    assert images[1].shape == (12, 12)
    assert np.all(images[1][:3] == 0)
    assert np.array_equal(images[1][3:9, 3:9], images[0])
    assert np.array_equal(roi, original)


@pytest.mark.parametrize('value,confidence', [('1', .89), ('123', .99),
                                             ('1:02', .99), ('1', float('nan'))])
def test_padding_never_overrides_floor_or_integer_format(monkeypatch, value, confidence):
    monkeypatch.setattr(subject, 'propose', lambda *_args, **_kwargs: (0, 0, 6, 6))
    reader = SimpleNamespace(read=lambda *_: SimpleNamespace(value=value, confidence=confidence))
    result = subject.measure_crop(np.zeros((6, 6), np.uint8), reader)
    assert result['baseline']['accepted'] is False
    assert result['padded']['accepted'] is False


def test_missing_localization_never_calls_ocr(monkeypatch):
    monkeypatch.setattr(subject, 'propose', lambda *_args, **_kwargs: None)
    reader = SimpleNamespace(read=lambda *_: pytest.fail('no invented crop'))
    assert subject.measure_crop(np.zeros((6, 6), np.uint8), reader) == {
        'localized': False, 'baseline': None, 'padded': None,
    }


@pytest.fixture
def inventory(tmp_path, monkeypatch):
    assets = {}
    for field in subject.FIELDS:
        path = tmp_path / f'frame_01_{field}.png'
        assert cv2.imwrite(str(path), np.zeros((24, 24), np.uint8))
        assets[field] = hashlib.sha256(path.read_bytes()).hexdigest()
    review = {'kind': 'blind_global_numeric_review_not_lifecycle_gt',
              'production_input': False, 'model_outputs_exposed': False,
              'source_video_sha256': 'a' * 64, 'frames': [{
                  'frame_number': 1, 'source_frame_pts': 10, 'labels': None,
                  'roi_assets_sha256': assets}]}
    partition = {'kind': 'development_holdout_partition_not_gt',
                 'source_video_sha256': 'a' * 64,
                 'development': {'start_sec_inclusive': 0, 'end_sec_exclusive': 720}}
    review_path, partition_path = tmp_path / 'review.json', tmp_path / 'partition.json'
    review_path.write_text(json.dumps(review), encoding='utf-8')
    partition_path.write_text(json.dumps(partition), encoding='utf-8')
    monkeypatch.setattr(subject, '_check_output_privacy', lambda _: None)
    return review_path, partition_path, tmp_path / 'result.json'


@pytest.mark.parametrize('change', ['holdout', 'label', 'duplicate', 'hash', 'source'])
def test_invalid_inventory_rejects_before_ocr(inventory, monkeypatch, change):
    review_path, partition_path, output = inventory
    review = json.loads(review_path.read_text(encoding='utf-8'))
    if change == 'holdout':
        review['frames'][0]['source_frame_pts'] = 720
    elif change == 'label':
        review['frames'][0]['labels'] = {'ally_score': 1}
    elif change == 'duplicate':
        review['frames'].append(review['frames'][0].copy())
    elif change == 'hash':
        review['frames'][0]['roi_assets_sha256']['ally_score'] = 'b' * 64
    else:
        review['source_video_sha256'] = 'b' * 64
    review_path.write_text(json.dumps(review), encoding='utf-8')
    monkeypatch.setattr(subject, 'TesseractDigitsReader', lambda: pytest.fail('no OCR'))
    with pytest.raises(ValueError):
        subject.measure(review_path, partition_path, output)
    assert not output.exists()


def test_measurement_keeps_local_raw_results_but_summary_is_bounded(inventory, monkeypatch):
    review_path, partition_path, output = inventory
    before = review_path.read_bytes()
    monkeypatch.setattr(subject, 'TesseractDigitsReader', lambda: SimpleNamespace(
        executable=subject.__file__, read=lambda *_: SimpleNamespace(value='1', confidence=.95)))
    monkeypatch.setattr(subject, 'propose', lambda *_args, **_kwargs: (2, 2, 8, 8))
    summary = subject.measure(review_path, partition_path, output)
    local = json.loads(output.read_text(encoding='utf-8'))
    assert local['rows'][0]['baseline']['raw_value'] == '1'
    assert 'raw_value' not in json.dumps(summary)
    assert 'inputs_sha256' not in summary
    assert summary['events_released'] == 0
    assert summary['production_adopted'] is False
    assert review_path.read_bytes() == before
    with pytest.raises(FileExistsError):
        subject.measure(review_path, partition_path, output)

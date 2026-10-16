import json

import cv2
import numpy as np
import pytest
from test_geometry_candidate_challenge import fixture

from scripts.diagnostics.prepare_geometry_review import prepare
from scripts.e2e.run_dataset_case import sha256_file


def test_geometry_review_hides_model_results_and_preserves_originals(tmp_path):
    candidate = fixture(tmp_path / "candidate")
    path = candidate / "candidate_report.json"
    report = json.loads(path.read_text(encoding="utf-8"))
    report["validation_frames"][0]["source_frame_pts"] = 1.25
    report["secret_score"] = "MUST_NOT_SHOW"
    # This test owns its synthetic frozen fixture; it updates its fingerprint.
    path.write_text(json.dumps(report), encoding="utf-8")
    fingerprint = candidate / "candidate_fingerprint.json"
    data = json.loads(fingerprint.read_text(encoding="utf-8"))
    from scripts.e2e.run_dataset_case import sha256_file

    data[path.name] = sha256_file(path)
    fingerprint.write_text(json.dumps(data), encoding="utf-8")
    before = sha256_file(candidate / "validation_frames/synthetic.jpg")
    output = tmp_path / "review"
    receipt = prepare(candidate, output)
    page = (output / "index.html").read_text(encoding="utf-8")
    assert "MUST_NOT_SHOW" not in page and receipt["model_scores_exposed"] is False
    assert receipt["frames"][0]["labels"] is None
    assert receipt["production_input"] is False and receipt["approved_ground_truth"] is False
    assert sha256_file(candidate / "validation_frames/synthetic.jpg") == before
    with pytest.raises(FileExistsError):
        prepare(candidate, output)


@pytest.fixture
def external_review(tmp_path):
    candidate = fixture(tmp_path / 'candidate')
    path = candidate / 'candidate_report.json'
    data = json.loads(path.read_text(encoding='utf-8'))
    data['source_sha256'] = 'a' * 64
    path.write_text(json.dumps(data), encoding='utf-8')
    fingerprint = candidate / 'candidate_fingerprint.json'
    frozen = json.loads(fingerprint.read_text(encoding='utf-8'))
    frozen[path.name] = sha256_file(path)
    fingerprint.write_text(json.dumps(frozen), encoding='utf-8')
    pool = tmp_path / 'pool'
    (pool / 'validation_frames').mkdir(parents=True)
    image = pool / 'validation_frames/frame.jpg'
    assert cv2.imwrite(str(image), np.full((100, 160, 3), 20, np.uint8))
    (pool / 'candidate_report.json').write_text(json.dumps({
        'source_sha256': 'a' * 64, 'validation_frames': [
            {'sha256': sha256_file(image), 'source_frame_pts': 2.5}],
        'expected_state': 'MUST_NOT_SHOW', 'scores': 'MUST_NOT_SHOW',
    }), encoding='utf-8')
    partition = tmp_path / 'partition.json'
    partition.write_text(json.dumps({
        'kind': 'development_holdout_partition_not_gt', 'source_video_sha256': 'a' * 64,
        'development': {'start_sec_inclusive': 0, 'end_sec_exclusive': 10},
        'holdout': {'start_sec_inclusive': 10, 'end_sec_exclusive': 20},
    }), encoding='utf-8')
    return candidate, pool, partition, tmp_path / 'review'


def test_external_geometry_review_binds_whole_pool_without_labels(external_review):
    candidate, pool, partition, output = external_review
    source_hash = sha256_file(pool / 'validation_frames/frame.jpg')
    receipt = prepare(candidate, output, source_pool=pool, partition=partition)
    assert receipt['external_source_pool'] is True
    assert receipt['source_inventory_sha256'] == sha256_file(pool / 'candidate_report.json')
    assert receipt['partition_sha256'] == sha256_file(partition)
    assert receipt['frames'][0]['source_sha256'] == source_hash
    assert receipt['frames'][0]['labels'] is None
    assert sha256_file(pool / 'validation_frames/frame.jpg') == source_hash
    assert sha256_file(output / 'source_01.jpg') == source_hash
    assert 'MUST_NOT_SHOW' not in (output / 'index.html').read_text(encoding='utf-8')
    assert str(pool) not in (output / 'index.html').read_text(encoding='utf-8')
    assert 'MUST_NOT_SHOW' not in json.dumps(receipt)


@pytest.mark.parametrize('change', ['holdout', 'overlap', 'source', 'pixels', 'no_partition'])
def test_external_geometry_review_rejects_invalid_sources(external_review, change):
    candidate, pool, partition, output = external_review
    path = pool / 'candidate_report.json'
    data = json.loads(path.read_text(encoding='utf-8'))
    if change == 'holdout':
        data['validation_frames'][0]['source_frame_pts'] = 10
    elif change == 'overlap':
        image = pool / 'validation_frames/frame.jpg'
        image.write_bytes((candidate / 'validation_frames/synthetic.jpg').read_bytes())
        data['validation_frames'][0]['sha256'] = sha256_file(image)
    elif change == 'source':
        data['source_sha256'] = 'b' * 64
    elif change == 'pixels':
        (pool / 'validation_frames/frame.jpg').write_bytes(b'changed')
    else:
        partition = None
    path.write_text(json.dumps(data), encoding='utf-8')
    with pytest.raises(ValueError):
        prepare(candidate, output, source_pool=pool, partition=partition)

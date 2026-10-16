import pytest

from scripts.e2e.practical_accuracy import evaluate_matched_boundary
from valorant_ai_coach.rounds.boundaries import BoundaryObservation


def predicted(time):
    return BoundaryObservation("round_start", "provisional", time, time + .85,
                               (time, time + .85), .93, {"producer": "synthetic"})


@pytest.mark.parametrize("offset,status", [
    (-.1, "PASS"), (.1, "PASS"), (.099, "PASS"), (.101, "FAIL"),
])
def test_tolerance_scores_boundary_and_never_confirmation(offset, status):
    result = evaluate_matched_boundary(predicted(4 + offset), truth_kind="round_start",
                                       truth_time_sec=4)
    assert result["status"] == status
    assert result["boundary_status"] == "provisional"
    assert result["absolute_error_sec"] == pytest.approx(abs(offset))


def test_wrong_kind_and_missing_boundary_never_pass():
    assert evaluate_matched_boundary(predicted(4), truth_kind="round_end",
                                      truth_time_sec=4)["status"] == "FAIL"
    assert evaluate_matched_boundary(None, truth_kind="round_start",
                                      truth_time_sec=4)["status"] == "FAIL"
    assert evaluate_matched_boundary(predicted(4), truth_kind="round_start",
                                      truth_time_sec=None)["status"] == "NE"


def test_batch_duplicate_is_false_positive_and_cannot_get_a_second_pass():
    from scripts.e2e.practical_accuracy import evaluate_boundary_set

    report = evaluate_boundary_set([predicted(4), predicted(4)], [
        {'id': 'S1', 'kind': 'round_start', 'time_sec': 4},
    ], complete_review=True)
    assert report['counts'] == {'PASS': 1, 'FAIL': 1, 'NE': 0}
    assert report['false_positive_count'] == 1
    assert report['matched_boundary_count'] == 1


def test_batch_wrong_kind_and_unreviewed_prediction_are_distinct():
    from scripts.e2e.practical_accuracy import evaluate_boundary_set

    truths = [{'id': 'E1', 'kind': 'round_end', 'time_sec': 4}]
    complete = evaluate_boundary_set([predicted(4)], truths, complete_review=True)
    assert complete['counts'] == {'PASS': 0, 'FAIL': 2, 'NE': 0}
    assert complete['false_positive_count'] == 1
    partial = evaluate_boundary_set([predicted(4)], truths)
    assert partial['counts'] == {'PASS': 0, 'FAIL': 1, 'NE': 1}
    assert partial['false_positive_count'] is None


def test_batch_association_does_not_replace_the_accuracy_tolerance():
    from scripts.e2e.practical_accuracy import evaluate_boundary_set

    report = evaluate_boundary_set([predicted(4.2)], [
        {'id': 'S1', 'kind': 'round_start', 'time_sec': 4},
    ], complete_review=True)
    assert report['matched_boundary_count'] == 1
    assert report['counts']['FAIL'] == 1
    assert report['false_positive_count'] == 0
    assert report['boundaries'][0]['absolute_error_sec'] == pytest.approx(.2)


def test_batch_delayed_confirmation_and_missing_point_truth():
    from scripts.e2e.practical_accuracy import evaluate_boundary_set

    report = evaluate_boundary_set([predicted(4)], [
        {'id': 'S1', 'kind': 'round_start', 'time_sec': 4},
        {'id': 'S2', 'kind': 'round_start', 'time_sec': None},
    ], complete_review=True)
    assert report['counts'] == {'PASS': 1, 'FAIL': 0, 'NE': 1}
    assert report['time_accuracy_rate'] == 1
    assert report['provisional_boundary_count'] == 1


def test_missing_point_truth_prevents_false_positive_certification():
    from scripts.e2e.practical_accuracy import evaluate_boundary_set

    result = evaluate_boundary_set([predicted(4)], [
        {'id': 'S1', 'kind': 'round_start', 'time_sec': None},
    ], complete_review=True)
    assert result['false_positive_count'] is None
    assert result['counts'] == {'PASS': 0, 'FAIL': 0, 'NE': 2}
    assert result['complete_boundary_review'] is False


def test_alignment_never_crosses_event_order():
    from scripts.e2e.practical_accuracy import evaluate_boundary_set

    end = BoundaryObservation('round_end', 'provisional', 4, 4.85,
                              (4, 4.85), .93, {'producer': 'synthetic'})
    result = evaluate_boundary_set([end, predicted(4.05)], [
        {'id': 'S1', 'kind': 'round_start', 'time_sec': 4},
        {'id': 'E1', 'kind': 'round_end', 'time_sec': 4.05},
    ], complete_review=True)
    assert result['matched_boundary_count'] == 1
    assert result['false_positive_count'] == 1


def test_alignment_handles_more_predictions_than_python_recursion_limit():
    from scripts.e2e.practical_accuracy import evaluate_boundary_set

    result = evaluate_boundary_set([predicted(i + 4) for i in range(1100)], [
        {'id': 'S1', 'kind': 'round_start', 'time_sec': 4},
    ])
    assert result['counts'] == {'PASS': 1, 'FAIL': 0, 'NE': 1099}


def test_accuracy_cli_keeps_input_hashes_and_canonical_scope(tmp_path):
    import hashlib
    import json

    from scripts.e2e.practical_accuracy import main

    prediction_file = tmp_path / 'predictions.json'
    truth_file = tmp_path / 'truth.json'
    report_file = tmp_path / 'reports' / 'accuracy.json'
    prediction_file.write_text(json.dumps({'boundaries': [predicted(4).to_dict()]}),
        encoding="utf-8",
    )
    truth_file.write_text(json.dumps({'complete_review': True, 'boundaries': [
        {'id': 'independent-start', 'kind': 'round_start', 'time_sec': 4},
    ]}),
        encoding="utf-8",
    )
    original_prediction, original_truth = prediction_file.read_bytes(), truth_file.read_bytes()
    assert main(['--predictions', str(prediction_file), '--truth', str(truth_file),
                 '--output', str(report_file)]) == 0
    report = json.loads(report_file.read_text(encoding="utf-8"))
    assert report['counts'] == {'PASS': 1, 'FAIL': 0, 'NE': 0}
    assert report['canonical_evaluation_modified'] is False
    assert report['source_binding']['source_binding_verified'] is False
    assert report['source_binding']['independent_label_review_verified'] is False
    assert report['inputs']['truth_sha256'] == hashlib.sha256(original_truth).hexdigest()
    assert prediction_file.read_bytes() == original_prediction
    assert truth_file.read_bytes() == original_truth


def test_cross_video_cli_cannot_publish_matching_time_pass(tmp_path):
    import json

    from scripts.e2e.practical_accuracy import main

    predictions = tmp_path / 'predictions.json'
    truth = tmp_path / 'truth.json'
    output = tmp_path / 'result.json'
    predictions.write_text(json.dumps({
        'source_video_sha256': 'a' * 64, 'boundaries': [predicted(4).to_dict()],
    }),
        encoding="utf-8",
    )
    truth.write_text(json.dumps({
        'source_video_sha256': 'b' * 64,
        'boundaries': [{'id': 'different-video-start', 'kind': 'round_start', 'time_sec': 4}],
    }),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match='source videos differ'):
        main(['--predictions', str(predictions), '--truth', str(truth), '--output', str(output)])
    assert not output.exists()


def test_source_agreement_does_not_certify_independent_label_review():
    from scripts.e2e.practical_accuracy import evaluation_source_binding

    result = evaluation_source_binding(
        {'source_video_sha256': 'a' * 64, 'boundaries': [predicted(4).to_dict()]},
        {'source_video_sha256': 'a' * 64},
    )
    assert result['source_binding_verified'] is True
    assert result['independent_label_review_verified'] is False


def test_partial_decoder_provenance_does_not_bind_unattested_boundary():
    from scripts.e2e.practical_accuracy import evaluation_source_binding

    first, second = predicted(4).to_dict(), predicted(8).to_dict()
    first['provenance']['source_video_sha256'] = 'a' * 64
    result = evaluation_source_binding({'boundaries': [first, second]},
                                       {'source_video_sha256': 'a' * 64})
    assert result['source_binding_verified'] is False


def test_package_formal_event_provenance_keeps_source_attestation():
    from scripts.e2e.practical_accuracy import evaluation_source_binding

    boundary = predicted(4).to_dict()
    boundary['provenance'] = {'event': {'attributes': {'evidence_provenance': {
        'source_video_sha256': 'a' * 64,
    }}}}
    result = evaluation_source_binding({'boundaries': [boundary]},
                                       {'source_video_sha256': 'a' * 64})
    assert result['source_binding_verified'] is True


def test_mixed_package_or_document_source_is_rejected():
    from scripts.e2e.practical_accuracy import evaluation_source_binding

    boundary = predicted(4).to_dict()
    boundary['provenance']['source_video_sha256'] = 'b' * 64
    with pytest.raises(ValueError, match='multiple source videos'):
        evaluation_source_binding({'source_video_sha256': 'a' * 64, 'boundaries': [boundary]},
                                  {'source_video_sha256': 'a' * 64})


@pytest.mark.parametrize('invalid', [True, '', 'A' * 64, 'not-a-hash'])
def test_malformed_source_hashes_are_rejected(invalid):
    from scripts.e2e.practical_accuracy import evaluation_source_binding

    with pytest.raises(ValueError, match='source SHA256'):
        evaluation_source_binding({'source_video_sha256': invalid, 'boundaries': []}, {})
    with pytest.raises(ValueError, match='source SHA256'):
        evaluation_source_binding({'boundaries': []}, {'source_video_sha256': invalid})


@pytest.mark.parametrize('offset,status', [(0, 'PASS'), (.05, 'PASS'), (.1, 'PASS'),
                                         (.101, 'FAIL'), (.1000000000005, 'FAIL')])
def test_point_policy_has_no_widening_epsilon(offset, status):
    from decimal import Decimal

    actual = float(Decimal('4') + Decimal(str(offset)))
    result = evaluate_matched_boundary(predicted(actual), truth_kind='round_start',
                                      truth_time_sec=4)
    assert result['status'] == status

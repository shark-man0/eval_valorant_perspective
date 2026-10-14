import json
from copy import deepcopy

import pytest

from scripts.e2e.practical_accuracy import main
from scripts.e2e.practical_export import export_package_boundaries
from tests.unit.test_round_package_builder import practical_build as practical_build
from tests.unit.test_round_package_builder import practical_candidate


def test_export_keeps_unknown_edges_and_original_candidate_times(practical_build):
    packages = practical_build(boundary_mode='practical', provisional_boundaries=[
        practical_candidate('round_start', 2, 2.5),
        practical_candidate('round_end', 5, 5.8),
        practical_candidate('round_start', 6, 6.4),
    ])
    before = deepcopy(packages)
    export = export_package_boundaries(packages)
    observed = [b for b in export['boundaries'] if b['boundary_status'] != 'unknown']
    assert [(b['kind'], b['boundary_time_sec']) for b in observed] == [
        ('round_start', 2), ('round_end', 5), ('round_start', 6),
    ]
    assert observed[0]['confirmation_time_sec'] == 2.5
    assert all(b['boundary_status'] == 'provisional' for b in observed)
    assert any(b['kind'] == 'round_end' and b['boundary_time_sec'] is None
               for b in export['boundaries'])
    assert packages == before
    assert not any(e['type'] in {'round_start', 'round_end'}
                   for p in packages for e in p['events'])


def test_formal_event_export_does_not_invent_confirmation(practical_build):
    event = {'event_id': 'formal-start', 'time_sec': 2, 'type': 'round_start',
             'actor': 'system', 'confidence': .9, 'attributes': {}}
    packages = practical_build(boundary_mode='practical', hud_events=[event],
                               provisional_boundaries=[practical_candidate('round_start', 2)])
    export = export_package_boundaries(packages)
    starts = [b for b in export['boundaries'] if b['kind'] == 'round_start'
              and b['boundary_time_sec'] is not None]
    assert len(starts) == 1
    assert starts[0]['boundary_status'] == 'confirmed'
    assert starts[0]['confirmation_time_sec'] is None
    assert starts[0]['provenance']['event']['actor'] == 'system'


def test_export_rejects_mixed_sources_and_overlapping_packages(practical_build):
    package = practical_build(boundary_mode='practical', require_detected_rounds=False)[0]
    changed = deepcopy(package)
    changed['source_video']['path'] = 'another.mp4'
    with pytest.raises(ValueError, match='one match and source'):
        export_package_boundaries([package, changed])
    with pytest.raises(ValueError, match='overlapping'):
        export_package_boundaries([package, deepcopy(package)])


def test_saved_packages_feed_separate_accuracy_cli(practical_build, tmp_path):
    packages = practical_build(boundary_mode='practical', provisional_boundaries=[
        practical_candidate('round_start', 2, 2.5),
    ])
    source = tmp_path / 'packages.json'
    truth = tmp_path / 'truth.json'
    report = tmp_path / 'accuracy.json'
    source.write_text(json.dumps({'round_packages': packages}), encoding="utf-8")
    truth.write_text(json.dumps({'boundaries': [
        {'id': 'synthetic-independent-start', 'kind': 'round_start', 'time_sec': 2},
    ]}),
        encoding="utf-8",
    )
    assert main(['--packages', str(source), '--truth', str(truth),
                 '--output', str(report)]) == 0
    result = json.loads(report.read_text(encoding="utf-8"))
    assert result['counts']['PASS'] == 1
    assert result['confirmed_boundary_count'] == 0
    assert result['provisional_boundary_count'] == 1
    assert result['package_export']['provisional_package_count'] == 1
    assert result['canonical_evaluation_modified'] is False

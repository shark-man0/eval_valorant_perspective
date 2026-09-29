import json
from pathlib import Path
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]

def load(rel):
    return json.loads((ROOT / rel).read_text(encoding='utf-8'))

obs_schema = load('schemas/visual_observation_schema_v2.json')
cand_schema = load('schemas/visual_event_candidate_schema_v2.json')
contract = load('config/visual_event_detection_contract_v2.json')
sampling = load('config/visual_sampling_policy_v2.json')
semantic = load('config/visual_semantic_inference_policy_v2.json')
visual_conf = load('config/visual_confidence_policy_v1.json')
map_spatial = load('config/map_spatial_fact_policy_v1.json')
projection = load('config/event_projection_contract_v1.json')
ability = load('config/ability_slot_contract_v1.json')
remote = load('config/remote_view_detection_policy_v1.json')
logic = load('tests/visual_logic_cases_v2.json')
real = load('tests/real_video_windows_v2.json')
fixture = load('tests/fixtures/coarse_zone_fixture_test_map.json')

Draft202012Validator.check_schema(obs_schema)
Draft202012Validator.check_schema(cand_schema)

required_visual = {
    'enemy_spotted','enemy_lost','engagement_start','engagement_end','shot',
    'movement_state','preaim_started','peek','info_peek','position_change',
    'position_hold','rotation_started','rotation_completed','utility_used',
    'ally_entry_start','ally_enter_site','enemy_reengage','hold_angle',
    'site_state','utility_effect_observed'
}
missing = required_visual - set(contract['events'])
assert not missing, f'Missing visual event contracts: {sorted(missing)}'

# No coaching/evaluation fields in factual event attributes.
for ev, cfg in contract['events'].items():
    attrs = ' '.join(cfg.get('round_package_attributes', [])).lower()
    assert all(word not in attrs for word in ('good','bad','improve','mistake'))

# High-priority review fixes.
peek = contract['events']['peek']
assert 'forbidden_for_exposure_count' in peek['semantic_confirmation']
assert map_spatial['exposed_directions_count']['semantic_vlm_allowed'] is False
assert map_spatial['exposed_directions_count']['authoritative_source'] == 'static_peek_exposure_registry_only'

preaim = contract['events']['preaim_started']
assert 'does not use homography/back-projected' in preaim['notes'].lower()
assert semantic['confidence_policy']['semantic_only_cap_for_preaim'] < 0.70

# Pass B must be the guaranteed low-cost trigger scan.
pass_b = next(p for p in sampling['passes'] if p['id'] == 'B_always_on_trigger_scan')
assert pass_b['fps'] >= 5
assert 'ammo' in pass_b['purpose'].lower()
assert sampling['cross_module_trigger_contract']['shot_event_granularity'].startswith('MVP emits a shot event')

# Visual confidence tiers must exist and be distinct from coach confidence.
for tier in ('A','B','C'):
    assert tier in visual_conf['tiers']
    assert 0 <= visual_conf['tiers'][tier]['below_candidate_min'] <= 1

# Ability slots are logical and rebind-safe.
assert ability['rebind_safe'] is True
assert set(ability['logical_slots']) == {'C','Q','E','X'}
assert 'Never OCR' in ability['implementation_rule']

# Remote ambiguity must fail safe.
assert 'unknown' in remote['safety']

# Projection must explicitly drop intermediate spatial fields.
spatial_rule = next(r for r in projection['rules'] if r['source'] == 'VisualObservation.spatial')
for field in ('cover_edge_score','confidence','exposed_directions_source'):
    assert field in spatial_rule['drop']

# Logic test coverage from review.
ids = {c['id'] for c in logic['cases']}
required_case_ids = {f'VA-{i:03d}' for i in range(17, 34)}
assert required_case_ids.issubset(ids), f'Missing v2 review cases: {sorted(required_case_ids - ids)}'
assert len(logic['cases']) >= 30
assert len(real['windows']) >= 6

# Coarse-zone fixture has both zone and site semantics and one static peek anchor.
assert len(fixture['zones']) >= 3
assert len(fixture['sites']) >= 2
assert len(fixture['peek_exposure_anchors']) >= 1

# Semantic budget is bounded.
inv = semantic['invocation_policy']
assert inv['max_calls_per_round'] > 0
assert inv['max_calls_per_match'] >= inv['max_calls_per_round']
assert 'independent' in inv['session_isolation'].lower()

print('visual patch v2 validation: OK')
print('visual event contracts:', len(contract['events']))
print('logic cases:', len(logic['cases']))
print('real video windows:', len(real['windows']))
print('semantic budget:', inv['max_calls_per_round'], 'per round /', inv['max_calls_per_match'], 'per match')

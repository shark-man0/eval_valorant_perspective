import json, hashlib, sys
from pathlib import Path
from itertools import combinations
from jsonschema import Draft202012Validator
from shapely.geometry import Polygon, Point
from shapely.ops import unary_union
from reference_runtime_v3 import detect_rotation, detect_team_entry, fuse, edge_pairs
ROOT=Path(__file__).resolve().parents[1]
load=lambda p: json.loads((ROOT/p).read_text(encoding='utf-8'))
MAP=load('config/maps/summit_map_v3.json'); CAL=load('config/maps/summit_callout_registry_v3.json'); PEEK=load('config/maps/summit_peek_exposure_registry_v2.json'); MASK=load('config/maps/summit_operational_mask_v1.json'); REG=load('config/map_registry_v1.json'); RUN=load('config/map_zone_runtime_contract_v4.json'); CASES=load('tests/map_zone_runtime_cases_v3.json')
TRI=load('config/maps/fixtures/three_site_fixture_v1.json'); SPL=load('config/maps/fixtures/special_link_fixture_v1.json')
SCHEMAS={'map':load('schemas/map_zone_map_schema_v3.json'),'callout':load('schemas/callout_registry_schema_v1.json'),'peek':load('schemas/peek_exposure_registry_schema_v1.json'),'mask':load('schemas/operational_mask_schema_v1.json'),'registry':load('schemas/map_registry_schema_v1.json'),'runtime':load('schemas/map_zone_runtime_contract_schema_v1.json')}

def validate(schema,obj,name):
    errs=sorted(Draft202012Validator(schema).iter_errors(obj),key=lambda e:list(e.path))
    assert not errs, name+': '+ '; '.join(f"{list(e.path)} {e.message}" for e in errs[:5])

def resolve_point(point):
    pt=Point(*point); matches=[]
    for z in MAP['zones']:
        poly=Polygon(z['polygon_norm'])
        if poly.contains(pt) or poly.touches(pt): matches.append(z)
    if len(matches)!=1: return None
    return matches[0]['zone_id']

def main():
    validate(SCHEMAS['map'],MAP,'summit map'); validate(SCHEMAS['map'],TRI,'three site fixture'); validate(SCHEMAS['map'],SPL,'special link fixture')
    validate(SCHEMAS['callout'],CAL,'callout'); validate(SCHEMAS['peek'],PEEK,'peek'); validate(SCHEMAS['mask'],MASK,'mask'); validate(SCHEMAS['registry'],REG,'registry'); validate(SCHEMAS['runtime'],RUN,'runtime')
    # registry file references and geometry versions must resolve exactly
    sm=REG['maps']['summit']; assert (ROOT/sm['map_file']).exists() and (ROOT/sm['callout_registry_file']).exists() and (ROOT/sm['peek_registry_file']).exists() and (ROOT/sm['coverage_mask_file']).exists()
    assert sm['geometry_version']==MAP['geometry_version']
    assert 'matched_zone.geometry_confidence_cap' in RUN['canonical_provider_ids']['polygon']['confidence_rule']
    zone_ids={z['zone_id'] for z in MAP['zones']}; assert len(zone_ids)==len(MAP['zones'])
    # topology is single source of truth
    assert 'adjacency' not in MAP
    for e in MAP['topology_edges']:
        assert e['from_zone_id'] in zone_ids and e['to_zone_id'] in zone_ids
    # every site zone exists and is kind=site with matching site_id
    zi={z['zone_id']:z for z in MAP['zones']}
    for s in MAP['sites']:
        for zid in s['zone_ids']:
            assert zid in zi and zi[zid]['kind']=='site' and zi[zid]['site_id']==s['site_id']
    # independent mask asset hash
    actual=hashlib.sha256((ROOT/MASK['reference_asset']).read_bytes()).hexdigest(); assert actual==MASK['reference_sha256']==REG['maps']['summit']['reference_sha256']
    mask=Polygon(MASK['polygon_norm']); polys={z['zone_id']:Polygon(z['polygon_norm']).intersection(mask) for z in MAP['zones']}
    overlap_total=0.0; max_pair=(None,0.0)
    for a,b in combinations(polys,2):
        area=polys[a].intersection(polys[b]).area; overlap_total+=area
        if area>max_pair[1]: max_pair=((a,b),area)
    union=unary_union(list(polys.values())); gap_ratio=mask.difference(union).area/mask.area; overlap_ratio=overlap_total/mask.area
    assert overlap_ratio<=0.005+1e-12,(overlap_ratio,max_pair); assert gap_ratio<=0.12+1e-12,gap_ratio
    # callout single source + refs
    assert 'callout_to_operational_zone' not in CAL and 'official_callouts' not in CAL
    for name,r in CAL['records'].items(): assert r['zone_id'] in zone_ids
    # provider identifiers normalized
    assert list(RUN['canonical_provider_ids'])==['location_label','polygon','coarse_fallback']
    assert MAP['resolution_priority']==['location_label','polygon','coarse_fallback','unknown']
    checked=0
    fixtures={'three_site_fixture':TRI,'special_link_fixture':SPL}
    # alias helper
    aliases={a:name for name,r in CAL['records'].items() for vals in r['aliases'].values() for a in vals}
    for case in CASES['cases']:
        k=case['kind']
        if k=='schema_validation': pass
        elif k=='polygon_point': assert resolve_point(case['point_norm'])==case['expected_zone_id']
        elif k.startswith('fusion_'):
            z,conf,src,diag=fuse(case.get('label_zone'),case.get('label_conf',0),case.get('poly_zone'),case.get('poly_conf',0),previous_zone=case.get('previous_zone'),boundary_ambiguous=case.get('boundary',False)); assert z==case['expected'] and src==case['source'],(case['id'],z,src)
        elif k in ('rotation_summit','no_rotation_same_affinity'):
            got=detect_rotation(MAP,case['sequence']); assert bool(got)==case['expect'],(case['id'],got)
        elif k in ('rotation_three_site_fixture','special_link_fixture'):
            fm=fixtures[case['fixture']]; got=detect_rotation(fm,case['sequence']); assert bool(got)==case['expect'],(case['id'],got)
            if case.get('required_edge_kind'):
                kinds=[edge_pairs(fm)[frozenset((a,b))]['edge_kind'] for a,b in zip(case['sequence'],case['sequence'][1:])]; assert case['required_edge_kind'] in kinds
        elif k=='team_entry':
            got=detect_team_entry(MAP,case['from'],case['to'],case['dwell'],RUN['temporal_debounce']['site_entry_persistence_sec']); assert got and got['entry_start']==case['expect_start'] and got['entered']==case['expect_enter']
        elif k=='team_entry_not_site': assert detect_team_entry(MAP,case['from'],case['to'],case['dwell'],RUN['temporal_debounce']['site_entry_persistence_sec']) is None
        elif k=='geometry_confidence': assert min(case['calibration'],case['marker'],case['geometry_cap'])==case['expected']
        elif k=='callout_alias': assert aliases[case['alias']]==case['expected']
        elif k=='calibration_required_profile': assert REG['minimap_policy']['dynamic_rotation']=='unsupported_in_mvp' and case['expect']=='calibration_required'
        elif k=='map_unresolved': assert REG['selection_policy']['manual_fallback_required'] and case['expect_zone_events'] is False
        elif k=='peek_unmatched': assert PEEK['anchors']==[] and PEEK['policy']['default_when_unmatched'] is case['expected']
        elif k=='topology_single_source': assert 'adjacency' not in MAP and RUN['consumer_contract']['topology_source_of_truth'].startswith('topology_edges')
        elif k=='provider_ids': assert set(RUN['canonical_provider_ids'])=={'location_label','polygon','coarse_fallback'}
        elif k=='operational_mask_independent': assert MAP['coverage_mask_file'].endswith('summit_operational_mask_v1.json') and 'mask_polygon_norm' not in MAP
        elif k=='callout_single_source': assert 'records' in CAL and 'callout_to_operational_zone' not in CAL
        elif k=='duration_based_stability': assert CAL['location_label_policy']['stable_duration_sec']>0 and 'stable_frames_min' not in CAL['location_label_policy']
        elif k=='visual_override':
            ov=load('integration_overrides/visual_analyzer_v2/visual_analyzer_map_contract_overrides_v1.json'); assert 'config/map_zone_runtime_contract_v1.json' in ov['must_ignore_or_remove']
        elif k=='boundary_ambiguous_no_previous':
            z,conf,src,_=fuse('summit_a_site',.91,'summit_a_link',.92,previous_zone=None,boundary_ambiguous=True); assert z is None and src=='unknown'
        else: raise AssertionError('unknown '+k)
        checked+=1
    print(f'map zone patch v3 validation: OK ({checked} cases)')
    print(f'zones={len(MAP["zones"])} callouts={len(CAL["records"])} topology_edges={len(MAP["topology_edges"])}')
    print(f'coverage gap={gap_ratio:.4%} overlap={overlap_ratio:.4%} max_pair_overlap={max_pair[1]:.8f}')
if __name__=='__main__': main()

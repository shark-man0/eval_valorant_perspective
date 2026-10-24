import hashlib
from copy import deepcopy

import cv2
import numpy as np
import pytest

from scripts.diagnostics.hud_scope_structure import (
    component_geometry,
    component_support,
    outline_mask,
    reference_fingerprint,
)
from scripts.diagnostics.result_title_region import title_region
from scripts.diagnostics.round_lifecycle_evidence import lifecycle
from scripts.temporal_gt.contract import canonical_hash
from tests.unit.test_hud_scope_structure import reference
from tests.unit.test_round_lifecycle_evidence import chain
from valorant_ai_coach.hud.layout import HudLayout, NormalizedRoi


def bound_rows():
    t, m = reference()
    image = np.zeros((240, 600, 3), np.uint8)
    image[:90] = cv2.cvtColor(t, cv2.COLOR_GRAY2BGR)
    cv2.putText(image, 'THRIFTY', (220, 160), cv2.FONT_HERSHEY_SIMPLEX, .8, (255,)*3, 2)
    layout = HudLayout('3.0', True, (600, 240), {
        'top_match_bar': NormalizedRoi(0, 0, 1, 90/240),
        'round_end_banner': NormalizedRoi(200/600, 110/240, 200/600, 100/240),
    }, layout_format='v3')
    crop = image[110:210, 200:400]
    region = title_region(crop)
    assert region['status'] == 'PROPOSAL'
    a, b, c, d = region['bounds']
    region.update(outer_pixel_bounds=[200,110,400,210],
                  text_pixel_bounds=[200+a,110+b,200+c,110+d],
                  crop_pixel_sha256=hashlib.sha256(crop[b:d,a:c].tobytes()).hexdigest())
    refs = [(t, outline_mask(t,m))]
    bindings = {k: 'a'*64 for k in (
        'layout_sha256','reader_profile_sha256','reference_bank_sha256')}
    bindings['references_sha256'] = reference_fingerprint(refs)
    rows = chain()
    for f in rows:
        f['geometry_consistent'] = False
        f['pixel_sha256'] = hashlib.sha256(image.tobytes()).hexdigest()
        f['result']['region'] = deepcopy(region)
        f['component_geometry'] = component_geometry(f,image,layout,refs,bindings)
    return rows, image, layout, refs, bindings


def test_round_components_allow_development_chain_without_rewriting_global_or_owner():
    rows, *_ = bound_rows()
    without = deepcopy(rows)
    for f in without:
        del f['component_geometry']
    assert lifecycle(without)['chains'][0]['status'] == 'UNKNOWN'
    r = lifecycle(rows)
    assert r['chains'][0]['status'] == 'DEVELOPMENT_LIFECYCLE_CANDIDATE'
    assert all(f['geometry_consistent'] is False for f in rows)
    assert all(f['component_geometry']['ownership_authorized'] is False for f in rows)
    assert r['formal_events'] == [] and not r['qualification_created']


@pytest.mark.parametrize('fault', [
    'source','epoch','pixels','profile','score','role','authorization','reader','duplicate_tile',
    'integer_role',
])
def test_modified_receipts_cannot_support_any_component(fault):
    rows, *_ = bound_rows()
    f=rows[2]
    v=f['component_geometry']
    if fault in ('source','epoch','pixels'):
        key={'source':'source_sha256','epoch':'epoch','pixels':'pixel_sha256'}[fault]
        f[key]='different'
    elif fault=='profile':
        v['bindings']['layout_sha256']='wrong'
    elif fault=='score':
        v['top_scope']['tiles'][0]['score']=.89
        v['evidence_sha256']=canonical_hash({k:x for k,x in v.items() if k!='evidence_sha256'})
    elif fault=='role':
        v['roles']['result']=False
    elif fault=='reader':
        f['enemy_score']['value']='99'
    elif fault=='duplicate_tile':
        v['top_scope']['tiles'][1]=deepcopy(v['top_scope']['tiles'][0])
        v['evidence_sha256']=canonical_hash({k:x for k,x in v.items() if k!='evidence_sha256'})
    elif fault=='integer_role':
        v['roles']['score']=1
        v['evidence_sha256']=canonical_hash({k:x for k,x in v.items() if k!='evidence_sha256'})
    else:
        v['ownership_authorized']=True
    with pytest.raises(ValueError,match='component'):
        component_support(f,'score')


def test_component_profile_change_within_one_epoch_is_rejected():
    rows, image, layout, refs, bindings = bound_rows()
    other={**bindings,'layout_sha256':'b'*64}
    rows[4]['component_geometry']=component_geometry(rows[4],image,layout,refs,other)
    with pytest.raises(ValueError,match='profile changed'):
        lifecycle(rows)


def test_blank_result_pixels_or_wrong_reference_do_not_authorize_result():
    rows,image,layout,refs,bindings=bound_rows()
    f=rows[0]
    blank=image.copy()
    blank[110:210]=0
    f['pixel_sha256']=hashlib.sha256(blank.tobytes()).hexdigest()
    f['component_geometry']=component_geometry(f,blank,layout,refs,bindings)
    assert component_support(f,'score') and not component_support(f,'result')
    with pytest.raises(ValueError,match='reference'):
        component_geometry(f,blank,layout,[(refs[0][0],np.zeros_like(refs[0][1]))],bindings)


def test_components_do_not_repair_native_gap_or_duplicate_pts():
    rows, *_ = bound_rows()
    gap = deepcopy(rows)
    gap.pop(2)
    assert all(c['status']=='UNKNOWN' for c in lifecycle(gap)['chains'])
    with pytest.raises(ValueError,match='duplicate'):
        lifecycle(rows+[deepcopy(rows[0])])


def test_joint_component_receipt_keeps_original_source_profile_and_no_full_hud_authority():
    rows, image, layout, refs, bindings = bound_rows()
    layout.regions.update({
        'ally_score': NormalizedRoi(0,0,1/3,90/240),
        'round_timer': NormalizedRoi(1/3,0,1/3,90/240),
        'enemy_score': NormalizedRoi(2/3,0,1/3,90/240),
    })
    f = rows[2]
    f['component_geometry'] = component_geometry(f,image,layout,refs,bindings,joint_regions=True)
    assert component_support(f,'score')
    assert f['component_geometry']['method'] == 'frozen_long_outline_joint_regions_v1'
    assert f['component_geometry']['bindings'] == bindings
    assert f['geometry_consistent'] is False
    assert f['component_geometry']['ownership_authorized'] is False
    v = f['component_geometry']
    v['joint_scope']['regions']['ally_score']['tiles'][0]['score'] = .89
    v['evidence_sha256'] = canonical_hash({k:x for k,x in v.items() if k!='evidence_sha256'})
    with pytest.raises(ValueError):
        component_support(f,'score')

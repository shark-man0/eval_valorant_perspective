from __future__ import annotations
import json, math
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
D=json.loads((ROOT/'fixtures/map_zone_synthetic_v1.json').read_text())

def norm(pixel):
    x0,y0,x1,y1=D['calibration']['pixel_roi']; x,y=pixel
    return ((x-x0)/(x1-x0),(y-y0)/(y1-y0))
def point_in_poly(x,y,poly):
    inside=False; j=len(poly)-1
    for i,(xi,yi) in enumerate(poly):
        xj,yj=poly[j]
        if ((yi>y)!=(yj>y)) and x < (xj-xi)*(y-yi)/(yj-yi+1e-15)+xi: inside=not inside
        j=i
    return inside
def dist_to_vertical_boundary(x): return min(abs(x-0.45),abs(x-0.55))
for c in D['cases']:
    x,y=norm(c['pixel'])
    if dist_to_vertical_boundary(x)<=D['boundary_margin_norm']+1e-12:
        zone=None; bs='ambiguous'
    else:
        hits=[z['zone_id'] for z in D['zones'] if point_in_poly(x,y,z['polygon'])]
        zone=hits[0] if len(hits)==1 else None; bs='interior' if len(hits)==1 else 'ambiguous'
    assert zone==c['expected_zone'],(c['id'],x,zone)
    assert bs==c['expected_boundary_state'],(c['id'],bs)
print('map/zone synthetic fixture: OK',len(D['cases']))

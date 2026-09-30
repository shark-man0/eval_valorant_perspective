from __future__ import annotations
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
D=json.loads((ROOT/'fixtures/shot_granularity_contract_v1.json').read_text())

def reference_count(samples):
    # Contract reference only: open a burst on ammo-decrease/muzzle evidence; close after 0.30s without firing cue.
    # Ammo increase, reload, and weapon switch are exclusions.
    count=0; in_burst=False; last_fire=None; prev=None
    for s in samples:
        t=s['t']
        if prev is not None:
            if s.get('weapon') is not None and prev.get('weapon') is not None and s.get('weapon')!=prev.get('weapon'):
                in_burst=False; prev=s; continue
            if s.get('reload') or (s.get('ammo') is not None and prev.get('ammo') is not None and s['ammo']>prev['ammo']):
                in_burst=False; prev=s; continue
            decreased=s.get('ammo') is not None and prev.get('ammo') is not None and s['ammo']<prev['ammo']
            fire=bool(s.get('muzzle')) or decreased
            if in_burst and last_fire is not None and t-last_fire>0.30: in_burst=False
            if fire:
                if not in_burst: count+=1; in_burst=True
                last_fire=t
        prev=s
    return count
for c in D['cases']:
    got=reference_count(c['input_samples'])
    assert got==c['expected_shot_events'],(c['id'],got,c['expected_shot_events'])
print('shot granularity synthetic contract: OK',len(D['cases']))

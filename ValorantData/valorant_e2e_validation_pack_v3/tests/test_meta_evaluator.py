from __future__ import annotations
import json, copy
from pathlib import Path
from reference_evaluator import evaluate
ROOT=Path(__file__).resolve().parents[1]
A=json.loads((ROOT/'tests/generated/e2e_assertions_v3.json').read_text(encoding='utf-8'))

def make_oracle():
    out={'events':[],'state_intervals':[],'ownership_intervals':[],'snapshots':[],'visual_observations':[],'temporal_features':[]}
    for p in A['required_point_events']:
        t=sum(p['acceptance_window'])/2
        out['events'].append({'oracle_id':p['id'],'round_id':p['round_id'],'type':p['type'],'actor':p['actor'],'time_sec':t,'attributes':copy.deepcopy(p.get('required_event_attributes',{})),'confidence':0.9})
    for c in A['event_count_constraints']:
        existing=[e for e in out['events'] if e['round_id']==c['round_id'] and e['type']==c['type'] and e['actor']==c['actor']]
        if len(existing)<c['min']:
            t=sum(c.get('window',[1,1]))/2 if 'window' in c else 1.0
            for _ in range(c['min']-len(existing)): out['events'].append({'round_id':c['round_id'],'type':c['type'],'actor':c['actor'],'time_sec':t,'attributes':{},'confidence':0.85})
    for s in A['required_state_intervals']:
        iv=s['core_interval'][:]
        if s.get('edge_brackets'): iv=[s['edge_brackets']['start']['first_present_sec'],s['edge_brackets']['end']['last_present_sec']]
        out['state_intervals'].append({'round_id':s['round_id'],'state':s['state'],'subtype':s['subtype'],'interval':iv,'confidence':0.9})
    for s in A['required_ownership_intervals']:
        out['ownership_intervals'].append({'round_id':s['round_id'],'owner':s['owner'],'interval':s['core_interval'][:],'confidence':0.95})
    for s in A['required_snapshots']:
        x={'round_id':s['round_id'],'time_sec':s['time_sec'],'confidence':0.9}; x.update(s['expected']); out['snapshots'].append(x)
    for d in A.get('derived_assertions',[]):
        cand=min([x for x in out['snapshots'] if x['round_id']==d['round_id']],key=lambda x:abs(x['time_sec']-d['time_sec']))
        cand[d['field']]=d['expected']
    for v in A.get('required_visual_observations',[]): out['visual_observations'].append({'round_id':v['round_id'],'observation':v['observation'],'actor':v['actor'],'time_sec':v['time_sec'],'confidence':0.9})
    return out

oracle=make_oracle(); f=evaluate(A,oracle); assert not f,f
assert evaluate(A,{'events':[],'state_intervals':[],'ownership_intervals':[],'snapshots':[],'visual_observations':[],'temporal_features':[]}), 'null analyzer must fail'
shift=copy.deepcopy(oracle)
for e in shift['events']: e['time_sec']+=10
for key in ('state_intervals','ownership_intervals'):
    for s in shift[key]: s['interval']=[s['interval'][0]+10,s['interval'][1]+10]
for s in shift['snapshots']: s['time_sec']+=10
for v in shift['visual_observations']: v['time_sec']+=10
assert evaluate(A,shift), '+10s shifted output must fail'
swap=copy.deepcopy(oracle)
for e in swap['events']:
    if e['actor']=='player': e['actor']='ally'
assert evaluate(A,swap), 'event ownership swap must fail'
own=copy.deepcopy(oracle)
for x in own['ownership_intervals']:
    if x['owner']=='teammate_spectated': x['owner']='self'
assert evaluate(A,own), 'view ownership corruption must fail'
emit=copy.deepcopy(oracle); emit['events'].append({'round_id':'sample_round_2','type':'shot','actor':'player','time_sec':170.0,'attributes':{},'confidence':0.9})
assert evaluate(A,emit), 'spectator shot must fail'
facts=copy.deepcopy(oracle)
for e in facts['events']:
    if e.get('oracle_id')=='GT-R2-DEATH': e['attributes']['killer_agent']='WrongAgent'
assert evaluate(A,facts), 'fact corruption must fail'
state_over=copy.deepcopy(oracle)
for s in state_over['state_intervals']:
    if s['state']=='remote_control_view' and s['round_id']=='sample_round_1': s['interval']=[9.0,13.0]; break
assert evaluate(A,state_over), 'state overreach must fail'
state_edge=copy.deepcopy(oracle)
for s in state_edge['state_intervals']:
    if s['state']=='vision_obscured_smoke': s['interval'][0]=59.0; break
assert evaluate(A,state_edge), 'state edge violation must fail'
disc=copy.deepcopy(oracle); disc['temporal_features'].append({'feature':'movement_state.duration_sec','interval':[74.0,74.8],'value':0.8,'confidence':0.8})
assert evaluate(A,disc), 'feature spanning discontinuity must fail'
conf=copy.deepcopy(oracle); conf['events'][0]['confidence']=1.2
assert evaluate(A,conf), 'out-of-range confidence must fail'
vocab=copy.deepcopy(oracle); vocab['events'].append({'round_id':'sample_round_1','type':'enemy_spotted','actor':'player','time_sec':50.0,'attributes':{'source':'magic'},'confidence':0.6})
assert evaluate(A,vocab), 'unknown source token must fail'
der=copy.deepcopy(oracle)
for s in der['snapshots']:
    if 'zone_id' in s: s['zone_id']='wrong_zone'; break
assert evaluate(A,der), 'derived zone corruption must fail'
vis=copy.deepcopy(oracle); vis['visual_observations']=[]
assert evaluate(A,vis), 'missing visual observations must fail'

poison=copy.deepcopy(oracle)
poison['snapshots'].append({'round_id':'sample_round_2','time_sec':151.0,'ammo_mag':21,'ammo_reserve':50,'weapon':'Vandal','zone_id':'summit_mid','confidence':0.9})
assert evaluate(A,poison), 'spectator HUD/location tuple contamination must fail'

print('meta evaluator tests: OK (positive oracle; 13 corruption modes fail)')

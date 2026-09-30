from __future__ import annotations
import math

def _overlap(a,b): return max(0.0,min(a[1],b[1])-max(a[0],b[0]))
def _subset(expected,actual): return all(actual.get(k)==v for k,v in expected.items())
def _union_coverage(target, intervals):
    clipped=[]
    for iv in intervals:
        a=max(target[0],iv[0]); b=min(target[1],iv[1])
        if b>a: clipped.append((a,b))
    if not clipped: return 0.0
    clipped.sort(); total=0.0; a,b=clipped[0]
    for x,y in clipped[1:]:
        if x<=b: b=max(b,y)
        else: total+=b-a; a,b=x,y
    return total+(b-a)

def _finite_confidence_failures(output):
    failures=[]
    groups=('events','state_intervals','ownership_intervals','snapshots','visual_observations','temporal_features')
    for g in groups:
        for i,x in enumerate(output.get(g,[])):
            for k,v in x.items():
                if k=='confidence' or k.endswith('_confidence'):
                    if not isinstance(v,(int,float)) or isinstance(v,bool) or not math.isfinite(float(v)) or not (0.0<=float(v)<=1.0):
                        failures.append(f'confidence:{g}:{i}:{k}')
    return failures

def evaluate(assertions,output):
    failures=[]
    events=output.get('events',[]); states=output.get('state_intervals',[]); owners=output.get('ownership_intervals',[])
    snaps=output.get('snapshots',[]); vis=output.get('visual_observations',[]); temporal=output.get('temporal_features',[])
    matched={}
    for req in assertions['required_point_events']:
        cand=[e for e in events if e.get('round_id')==req['round_id'] and e.get('type')==req['type'] and e.get('actor')==req['actor'] and req['acceptance_window'][0] <= e.get('time_sec',-1) <= req['acceptance_window'][1] and _subset(req.get('required_event_attributes',{}),e.get('attributes',{}))]
        if not cand: failures.append('missing_point:'+req['id'])
        else:
            center=sum(req['acceptance_window'])/2; matched[req['id']]=min(cand,key=lambda e:abs(e.get('time_sec',0)-center))
    for oc in assertions['ordering_constraints']:
        be=matched.get(oc['before']); af=matched.get(oc['after'])
        if be is not None and af is not None and be['time_sec']>=af['time_sec']: failures.append('ordering:'+oc['before']+'>='+oc['after'])
    for req in assertions['required_state_intervals']:
        core=req['core_interval']; outer=req['outer_interval']; dur=core[1]-core[0]
        matching=[s for s in states if s.get('round_id')==req['round_id'] and s.get('state')==req['state'] and (req.get('subtype') is None or s.get('subtype')==req.get('subtype'))]
        local=[s for s in matching if _overlap(outer,s.get('interval',[-1,-1]))>0]
        covered=_union_coverage(core,[s.get('interval',[-1,-1]) for s in local])
        if dur>0 and covered/dur+1e-9<req['min_core_coverage']: failures.append('state_coverage:'+req['id'])
        if req.get('exhaustive'):
            for s in local:
                iv=s.get('interval',[-1,-1])
                if iv[0]<outer[0]-1e-9 or iv[1]>outer[1]+1e-9: failures.append('state_overreach:'+req['id']); break
        if req.get('edge_brackets') and local:
            best=max(local,key=lambda s:_overlap(core,s.get('interval',[-1,-1]))); iv=best.get('interval',[-1,-1]); eb=req['edge_brackets']
            sb=eb['start']; en=eb['end']
            if not (sb['last_absent_sec']-1e-9 <= iv[0] <= sb['first_present_sec']+1e-9): failures.append('state_start_edge:'+req['id'])
            if not (en['last_present_sec']-1e-9 <= iv[1] <= en['first_absent_sec']+1e-9): failures.append('state_end_edge:'+req['id'])
    for req in assertions.get('required_ownership_intervals',[]):
        core=req['core_interval']; outer=req['outer_interval']; dur=core[1]-core[0]
        local=[s for s in owners if s.get('round_id')==req['round_id'] and s.get('owner')==req['owner'] and _overlap(outer,s.get('interval',[-1,-1]))>0]
        covered=_union_coverage(core,[s.get('interval',[-1,-1]) for s in local])
        if dur>0 and covered/dur+1e-9<req.get('min_core_coverage',0.9): failures.append('ownership_coverage:'+req['id'])
    matched_snaps={}
    for req in assertions['required_snapshots']:
        cand=[s for s in snaps if s.get('round_id')==req['round_id'] and abs(s.get('time_sec',-999)-req['time_sec'])<=req['tolerance_sec']]
        if not cand: failures.append('missing_snapshot:'+req['id']); continue
        s=min(cand,key=lambda x:abs(x['time_sec']-req['time_sec'])); matched_snaps[(req['round_id'],req['id'])]=s
        for k,v in req['expected'].items():
            if s.get(k)!=v: failures.append(f"snapshot:{req['id']}:{k}")
    for req in assertions.get('derived_assertions',[]):
        cand=[s for s in snaps if s.get('round_id')==req['round_id'] and abs(s.get('time_sec',-999)-req['time_sec'])<=req['tolerance_sec']]
        if not cand: failures.append('missing_derived_snapshot:'+req['id']); continue
        s=min(cand,key=lambda x:abs(x['time_sec']-req['time_sec']))
        if s.get(req['field'])!=req['expected']: failures.append('derived:'+req['id'])
    for req in assertions.get('required_visual_observations',[]):
        cand=[v for v in vis if v.get('round_id')==req['round_id'] and v.get('observation')==req['observation'] and v.get('actor')==req['actor'] and abs(v.get('time_sec',-999)-req['time_sec'])<=req['tolerance_sec']]
        if not cand: failures.append('missing_visual_observation:'+req['id'])
    for c in assertions['event_count_constraints']:
        es=[e for e in events if e.get('type')==c['type'] and e.get('actor')==c['actor'] and e.get('round_id')==c['round_id']]
        if 'window' in c: es=[e for e in es if c['window'][0]<=e.get('time_sec',-1)<=c['window'][1]]
        if not (c['min']<=len(es)<=c['max']): failures.append('count:'+c['round_id']+':'+c['type'])
    # Stable attribute vocabulary.
    for e in events:
        spec=assertions.get('attribute_vocab',{}).get(e.get('type'))
        if spec and 'source' in e.get('attributes',{}):
            if e['attributes']['source'] not in spec.get('source_enum',[]): failures.append('attribute_vocab:'+e.get('type','?')+':source')
    for n in assertions['negative_assertions']:
        w=n['window']
        if 'must_not_emit_player_event_types' in n:
            bad=[e for e in events if e.get('actor')=='player' and e.get('type') in n['must_not_emit_player_event_types'] and w[0]<=e.get('time_sec',-1)<=w[1]]
            if bad: failures.append('negative_event:'+n['id'])
        if 'must_not_emit_matching' in n:
            m=n['must_not_emit_matching']
            def match(e):
                if not (w[0]<=e.get('time_sec',-1)<=w[1]): return False
                for k,v in m.items():
                    if k=='attributes':
                        if not _subset(v,e.get('attributes',{})): return False
                    elif e.get(k)!=v: return False
                return True
            if any(match(e) for e in events): failures.append('negative_match:'+n['id'])
        if 'must_not_state_match' in n:
            m=n['must_not_state_match']
            if any(_overlap(w,s.get('interval',[-1,-1]))>0 and all(s.get(k)==v for k,v in m.items()) for s in states): failures.append('negative_state:'+n['id'])
        if 'must_not_update_player_fields_to' in n:
            poison=n['must_not_update_player_fields_to']
            for s in snaps:
                if w[0]<=s.get('time_sec',-1)<=w[1] and any(s.get(k)==v for k,v in poison.items()): failures.append('poison:'+n['id']); break
        if 'must_not_match_snapshot_subset' in n:
            poison=n['must_not_match_snapshot_subset']
            for s in snaps:
                if w[0]<=s.get('time_sec',-1)<=w[1] and _subset(poison,s): failures.append('poison_subset:'+n['id']); break
        if 'must_not_span_temporal_features' in n:
            names=set(n['must_not_span_temporal_features'])
            for tf in temporal:
                iv=tf.get('interval',[-1,-1])
                if tf.get('feature') in names and iv[0] <= w[0] and iv[1] >= w[1]: failures.append('discontinuity_span:'+n['id']+':'+tf.get('feature','?'))
    failures.extend(_finite_confidence_failures(output))
    return failures

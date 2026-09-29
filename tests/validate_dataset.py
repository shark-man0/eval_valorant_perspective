import json, sys
from pathlib import Path
from collections import defaultdict
try:
    import jsonschema
except ImportError:
    print("jsonschema が必要です: pip install jsonschema")
    sys.exit(2)
ROOT=Path(__file__).resolve().parents[1]
input_schema=json.load(open(ROOT/'schemas'/'round_package_schema_v2.json',encoding='utf-8'))
assert_schema=json.load(open(ROOT/'schemas'/'test_assertion_schema_v1.json',encoding='utf-8'))
triggers=json.load(open(ROOT/'config'/'rule_trigger_registry_v2.json',encoding='utf-8'))
manifest=json.load(open(Path(__file__).with_name('manifest.json'),encoding='utf-8'))
errors=[]

def f_map(data):
    m=defaultdict(list)
    for f in data.get('deterministic_facts',[]): m[f['key']].append(f['value'])
    return m

def cmp(vals,op,val):
    if not vals: return None
    if op=='eq': return any(x==val for x in vals)
    if op=='neq': return any(x!=val for x in vals)
    if op=='in': return any(x in val for x in vals)
    if op=='gte': return any(isinstance(x,(int,float)) and x>=val for x in vals)
    if op=='lte': return any(isinstance(x,(int,float)) and x<=val for x in vals)
    if op=='gt': return any(isinstance(x,(int,float)) and x>val for x in vals)
    if op=='lt': return any(isinstance(x,(int,float)) and x<val for x in vals)
    if op=='exists': return True
    return False

def candidates(data):
    evtypes={e['type'] for e in data['events']}; fm=f_map(data); out=[]
    for rid,r in triggers['rules'].items():
        if r['trigger_event_types'] and not (evtypes & set(r['trigger_event_types'])): continue
        ok=True
        for p in r.get('required_state_predicates',[]):
            res=cmp(fm.get(p['fact_key'],[]),p['op'],p.get('value'))
            if res is None and p.get('missing_policy','exclude')=='exclude': ok=False; break
            if res is False: ok=False; break
        if ok: out.append(rid)
    return set(out)

for c in manifest['cases']:
    cid=c['id']; base=Path(__file__).with_name('cases')/cid
    data=json.load(open(base/'input.json',encoding='utf-8'))
    ass=json.load(open(base/'expected_assertions.json',encoding='utf-8'))
    try: jsonschema.validate(data,input_schema)
    except Exception as e: errors.append(f"{cid}: input schema: {e.message}")
    try: jsonschema.validate(ass,assert_schema)
    except Exception as e: errors.append(f"{cid}: assertion schema: {e.message}")
    raw=json.dumps(data,ensure_ascii=False).lower()
    for term in ass.get('forbidden_input_conclusion_terms',[]):
        if term.lower() in raw: errors.append(f"{cid}: conclusion leak term: {term}")
    cand=candidates(data)
    for rid in ass.get('expected_candidate_rule_ids',[]):
        if rid not in cand: errors.append(f"{cid}: expected candidate missing: {rid}; got={sorted(cand)}")
    for rid in ass.get('forbidden_candidate_rule_ids',[]):
        if rid in cand: errors.append(f"{cid}: forbidden candidate selected: {rid}")
    for e in ass.get('expected_evaluations',[]):
        if e['primary_rule_id'] not in cand:
            errors.append(f"{cid}: expected evaluation rule is not a candidate: {e['primary_rule_id']}")
if errors:
    print('\n'.join(errors)); sys.exit(1)
print(f"OK: {len(manifest['cases'])} cases; schemas + candidate selection contract valid")

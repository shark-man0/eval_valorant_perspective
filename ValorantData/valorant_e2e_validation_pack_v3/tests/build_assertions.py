from __future__ import annotations
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def load(rel): return json.loads((ROOT/rel).read_text(encoding='utf-8'))
def build():
    gt=load('ground_truth/timeline_ground_truth_v3.json')
    neg=load('ground_truth/negative_assertions_v3.json')
    vocab=load('contracts/event_attribute_vocab_v1.json')
    out={
      'version':'3.0',
      'generated_from':['ground_truth/timeline_ground_truth_v3.json','ground_truth/negative_assertions_v3.json'],
      'required_point_events':[], 'required_state_intervals':[], 'required_ownership_intervals':[],
      'required_snapshots':[], 'required_visual_observations':[], 'derived_assertions':[],
      'event_count_constraints':[], 'ordering_constraints':[], 'negative_assertions':neg['assertions'],
      'discontinuities':gt['known_discontinuities'], 'continuous_segments':gt['continuous_segments'],
      'attribute_vocab':vocab['events']
    }
    for r in gt['rounds']:
        rid=r['round_id']
        for e in r.get('point_events',[]):
            item={'id':e['id'],'round_id':rid,'type':e['type'],'actor':e['actor'],
                  'acceptance_window':[e['evidence_bracket']['last_absent_sec']-e['tolerance_before_sec'],e['evidence_bracket']['first_present_sec']+e['tolerance_after_sec']],
                  'facts':e['facts'],'required_event_attributes':e.get('required_event_attributes',{})}
            out['required_point_events'].append(item)
            for after in e.get('must_precede',[]): out['ordering_constraints'].append({'before':e['id'],'after':after})
        for s in r.get('state_intervals',[]):
            item={'id':s['id'],'round_id':rid,'state_class':s['state_class'],'state':s['state'],'subtype':s['subtype'],
                  'core_interval':s['core_interval'],'outer_interval':s['outer_interval'],'min_core_coverage':s['min_core_coverage'],'exhaustive':s['exhaustive']}
            if 'edge_brackets' in s: item['edge_brackets']=s['edge_brackets']
            out['required_state_intervals'].append(item)
        for s in r.get('ownership_intervals',[]):
            out['required_ownership_intervals'].append({'id':s['id'],'round_id':rid,'owner':s['owner'],'core_interval':s['core_interval'],'outer_interval':s['outer_interval'],'min_core_coverage':0.9})
        for s in r.get('snapshots',[]):
            out['required_snapshots'].append({'id':s['id'],'round_id':rid,'time_sec':s['time_sec'],'tolerance_sec':s['tolerance_sec'],'expected':s['expected']})
            for key,val in s.get('derived_expectations',{}).items():
                out['derived_assertions'].append({'id':s['id']+'-DERIVED-'+key,'round_id':rid,'time_sec':s['time_sec'],'tolerance_sec':s['tolerance_sec'],'field':key,'expected':val['value'],'source_contract':val['source_contract']})
        for v in r.get('visual_observations',[]):
            out['required_visual_observations'].append({'id':v['id'],'round_id':rid,'observation':v['observation'],'actor':v['actor'],'time_sec':v['time_sec'],'tolerance_sec':0.08})
        for c in r['round_package_expectations']['event_count_constraints']:
            x=dict(c); x['round_id']=rid; out['event_count_constraints'].append(x)
    return out
if __name__=='__main__':
    dst=ROOT/'tests/generated/e2e_assertions_v3.json'; dst.parent.mkdir(parents=True,exist_ok=True)
    dst.write_text(json.dumps(build(),ensure_ascii=False,indent=2)+'\n',encoding='utf-8'); print(dst)

from __future__ import annotations
import argparse,hashlib,json,subprocess,sys,math,re
from pathlib import Path
import jsonschema
ROOT=Path(__file__).resolve().parents[1]
def load(rel): return json.loads((ROOT/rel).read_text(encoding='utf-8'))
def run_py(name): subprocess.check_call([sys.executable,str(ROOT/'tests'/name)])

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--source-video'); ap.add_argument('--project-root'); args=ap.parse_args()
    gt=load('ground_truth/timeline_ground_truth_v3.json'); neg=load('ground_truth/negative_assertions_v3.json'); inp=load('inputs/e2e_inputs_v3.json'); profile=load('ground_truth/source_video_profile_v3.json'); sync=load('ground_truth/sync_anchors_v3.json'); side=load('ground_truth/frame_pts_sidecar_v3.json')
    jsonschema.validate(gt,load('schemas/e2e_ground_truth_schema_v3.json')); jsonschema.validate(neg,load('schemas/negative_assertions_schema_v3.json')); jsonschema.validate(inp,load('schemas/e2e_inputs_schema_v3.json'))
    dur=profile['duration_sec']; ids=set(); disc=gt['known_discontinuities']
    for r in gt['rounds']:
        for group in ('point_events','state_intervals','ownership_intervals','snapshots','visual_observations'):
            for x in r.get(group,[]):
                assert x['id'] not in ids,x['id']; ids.add(x['id'])
                for p in x.get('evidence',[]): assert (ROOT/p).exists(),p
        for e in r['point_events']:
            b=e['evidence_bracket']; assert 0<=b['last_absent_sec']<=b['first_present_sec']<=dur
            for d in disc:
                assert not (b['last_absent_sec']<d['last_pre_jump_sec'] and b['first_present_sec']>d['first_post_jump_sec']),f"point bracket crosses discontinuity: {e['id']}"
        for s in r['state_intervals']:
            c,o=s['core_interval'],s['outer_interval']; assert 0<=o[0]<=c[0]<=c[1]<=o[1]<=dur
            if 'edge_brackets' in s:
                eb=s['edge_brackets']; st,en=eb['start'],eb['end']
                assert o[0]<=st['last_absent_sec']<=st['first_present_sec']<=c[0]+1e-9,(s['id'],'start')
                assert c[1]-1e-9<=en['last_present_sec']<=en['first_absent_sec']<=o[1]+1e-9,(s['id'],'end')
        for s in r.get('ownership_intervals',[]):
            c,o=s['core_interval'],s['outer_interval']; assert 0<=o[0]<=c[0]<=c[1]<=o[1]<=dur
        for s in r['snapshots']: assert 0<=s['time_sec']<=dur
    for d in disc:
        assert d['last_pre_jump_sec']<d['first_post_jump_sec']
        for p in d['evidence']: assert (ROOT/p).exists(),p
    # Continuous segments must not bridge a discontinuity.
    for seg in gt['continuous_segments']:
        a,b=seg['interval']; assert 0<=a<b<=dur
        for d in disc: assert not (a<d['last_pre_jump_sec'] and b>d['first_post_jump_sec']),('segment crosses discontinuity',seg['id'])
    for a in sync['anchors']: assert 0<=a['time_sec']<=dur and (ROOT/a['evidence']).exists(),a
    # Every reference frame must have an exact PTS sidecar entry within one frame.
    refs=sorted(str(p.relative_to(ROOT)).replace('\\','/') for p in (ROOT/'assets/reference_frames').glob('*.jpg'))
    entries={x['evidence_path']:x for x in side['entries']}; assert set(refs)==set(entries),(len(refs),len(entries))
    assert side['max_abs_delta_sec']<=1/60+1e-6,side['max_abs_delta_sec']
    for x in entries.values(): assert abs(x['delta_sec'])<=1/60+1e-6
    # Assertions are generated, never hand-maintained.
    sys.path.insert(0,str(ROOT/'tests')); import build_assertions
    generated=build_assertions.build(); checked=load('tests/generated/e2e_assertions_v3.json'); assert generated==checked,'generated assertions drifted from canonical GT'
    # Integration overlay evidence.
    overlay=load('integration_overrides/map_zone_v3/summit_observed_ja_alias_overlay_v1.json')
    for rec in overlay['records']: assert (ROOT/rec['evidence']).exists(),rec
    # Stable source vocabulary covers tokens used in negatives.
    vocab=load('contracts/event_attribute_vocab_v1.json')['events']['enemy_spotted']['source_enum']; assert 'world_view' in vocab
    # Run synthetic contract tests.
    for name in ('test_shot_granularity_contract.py','test_map_zone_synthetic.py','test_continuous_combat_contract.py','test_map_alias_overlay.py','test_meta_evaluator.py'): run_py(name)
    if args.source_video:
        p=Path(args.source_video); h=hashlib.sha256(p.read_bytes()).hexdigest(); assert h==profile['sha256'],(h,profile['sha256'])
        pr=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=start_time,duration:stream=index,codec_type,codec_name,start_time,duration,avg_frame_rate,time_base,channels','-of','json',str(p)],text=True))
        assert abs(float(pr['format']['duration'])-dur)<0.002
        vs=[s for s in pr['streams'] if s['codec_type']=='video'][0]; assert abs(float(vs['start_time'])-profile['video_stream']['start_time_sec'])<0.002
        aud=[s for s in pr['streams'] if s['codec_type']=='audio']; assert len(aud)==profile['audio_streams']['count']; assert all(s['codec_name']==profile['audio_streams']['codec'] for s in aud)
        # Rebuild exact packet-PTS mapping and compare byte-level data structure semantics.
        out=subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-show_packets','-show_entries','packet=pts_time','-of','csv=p=0',str(p)],text=True)
        pts=sorted({float(x.split(',')[0]) for x in out.splitlines() if x.strip()})
        for x in side['entries']:
            near=min(pts,key=lambda t:abs(t-x['requested_sec']))
            assert abs(near-x['decoded_frame_pts_sec'])<1e-6,(x['evidence_path'],near,x['decoded_frame_pts_sec'])
        subprocess.check_call([sys.executable,str(ROOT/'tests/validate_media_transport.py'),'--source-video',str(p)])
    if args.project_root:
        root=Path(args.project_root)
        forbidden=('ground_truth','timeline_ground_truth_v3','e2e_assertions_v3.json',profile['sha256'],'frame_pts_sidecar_v3')
        hits=[]
        for p in root.rglob('*.py'):
            if 'tests' in p.parts: continue
            txt=p.read_text(encoding='utf-8',errors='ignore')
            if any(x in txt for x in forbidden): hits.append(str(p))
        assert not hits,'possible GT leakage in production code: '+repr(hits)
    print('e2e validation pack v3: OK')
    print('rounds:',len(gt['rounds']))
    print('point events:',sum(len(r['point_events']) for r in gt['rounds']))
    print('state intervals:',sum(len(r['state_intervals']) for r in gt['rounds']))
    print('ownership intervals:',sum(len(r.get('ownership_intervals',[])) for r in gt['rounds']))
    print('snapshots:',sum(len(r['snapshots']) for r in gt['rounds']))
    print('visual observations:',sum(len(r.get('visual_observations',[])) for r in gt['rounds']))
    print('negative assertions:',len(neg['assertions']))
    print('reference frames with exact PTS:',len(side['entries']))
    print('known discontinuities:',len(disc))
if __name__=='__main__': main()

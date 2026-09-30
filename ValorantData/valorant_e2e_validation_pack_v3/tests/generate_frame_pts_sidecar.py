from __future__ import annotations
import argparse,json,re,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
PAT=re.compile(r'_(\d+\.\d+)s\.jpg$')
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--source-video',required=True); ap.add_argument('--write',action='store_true'); args=ap.parse_args()
    out=subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-show_packets','-show_entries','packet=pts_time','-of','csv=p=0',args.source_video],text=True)
    pts=sorted({float(x.split(',')[0]) for x in out.splitlines() if x.strip()})
    entries=[]
    for p in sorted((ROOT/'assets/reference_frames').glob('*.jpg')):
        m=PAT.search(p.name)
        if not m: continue
        req=float(m.group(1)); near=min(pts,key=lambda x:abs(x-req)); idx=pts.index(near)
        entries.append({'evidence_path':str(p.relative_to(ROOT)).replace('\\','/'),'requested_sec':req,'decoded_frame_pts_sec':round(near,6),'presentation_index':idx,'delta_sec':round(near-req,6)})
    obj={'version':'3.0','timebase':'container_pts_seconds','method':'nearest exact video packet PTS from ffprobe -show_packets; presentation-sorted','source_video':Path(args.source_video).name,'frame_count_indexed':len(entries),'max_abs_delta_sec':round(max(abs(e['delta_sec']) for e in entries),6),'entries':entries}
    if args.write: (ROOT/'ground_truth/frame_pts_sidecar_v3.json').write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n')
    else: print(json.dumps(obj,ensure_ascii=False,indent=2))
if __name__=='__main__': main()

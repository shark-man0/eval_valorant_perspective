from __future__ import annotations
import argparse,json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
C=json.loads((ROOT/'contracts/audio_transport_contract_v1.json').read_text())
def streams(path):
    x=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_entries','stream=index,codec_type,codec_name,channels','-of','json',str(path)],text=True))
    return x['streams']
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--source-video',required=True); ap.add_argument('--generated-clip'); args=ap.parse_args()
    a=[s for s in streams(args.source_video) if s['codec_type']=='audio']
    assert len(a)==C['source']['audio_stream_count']; assert all(s['codec_name']==C['source']['codec'] for s in a); assert all(s.get('channels')==C['source']['channels_each'] for s in a)
    if args.generated_clip:
        b=[s for s in streams(args.generated_clip) if s['codec_type']=='audio']
        if C['mvp']['generated_clip_preserve_all_tracks']: assert len(b)==len(a),(len(b),len(a))
    print('media transport: OK; source audio tracks=',len(a),'clip_checked=',bool(args.generated_clip))
if __name__=='__main__': main()

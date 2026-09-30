from __future__ import annotations
"""Advisory confidence audit. One fixture is too small for pass/fail calibration."""
import argparse,json,math
from pathlib import Path

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--trace',required=True); args=ap.parse_args()
    d=json.loads(Path(args.trace).read_text())
    vals=[]
    for group in ('events','state_intervals','ownership_intervals','snapshots','visual_observations'):
        for x in d.get(group,[]):
            for k,v in x.items():
                if k=='confidence' or k.endswith('_confidence'):
                    if isinstance(v,(int,float)) and not isinstance(v,bool): vals.append(float(v))
    bad=[v for v in vals if not math.isfinite(v) or not 0<=v<=1]
    assert not bad,bad
    print(json.dumps({'confidence_values':len(vals),'min':min(vals) if vals else None,'max':max(vals) if vals else None,'statistical_calibration':'NOT_ASSESSED: requires multi-fixture labeled corpus'},indent=2))
if __name__=='__main__': main()

from __future__ import annotations
import argparse,json,sys
from pathlib import Path
import jsonschema
from reference_evaluator import evaluate
ROOT=Path(__file__).resolve().parents[1]
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--trace',required=True); args=ap.parse_args()
    trace=json.loads(Path(args.trace).read_text(encoding='utf-8'))
    schema=json.loads((ROOT/'schemas/e2e_output_trace_schema_v1.json').read_text(encoding='utf-8'))
    jsonschema.validate(trace,schema)
    assertions=json.loads((ROOT/'tests/generated/e2e_assertions_v3.json').read_text(encoding='utf-8'))
    failures=evaluate(assertions,trace)
    if failures:
        print(json.dumps({'pass':False,'failure_count':len(failures),'failures':failures},ensure_ascii=False,indent=2)); sys.exit(1)
    print(json.dumps({'pass':True,'failure_count':0},indent=2))
if __name__=='__main__': main()

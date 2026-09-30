from __future__ import annotations
import json,unicodedata,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
D=json.loads((ROOT/'integration_overrides/map_zone_v3/summit_observed_ja_alias_overlay_v1.json').read_text())
def norm(s): return re.sub(r'\s+',' ',unicodedata.normalize('NFKC',s).strip())
seen=set()
for r in D['records']:
    k=norm(r['raw_label']); assert k not in seen,k; seen.add(k); assert (ROOT/r['evidence']).exists(); assert r['zone_id'].startswith('summit_')
assert {'A ロビー','中央ファウンテン','Bメイン'} <= {r['raw_label'] for r in D['records']}
print('map alias overlay: OK',len(D['records']))

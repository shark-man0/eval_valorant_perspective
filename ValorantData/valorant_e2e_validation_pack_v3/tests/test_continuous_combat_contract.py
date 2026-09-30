from __future__ import annotations
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
D=json.loads((ROOT/'fixtures/continuous_combat_contract_v1.json').read_text())
by={x['type']:x for x in D['timeline']}
reaction=by['shot']['t']-by['enemy_spotted']['t']
duration=by['engagement_end']['t']-by['engagement_start']['t']
assert abs(reaction-D['expected_metrics']['enemy_info_to_first_shot_sec'])<1e-9
assert abs(duration-D['expected_metrics']['engagement_duration_sec'])<1e-9
assert not D['discontinuities']
print('continuous combat synthetic consumer contract: OK')

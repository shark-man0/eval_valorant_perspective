"""Compare private replay files; emit only publishable aggregate differences."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from fixed_replay_comparison import compare_adaptive_sampling, compare_replays


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('baseline', type=Path)
    parser.add_argument('current', type=Path)
    parser.add_argument('--lane', choices=('fixed', 'adaptive'), default='fixed')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    baseline = json.loads(args.baseline.read_text(encoding='utf-8'))
    current = json.loads(args.current.read_text(encoding='utf-8'))
    compare = compare_replays if args.lane == 'fixed' else compare_adaptive_sampling
    result = compare(baseline, current)
    with args.output.open('x', encoding='utf-8') as handle:
        json.dump(result, handle, indent=2, sort_keys=True, allow_nan=False)
    print(json.dumps(result, sort_keys=True, allow_nan=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

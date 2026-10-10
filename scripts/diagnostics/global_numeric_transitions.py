"""Describe global numeric transitions; never classify or emit round events."""
from __future__ import annotations

import argparse
import hashlib
import json
from fractions import Fraction
from pathlib import Path

from valorant_ai_coach.hud.global_lifecycle import _display, _score, _timer
from valorant_ai_coach.hud.round_lifecycle import MAX_SAMPLE_GAP_SEC, MIN_START_CONFIRMATION_SEC


def describe(rows, time_base: Fraction, step: int):
    if not rows or time_base <= 0 or type(step) is not int or step <= 0:
        raise ValueError('nonempty native rows and positive timebase/cadence required')
    plateaus, clock_changes = [], []
    previous_clock = None
    current_plateau = None
    epoch = rows[0].get('source_epoch')
    epoch_present = any('source_epoch' in row for row in rows)
    for index, row in enumerate(rows):
        tick = row['source_pts_ticks']
        if (type(tick) is not int or tick < 0
                or float(tick * time_base) != row['pts_sec']
                or (index and tick - rows[index - 1]['source_pts_ticks'] != step)):
            raise ValueError('native PTS/cadence mismatch')
        observation = row['observation']
        if epoch_present and (
            not isinstance(epoch, str) or not epoch
            or row.get('source_epoch') != epoch
            or row.get('source_time_base') != str(time_base)
        ):
            raise ValueError('native source epoch/timebase mismatch')
        if (index and row.get('source_pixel_sha256') is not None
                and row['source_pixel_sha256'] == rows[index - 1].get('source_pixel_sha256')):
            raise ValueError('repeated source pixels cannot corroborate a transition')
        if observation['time_sec'] != row['pts_sec']:
            raise ValueError('observation/source PTS mismatch')
        values = observation['values']
        confidence = observation['quality']['roi_confidence']
        scores = [values.get(k) for k in ('score_ally', 'score_enemy')]
        quality = [_score(confidence.get(k)) for k in ('score_ally_value', 'score_enemy_value')]
        if all(type(n) is int and n >= 0 for n in scores) and all(quality):
            if current_plateau is None or current_plateau['values'] != scores:
                current_plateau = {'values': scores, 'first_tick': tick, 'last_tick': tick,
                                   'count': 0, 'confidence': 1.0, 'minimum_duration_tick': None}
                plateaus.append(current_plateau)
            current_plateau.update(last_tick=tick, count=current_plateau['count'] + 1,
                                   confidence=min(current_plateau['confidence'], *quality))
            if (current_plateau['minimum_duration_tick'] is None and
                    (tick - current_plateau['first_tick']) * time_base >=
                    Fraction(str(MIN_START_CONFIRMATION_SEC))):
                current_plateau['minimum_duration_tick'] = tick
        else:
            current_plateau = None  # Never carry a score plateau through an abstention.
        timer, timer_quality = _timer(observation)
        display = _display(observation)
        if timer is None or not timer_quality or display is None:
            continue  # Missing observations stay missing, never become repeated clocks.
        current = {'tick': tick, 'seconds': timer,
                   'display': values['round_time_remaining_display']}
        if previous_clock is not None:
            elapsed = float((tick - previous_clock['tick']) * time_base)
            decrease = previous_clock['seconds'] - timer
            if elapsed <= MAX_SAMPLE_GAP_SEC and (decrease < 0 or decrease > elapsed + 1):
                clock_changes.append({'before': previous_clock, 'after': current,
                                      'elapsed_sec': elapsed, 'observed_decrease': decrease})
        previous_clock = current
    hypotheses = []
    for change in clock_changes:
        if change['observed_decrease'] <= 0:
            continue
        tick = change['after']['tick']
        for before, after in zip(plateaus, plateaus[1:], strict=False):
            deltas = [b - a for a, b in zip(before['values'], after['values'], strict=True)]
            if (before['first_tick'] <= tick <= before['last_tick']
                    and after['first_tick'] - before['last_tick'] == step
                    and sorted(deltas) == [0, 1]
                    and after['minimum_duration_tick'] is not None
                    and 0 < (after['first_tick'] - tick) * time_base <= MAX_SAMPLE_GAP_SEC):
                hypotheses.append({'clock_change_tick': tick,
                                   'score_change_tick': after['first_tick'],
                                   'score_stability_tick': after['minimum_duration_tick'],
                                   'scope': 'Conditional numeric pattern; active round and '
                                            'safe end semantics are unproved.'})
    return {'clock_changes': clock_changes, 'score_plateaus': plateaus,
            'conditional_patterns': hypotheses, 'released_events': 0,
            'qualification_created': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--time-base', type=Fraction, required=True)
    parser.add_argument('--native-step-ticks', type=int, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('new output required')
    content = args.report.read_bytes()
    report = json.loads(content)
    result = describe(report['rows'], args.time_base, args.native_step_ticks)
    if args.report.read_bytes() != content:
        raise ValueError('input report changed during diagnostic')
    result.update(scope=__doc__, source_video_sha256=report['source_video_sha256'],
                  input_report=str(args.report), input_sha256=hashlib.sha256(content).hexdigest(),
                  diagnostic_script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  time_base=str(args.time_base), canonical_current=None, canonical_delta=None)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'conditional_patterns': len(result['conditional_patterns']),
                      'released_events': 0}))


if __name__ == '__main__':
    main()

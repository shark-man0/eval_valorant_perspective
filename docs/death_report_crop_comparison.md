# Report field crop and semantic contract: rejected static widening

## Problem and targets

The previous optional report candidate correctly read six later R2 frames,
but all positives displayed 194 in one death context. This follow-up targets
the report attribute dependency of `GT-R1-DEATH`, `GT-R2-DEATH`, related
self-dead ownership and event-count assertions. It neither modifies GT nor
claims their prerequisites are satisfied.

Analysis HEAD: `3f88b1a6120114643e71f72b247eb860e9b8416d`.
No production source, default profile or recognition policy is changed.

## Evidence and root cause

Three fixed source offsets 0.2/0.7/1.2 seconds were acquired with exact native
PTS and hash verification before reader execution. Manual pre-prediction review
shows report damage_received 190 in the first two images, and no report in the
third. The unchanged common analyzer recognizes report visibility but returns
unknown for both numbers and rejects the absent report.

A transparent wrapper delegates to the unchanged field reader and records the
actual 65x33 crops and rejection sources. All actual attempts reject with
`numeric_reader_below_configured_confidence`. The actual crop exactly equals
source rectangle [1832,526,1897,559]. The three visible digit components run
from y=544 through y=565 inclusive (22 pixels). The crop ends before y=559,
clipping seven bottom rows. A diagnostic white threshold of 200 identifies
109/124 omitted bright pixels in the two source images. This threshold is
only an image measurement, never an OCR/production acceptance condition.

The context also separates **agent** from **player name**. The header says
`自分を倒した敵 レイズ`, while the red band shows player name `シャバーニ`.
The earlier R2 red-band name `フェイド` coincides with its agent, which obscured
this distinction. The existing agent OCR development crop covers that red band;
it cannot be used as an agent-name contract merely by normalizing whitespace.
Header/portrait agent evidence and player-name evidence must stay separate.
No production killer_agent is currently created from that crop.

## Change and training

A private diagnostic profile increases only the damage field bottom from
normalized 0.578 to 0.608 (source y559 to y574), retaining original x/top,
minimum confidence 0.90, all OCR/runtime settings and all other profile fields.
There is no value-conditioned crop or GT input. These bounds are diagnosed
from the actual truncated glyph extent, not selected against evaluator values.

Development training uses three physical R1 images (including the calibration
prefix) and three prior R2 development images: all six read correctly (190 or
194). The R1 diagnosis images are now development inputs and are **not**
relabeled holdout. This success alone does not authorize adoption.

## Prospective holdout and tests

Before predictions, a new fixed set selected the first native frame at/after
0.3/0.45/0.6, 150/152/156 and 1.4/128/142 seconds. Source review before both
reader executions labels three 190s, three 194s and three naturally absent
reports. All nine images are retained. Six training, six positive holdout and
three negative physical pixel populations are mutually disjoint.
Both common analyzers receive identical PTS-ordered frames and the same source
calibration prefix. There is no geometry, phase or OCR result injection.
Selection/labels, source, runtime, profile and code hashes are verified at exit.

| Metric | Previous crop | Full-glyph crop | Delta |
| --- | ---: | ---: | ---: |
| Holdout correct | 3 | 5 | +2 |
| Holdout unknown | 3 | 1 | -2 |
| Holdout wrong | 0 | 0 | 0 |
| Natural negative rejects | 3 | 3 | 0 |
| Negative false accepts | 0 | 0 | 0 |
| unknown → correct | — | 3 | R1 positives |
| correct → unknown | — | 1 | R2 at 152.002669 sec |
| correct → wrong / unknown → wrong | — | 0 / 0 | No new wrong value |
| Formal events | 0 | 0 | 0 |
| Report readings with valid player HUD | 0 | 0 | 0 |
| Existing valid player HUD observations | 1 | 1 | 0 |
| Processed inputs incl. calibration | 10 | 10 | 0 |
| Analyzer seconds | 16.685 | 16.772 | +0.087 (+0.52%) |
| Canonical PASS / FAIL / NE | 23 / 55 / 4 | not rerun | unavailable |

The one valid-player observation is a report-absent live control, not a new
owned report or self-death. All report-positive observations retain unknown
primary state and invalid player-specific HUD. Model/schema roundtrips pass.
These point sets do not qualify temporal continuity or death attribution.
No code change means no new unit suite is needed; HEAD's previous Linux/Windows
CI remains the latest code regression evidence, not an independent accuracy test.

## Conclusion and remaining blockers

**Reject the static widening profile.** Its improved total count hides the
previously correct R2 value becoming unknown. Do not compensate with threshold
relaxation, per-value special cases or forcing the rejected value from neighbors.
No default profile, production behavior or current observation cache changes.
No sampled/full E2E is warranted for this rejected candidate.

The next report task is value-invariant local structure-based field placement,
with independently qualified header/portrait semantics and separate player-name
extraction. Global HUD geometry is not established as the cause: the analyzer
crop is exactly the configured rectangle and current report visibility works.
P1 Strict lifecycle qualification and P2 current self-dead ownership remain
separate gates; no 82-assertion statuses or canonical safety results are changed.

Machine-readable evidence: `e2e_reports/match_001/death_report_crop_comparison.json`.
Private native images/profile/reproduction scripts remain under ignored outputs.

# Frozen report candidate: prospective source holdout

## Problem and target

P2 death depends on victim/agent/report attributes and current source ownership,
as well as P1 Strict round association. The optional report producer previously
had only eight development inputs (six displayed numbers and two absent reports).
This check targets the damage_received source observation underlying
`GT-R2-DEATH`, `OWN-R2-SELF-DEAD` and `event_count_constraints-005`. It does not
claim those predicates are satisfied or that the 29 package failures are fixed.

## Evidence and independence

Start/analysis HEAD: `3f88b1a6120114643e71f72b247eb860e9b8416d`.
The original video SHA-256 is
`71d58558559d6f578433ce9f234bf176f76fd5a86657dbfe3eba1e7d36136b06`.
The unchanged optional report profile was frozen before frame acquisition.
No Validation Pack expected values were supplied to the analyzer or selection.

Six fixed offsets (148.2, 148.7, 149.2, 151, 154, 160 seconds) selected the first
actual native frame at/after each offset. All six were retained. A separate fixed
control set (130, 140, 146 seconds) was also retained regardless of display.
The source images were decoded using the common verified native decoder and
reviewed manually **before** the report reader was executed on any of them.
All six positive images visibly show received damage `194` and given damage `0`;
the three controls visibly show the game background with no report panel.
Only damage_received is configured in this frozen profile.

File/pixel SHA-256, native PTS, timebase, profile/code fingerprints, selection
and pre-prediction labels are recorded. All nine physical pixel hashes are
mutually distinct and disjoint from the eight development images. Earlier
whole-video HUD/global runs existed, so independence is specifically from the
new frozen damage_received reader; these are **not** new global lifecycle
holdout cases. The calibration prefix is not counted as holdout support.

## Change and tests

Production, profile, thresholds, ownership, confidence, events, GT, assertion
semantics and sampler are unchanged. Existing common RealHudAnalyzer processes
one exact-source calibration prefix plus the nine source samples in PTS order.
The actual observation/model/schema checks are exercised, not injected geometry,
phase flags or reader outputs. Input hashes and source SHA-256 are rechecked at
termination. This isolated point set does not test temporal continuity.

| Metric | Previous prospective check | Current | Delta |
| --- | ---: | ---: | ---: |
| Frozen candidate positive holdout cases | 0 | 6 | +6 |
| Correct / unknown / wrong | unmeasured | 6 / 0 / 0 | unavailable |
| Natural absence controls | 0 | 3 | +3 |
| Negative rejects / false accepts | unmeasured | 3 / 0 | unavailable |
| Player-owned observations | 0 | 0 | 0 |
| Formal HUD events | 0 | 0 | 0 |
| Complete qualification created | 0 | 0 | 0 |
| Canonical PASS / FAIL / NE | 23 / 55 / 4 | not rerun | unavailable |

Eight target observations remain primary_state unknown; the last positive
frame (160.002669 sec) is spectator_first_person. All nine retain
player_specific_hud_valid false. The personal report remains visible through
a camera-context change: its stored numbers cannot inherit current-camera
ownership or be treated as new death events at every positive frame. Model and persisted observation validation
pass. The analyzer takes **17.996 seconds** for ten inputs. Separate native
acquisition takes about 113 seconds; this is not an E2E speed comparison.
The latest HEAD's Linux/Windows CI passed both push and PR runs before this
document-only source check. No new full/sampled canonical E2E is justified by
an unqualified candidate. Canonical negative/discontinuity assertions were not
re-evaluated; their historical zero failures are not new measurements.

## Conclusion and remaining blockers

The unchanged source report candidate generalizes to these later frames and
rejects these natural missing-report controls. It cannot yet be adopted as a
qualified damage fact: all positives share one value and one death episode.
Victim-name semantics, killer-agent semantics, broader controls, current source
self-dead ownership and Strict round association remain required. No actual
canonical PASS gain or confidence increase follows from storing a candidate.

P1 global qualification remains the highest impact gate. Its already exposed
R1/R2 development episodes cannot be relabeled independent holdout. P2 can
continue on separately frozen source semantics without creating a new timer,
score, HP or spectator candidate, or applying the global identity-independent
lifecycle route to player-owned damage/death.

Machine report: `e2e_reports/match_001/death_report_prospective_holdout.json`.
Private reproduction artifacts: `outputs/recognition-investigation/death-report-holdout-20261012`
(selection, acquisition, pre-prediction labels and frozen-reader evaluation).
No images or OCR runtime assets are shared through Git.

# Current source evidence for the death producer gap

## Problem

P1 Practical partitioning preserves observations, but it does not satisfy Strict
round qualification. P2 death assertions additionally require a qualified
producer of death semantics. Target assertions are `GT-R2-DEATH`,
`OWN-R2-SELF-DEAD` and `event_count_constraints-005`. This investigation changes
neither their definitions nor production behavior.

## Evidence

At commit `6f7cce4aba02a7d74249594e7a71c71ee69b47b0`, FFmpeg decoded all 27
native frames in the explicit 147.60–148.04 second source window. Integer PTS
uses time base 1/15360 and every adjacent tick increases by 256. Every decoded
pixel hash matches the completed whole-native archive. The source-video SHA
was checked before and after analysis. Eight frames were visually reviewed;
27 decoded frames must not be reported as 27 independently reviewed positives.

The frame at 147.669336 has no combat report and visibly shows HP 22. At the
next native frame, 147.686003, the report appears with killer-agent text
`フェイド` and received-damage display `194`. The killfeed entrance animation is
still incomplete. At 147.736003, its victim text `sharkman` is readable as well.
The later reviewed images retain both fields and show the falling death
animation. These are source observations, not a runtime injection of the
assertion's expected values. They are post-prediction development evidence,
not an independent holdout or new validation ground truth.

The left-hand notification says a teammate is communicating while dead. That
notification does not establish the owner of the camera view and must not be
promoted to a spectator identity or spectated-player name.

## Root cause

The archived common application has 11 sampled observations in this native
window. They remain `unknown` with HUD confidence 0 and
`player_specific_hud_valid=False`. 8 of these observations retain
`combat_report_visible=True`, starting at 147.719336. All retain an empty
killfeed-row list. Thus the report's existence reaches production observations;
qualified semantics and player attribution do not.

`HudDirectEventBuilder._player_death_event` requires report presence plus a
second death source, and confidence from `death_source_confidence`.
The normal image producer does not generate that confidence, roster-self-dead
proof, or the three required semantic fields. Its existing event attributes
contain only `cause_known`. The analyzer's spectator-transition flag alone
cannot repair these missing proofs and must not justify a self death.

## Hypothesis and next implementation

Build a source-bound semantic death observation from independently qualified
report/killfeed readers, preserving each accepted field's original display,
ROI, source PTS, confidence and reader/profile fingerprint. Keep report
presence, semantic field acceptance and player ownership separate. A report
that persists after respawn is not a new death; another player's killfeed row
is not proof of self death. Do not loosen identity/ownership to turn these
unknown observations into a player event.

Before introducing that reader, inventory existing training assets and choose
training/holdout/negative cases explicitly. These 27 images are development
inputs and cannot later be relabeled independent holdout. R1's separate report
may help investigate transfer, but one additional correlated episode is not
proof of broad negative-control coverage. The implementation must also carry
accepted semantic fields through native events, Package and trace; changing
only the adapter would invent missing producer facts.

## Tests

The read-only verifier completed successfully: source SHA at both endpoints,
27/27 archive pixel matches, uninterrupted native PTS, encoded PNG hashes and
terminal hashes for raw observations, native archive and inspected source
files. No new recognizer or production code was introduced. No additional
full E2E was run for this diagnostic. Existing production CI results do not
qualify the manually observed death semantics.

## Previous / Current / Delta

| Metric | Previous | Current | Delta |
| --- | ---: | ---: | ---: |
| Formal HUD player-death events | 0 | 0 | 0 |
| Canonical PASS | 23 | Not re-evaluated | — |
| Canonical FAIL | 55 | Not re-evaluated | — |
| Canonical NE | 4 | Not re-evaluated | — |
| Native source images verified in this diagnostic | Not measured | 27 | — |
| Independently qualified death-semantic readers | 0 | 0 | 0 |

## Conclusion and remaining blockers

The R2 source exposes the required semantic information. The next task is a
qualified source producer and its ownership/event contract, not lowering a
report-detection threshold or copying the expected attributes into an event.
No additional canonical PASS is proven. Round association, Strict lifecycle
qualification, independent negative/temporal testing and safe self ownership
remain prerequisites. This bounded finding does not reclassify all 29 historic
round-package failures as solved.

Machine-readable evidence: `e2e_reports/match_001/death_current_source_gap.json`.
Raw PNG images remain Pi-local under
`outputs/recognition-investigation/death-current-source-20261012`.


## Source-preserving producer follow-up

The common analyzer now supports optional, unqualified report numeric readings
using the existing fields reader. Real source verification retains six correct
displays and rejects two absent fields without any player ownership or death
event. Victim/agent semantics and qualification remain incomplete. See
[source-preserved readings and regression evidence](death_report_readings.md).

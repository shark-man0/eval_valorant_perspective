# Evidence continuity in the shared development timeline

`--evidence-continuity` (API: `DevelopmentGameTimeline(evidence_continuity=True)`)
adds an offline revision pass to the existing shared state owner. It is not a
second state machine: it revises the rows that `DevelopmentGameTimeline.rebuild`
already produced, keeps the previous estimate under `rule_estimate`, cites the
native observations it used and records every change in
`evidence_continuity_projection_history`. The default path is unchanged.
Formal Facts/Events, qualification and recorder ownership are unchanged.

Related: #121, #124, #138. Code: `src/valorant_ai_coach/temporal/evidence_continuity.py`.

## Rules

Every rule combines measured displays with a game invariant that excludes the
alternatives. Missing frames, decode breaks, conflicting readings, unexplained
gaps and short unverified carries stop a revision. There are no Source, time or
match specific conditions and no threshold changes in any recognizer.

| Rule | Measured inputs | Invariant | Revision |
| --- | --- | --- | --- |
| Same-score phase bracket | Two measured BUY/ACTIVE/ENDED anchors of the same phase, equal score readings around and inside | The displayed score changes exactly when a Round is decided and never decreases | Unobserved rows between take the anchor phase |
| ACTIVE until the score changes | ACTIVE anchor, later frames still showing its score | Same as above | Rows before the last old-score frame are ACTIVE; that frame stays unrevised |
| ENDED after the score changed | One-point increment, later ENDED anchor with the new score | Same as above | Rows from the first new-score frame to the anchor are ENDED |
| Round end candidate | ACTIVE anchor, last old-score frame, first new-score frame | One increment is one decided Round | `round_end` bracket between those frames |
| Round start candidate | BUY or ENDED anchor, later ACTIVE anchor, equal score | A new Round starts only after its purchase phase | `round_start` bracket; two consistent ACTIVE countdown readings narrow it to the frame before the projected 1:40 display |
| Spectating during a Round | Measured spectator panel, or the combat report, learned spectator view and the recorder's alias in the elimination display together; no owner HUD, remote, revival or purchase cue; Round ACTIVE/ENDED | Living players do not spectate | Life `DEAD` (alternative `DOWNED`) |
| Dead bracket | Two such DEAD anchors, unchanged score, no owner HUD, revival or purchase cue between | No respawn inside a Round without revival | Rows between are DEAD |
| Not alive, not first person | DEAD without an open alternative, no owner HUD/remote/revival cue | A recorder that is not alive cannot hold the first-person view | Camera `SPECTATOR` |
| Purchase phase | BUY Round state (measured or same-score bracket), no spectator/remote/death cue | All players are alive in the purchase phase | Unknown life becomes ALIVE |
| Respawn after a new Round | Score higher than at the last measured death, current owner HUD, no death/spectator/report cue | A new Round respawns every player | Life ALIVE |
| Stale death hypothesis | An open (`UNKNOWN`-alternative) death hypothesis still latched after the score increased | A death hypothesis cannot outlive its Round | Withdrawn to UNKNOWN, or ALIVE with a current owner HUD |

Added events carry `single_boundary_interval` (the anchor pair that can contain
only that boundary). An event is added only if no existing candidate of the same
kind overlaps that interval, so existing candidates are never duplicated.
`reconcile_visual_transitions` then archives edges made stale by the revisions in
`superseded_transition_candidates`.

## Running

```bash
python -m valorant_ai_coach.temporal.application generate ... --practical-visual-state --evidence-continuity
python -m valorant_ai_coach.temporal.application export ... --evidence-continuity
```

`export` restores the flag from the stored engine configuration. The flag is
recorded in a new acquisition checkpoint binding only when it is enabled, so
existing checkpoints remain compatible. It requires offline mode; it is rejected
with `forward_only=True`.

## Validation (2026-11-15)

Inputs: the same previously acquired native observations of the ten admitted
DEVELOPMENT matches used for the #145 integration replay. The replay harness
reproduced the integration baseline exactly before any change: 21,999 rows and
UNKNOWN Round 7,230 / Life 5,322 / Camera 4,118 seconds.

| Measure | Before | After |
| --- | ---: | ---: |
| Round UNKNOWN seconds | 7,230 | 3,852 |
| Life UNKNOWN seconds | 5,322 | 3,038 |
| Camera UNKNOWN seconds | 4,118 | 4,012 |
| Seconds changed between two known values | – | 0 |
| Life seconds withdrawn from a stale DEAD to UNKNOWN | – | 1,010 |
| Rounds with a start candidate (229 Rounds read from final screens) | 167 | 221 |
| Rounds with an end candidate (plus 5 final-Round ends after the last score display) | 197 | 220 |
| Duplicate start/end candidates for one Round | 0 / 0 | 0 / 0 |
| Start / end bracket width p90 (s) | 3 / 2 | 5 / 2 |
| Reconstructed exact-frame labels: correct / incorrect / abstained | 61 / 0 / 2 | 62 / 0 / 1 |
| Supplemental 9 and 6 attributes | 9/9, 6/6 | 9/9, 6/6 |
| Formal Facts/Events | 0 | 0 |

Rounds per match were read from the original recordings' final screens or, where
the recording ends in the last Round, from its last displayed score. The
reconstructed label set is the union of every accessible exact-frame label file,
deduplicated by physical native frame (63 observed attributes, 14 NOT_OBSERVED).

Original-video spot checks (frames decoded at the exact native PTS, reviewed
visually by the implementing agent; not human GT):

- 63 revised frames, 7 per rule: 61 consistent, 0 contradicted, 2 not decidable
  from the image (menu overlay, ambiguous countdown).
- New-Round respawn rule: 7/7 consistent.
- Stale death withdrawal, 8 frames: 4 removed a wrong DEAD, 2 withdrew a correct
  DEAD (now abstentions), 2 undecidable.
- Round ends 6/6 bracket the score update; in one, the result banner was already
  visible at the lower frame, so the decision lies a few seconds earlier.
- Round starts: result-to-ACTIVE 6/6 and countdown-narrowed 6/6 contain the start.
  The first version used short unverified carries as anchors and closed 3 of 6
  brackets about 2 s late; anchors are now measured estimates only.
- A rejected variant that also set the camera from open death hypotheses
  contradicted 5 of 7 frames (purchase phases after a stale death) and is not
  included; the stale-death rule above addresses that cause.

## Limits and next steps

- No fresh pixel acquisition was run: these are replays of existing native
  observations. A full fresh acquisition and the remaining camera UNKNOWN need
  the private observer configuration and a pixel cue for the spectator target
  label at the lower left, which is visible in every reviewed spectator frame.
- Sub-second internal boundary error, unseen-match generalization and recorder
  ownership accuracy remain unmeasured.
- The 1:40 Round countdown is a competitive-format constant; other formats need
  their own value before using the countdown projection.

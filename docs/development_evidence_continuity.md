# Evidence continuity in the shared development timeline

`--evidence-continuity` (API: `DevelopmentGameTimeline(evidence_continuity=True)`)
adds an offline revision pass to the existing shared state owner. It is not a
second state machine: it revises the rows that `DevelopmentGameTimeline.rebuild`
already produced, keeps the previous estimate under `rule_estimate`, cites the
native observations it used and records every change in
`evidence_continuity_projection_history`, with per-rule counts in
`evidence_continuity_summary`. The default path is unchanged. Formal
Facts/Events, qualification and recorder ownership are unchanged.

Related: #121, #124, #138. Code: `src/valorant_ai_coach/temporal/evidence_continuity.py`.

## Rules

Every rule combines measured displays with a game invariant that excludes the
alternatives. Missing frames, decode breaks, conflicting readings, unexplained
gaps and short unverified carries stop a revision. There are no Source, time or
match specific conditions and no threshold changes in any recognizer.

| Rule | Measured inputs | Invariant | Revision |
| --- | --- | --- | --- |
| Same-score phase bracket | Two measured BUY/ACTIVE/ENDED anchors of the same phase, equal score readings around and inside | The displayed score never decreases and changes once per decided Round | Unobserved rows between take the anchor phase |
| ACTIVE before a score change | ACTIVE anchor; later frames still showing its score | As above, plus the score display may follow the decision by up to `DECISION_DISPLAY_LEAD` (5 s; at most 3 s measured on the ten matches) | Rows up to the last measured ACTIVE cue, or the last old-score row at least 5 s before the update, are ACTIVE; later rows stay unrevised |
| ENDED after a score change | One-point increment; later ENDED anchor with the new score | As above | Rows from the first new-score frame to the anchor are ENDED |
| Round end candidate | Same inputs | One increment is one decided Round | `round_end` between the last known-undecided frame and the first result cue or new-score frame |
| Existing score-update end edges | An existing end edge whose lower frame is only the last old-score frame | Display lead as above | Lower bound moved back to the last known-undecided frame (`lower_sample_basis: score_display_lead`, `rule_lower_sample` kept) |
| Round start candidate | BUY or ENDED anchor, later ACTIVE anchor, equal score | A new Round starts only after its purchase phase | `round_start` bracket. The first countdown reading (30 to 100 s, within 60 s of the ACTIVE anchor) confirmed by a second consistent reading projects the start at `t - (100 - shown)`: the bracket closes to the frames 1 s either side, and rows after the projected start become ACTIVE |
| Spectating during a Round | Measured spectator panel, or the combat report, learned spectator view and the recorder's alias in the elimination display together; no owner HUD, remote, revival or purchase cue; Round ACTIVE/ENDED | Living players do not spectate | Life `DEAD` (alternative `DOWNED`) |
| Dead bracket | Two such DEAD anchors, unchanged score, no owner HUD, revival or purchase cue between, no SELF/REMOTE camera between | No respawn inside a Round without revival | Rows between are DEAD |
| Not alive, not first person | DEAD without an open alternative, no owner HUD/remote/revival cue | A recorder that is not alive cannot hold the first-person view | Camera `SPECTATOR` |
| Purchase phase | BUY Round state (measured or same-score bracket), no spectator/remote/death cue | All players are alive in the purchase phase | Unknown life becomes ALIVE |
| Respawn | Score higher than at the last measured death **and** a measured BUY or a Round start candidate since the death **and** a current owner HUD inside a BUY/ACTIVE phase, no death/spectator/report cue | A new Round respawns every player | Life ALIVE |
| Stale death hypothesis | An open (`UNKNOWN`-alternative) death hypothesis still latched after the score increased | A death hypothesis cannot outlive its Round | Withdrawn to UNKNOWN, or ALIVE under the respawn conditions above |

### Consistency after revision

- Added events carry `single_boundary_interval` (the anchor pair that can contain
  only that boundary) and are added only if no existing candidate of the same
  kind overlaps it.
- Stale `state_change` edges are archived in `superseded_transition_candidates`.
  Named edges (spectator, death, return) whose lower frame already holds the
  edge's after-state move to the first frame of that run (`rule_transition` kept).
- Current recorder-view Map candidates on a revised frame that no longer has a
  living first-person view are moved to `continuity_superseded_current_view`.
  Round numbers and provisional Map roles are recomputed after the pass.
- `consistency_violations(timeline)` counts frame, Map and edge contradictions.

### Withdrawn values are not error counts

`withdrawn_to_unknown_frames` counts values the pass returned to UNKNOWN. It is
an abstention count. Whether a withdrawn value was wrong is measured only by
review (below).

## Running

```bash
python -m valorant_ai_coach.temporal.application generate ... --practical-visual-state --evidence-continuity
python -m valorant_ai_coach.temporal.application export ... --evidence-continuity
```

`export` restores the flag from the stored engine configuration. The flag is
recorded in a new acquisition checkpoint binding only when it is enabled, so
existing checkpoints remain compatible. It requires offline mode.

## Validation (2026-11-16)

Inputs: the same previously acquired native observations of the ten admitted
DEVELOPMENT matches used for the #145 integration replay. The replay harness
first reproduced the baseline exactly: 21,999 rows, UNKNOWN Round 7,230 / Life
5,322 / Camera 4,118 seconds and the original fixed-label scorer's 69 attributes
(Round 23, Life 20, Camera 26 correct; 14 labels not observed).

| Measure | Before | After |
| --- | ---: | ---: |
| Round UNKNOWN seconds | 7,230 | 4,026 |
| Life UNKNOWN seconds | 5,322 | 3,401 |
| Camera UNKNOWN seconds | 4,118 | 4,016 |
| Seconds changed between two known values | – | 0 |
| Life seconds withdrawn from DEAD to UNKNOWN (abstentions) | – | 1,138 |
| Fixed 69 attributes: correct / incorrect / abstained | 69 / 0 / 0 | 69 / 0 / 0 |
| Supplemental 9 and 6 attributes | 9/9, 6/6 | 9/9, 6/6 |
| Rounds with a start candidate (229 Rounds) | 167 | 221 |
| Rounds with an end candidate (plus 5 final-Round ends after the last score display) | 197 | 220 |
| Duplicate start/end candidates for one Round | 0 / 0 | 0 / 0 |
| Start bracket width median / p90 / max (s) | 1 / 3 / 5 | 1 / 3 / 25 |
| End bracket width median / p90 / max (s) | 1 / 2 / 3 | 3 / 5 / 14 |
| Frames: DEAD recorder with a first-person camera | 223 | 201 |
| Named or state edges disagreeing with their frames | 57 | 0 |
| Formal Facts/Events | 0 | 0 |

End brackets are wider on purpose: in 3 of 6 reviewed score-update edges the
post-round countdown was already visible at the old lower frame, so the previous
bracket excluded the decision. 218 of 221 start brackets are at most 10 s wide.

Original-video spot checks: frames decoded at the exact native PTS and reviewed
visually by the implementing agent (not human GT):

| Check | Result |
| --- | --- |
| Revised frames, 7 per rule (first version) | 61 consistent, 0 contradicted, 2 undecidable |
| Respawn rule (first version, owner HUD + score) | 7/7 consistent |
| Stale death withdrawals, 8 frames | 4 removed a wrong DEAD, 2 withdrew a correct DEAD, 2 undecidable |
| Widened end brackets, 6 | 6/6 contain the decision; 3/6 old brackets did not |
| Countdown-filled ACTIVE rows, 6 | 6/6 show the running Round countdown |
| Result-to-ACTIVE and countdown-narrowed starts, 12 | 12/12 contain the start |

The 1,138 withdrawn seconds are therefore not 1,138 confirmed errors: the
reviewed sample found 4 wrong and 2 correct values among 6 decidable frames.

## Limits

- These are replays of existing native observations; fresh pixel acquisition is
  separate.
- Sub-second boundary error, unseen-match generalization and recorder
  ownership accuracy remain unmeasured.
- The 1:40 countdown and the display lead are competitive-format values.

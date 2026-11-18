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
| Round start candidate | BUY or ENDED anchor, later ACTIVE anchor, equal score | A new Round starts only after its purchase phase | `round_start` bracket. The first countdown reading (30 to 100 s, within 60 s of the ACTIVE anchor) confirmed by a second consistent reading projects the start at `t - (100 - shown)`: the bracket closes to the frames 1 s either side (the earlier anchor itself when it is closer), and rows after the projected start become ACTIVE. A projection before the earlier anchor is rejected |
| Purchase before combat | A measured BUY anchor, then the next measured BUY anchor or the combat start projected from two countdown readings after the next ACTIVE anchor; equal score readings; no result or intermission cue | The purchase phase precedes the combat phase of its Round and never follows it | Unmeasured ACTIVE values in between (single visual cues, never measured anchors) become BUY; Round start candidates lying wholly inside are archived in `superseded_transition_candidates` |
| Purchase countdown | A measured ACTIVE anchor whose countdown projects the combat start `S`; earlier rows of the same score with timer readings `r` where `t + r = S` (±1 s), at least two; no other reading before `S` and no result cue after the first match | The purchase countdown of a Round ends when its combat countdown starts | Rows from the first matching reading up to `S - 1` become BUY (rows with a current spectator, death or elimination cue are skipped); start candidates inside the interval are retired |
| Stale death latch in the purchase phase | A victim-display death hypothesis on a purchase-countdown row without a current non-living cue | All players are alive in the purchase phase | Life ALIVE; a carried spectator view on that row becomes SELF; the same latch carried one row past the interval with a first-person view is withdrawn |
| Overlapping start candidates | Two existing `round_start` candidates within 1 s of each other | Two Round starts are separated by a decided Round and a purchase phase | The narrower bracket is kept; the other is archived |
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
| Round UNKNOWN seconds | 7,230 | 3,202 |
| Life UNKNOWN seconds | 5,322 | 2,771 |
| Camera UNKNOWN seconds | 4,118 | 4,019 |
| Matches where any UNKNOWN count rose | – | 0 of 10 |
| Seconds changed between two known values | – | Life DEAD to ALIVE 445, Camera SPECTATOR to SELF 3 (all inside a purchase countdown) |
| Life seconds withdrawn from DEAD to UNKNOWN (abstentions) | – | 772 |
| Fixed 69 attributes: correct / incorrect / abstained | 69 / 0 / 0 | 69 / 0 / 0 |
| Supplemental 9 and 6 attributes | 9/9, 6/6 | 9/9, 6/6 |
| Rounds with a start candidate (229 Rounds) | 167 | 221 (220 indexable by a later score reading) |
| Rounds with an end candidate (plus 5 final-Round ends after the last score display) | 197 | 220 |
| Duplicate start/end candidates for one Round | 0 / 0 | 0 / 0 |
| Start bracket width median / p90 / max (s) | 1 / 3 / 5 | 1 / 3 / 5 |
| End bracket width median / p90 / max (s) | 1 / 2 / 3 | 3 / 5 / 14 |
| Frames: DEAD recorder with a first-person camera | 223 | 200 |
| Frames: DEAD recorder in a purchase phase | – | 0 |
| Named or state edges disagreeing with their frames | 57 | 0 |
| Formal Facts/Events | 0 | 0 |

Before the purchase countdown rule (9b76cae) the same replay gave Round 3,975,
Life 3,401, Camera 4,016 and 1,138 withdrawn seconds; the Round start and end
candidates are identical with and without that rule.

End brackets are wider on purpose: in 3 of 6 reviewed score-update edges the
post-round countdown was already visible at the old lower frame, so the previous
bracket excluded the decision. The 167 start brackets that existed before are
unchanged.

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
| Start brackets against the countdown switch (0:00 to 1:39) read every 0.5 s, 16 (10 added, 6 existing) | 16/16 contain the switch; bracket midpoint error median 0.25 s, max 2.25 s (an existing 5 s bracket) |

Withdrawn seconds (772 now, 1,138 before the purchase countdown rule) are
therefore not confirmed errors: the reviewed sample of the first version found
4 wrong and 2 correct values among 6 decidable frames.

### Fresh full-length analysis: all ten matches (2026-11-18)

The existing acquisition command (`generate`, 1 s sampling, ScreenCueObserver)
was run again on all ten DEVELOPMENT recordings from the original video files
in a Linux container (21,999 seconds), and each result was rebuilt with and
without the pass. Holdout recordings were not used.

| Measure | Before | After |
| --- | ---: | ---: |
| Round UNKNOWN seconds | 7,071 | 3,154 |
| Life UNKNOWN seconds | 4,059 | 2,208 |
| Camera UNKNOWN seconds | 3,333 | 3,218 |
| Matches where any UNKNOWN count rose | – | 0 of 10 |
| Seconds changed between two known values | – | Round ACTIVE to BUY 13, Life DEAD to ALIVE 444, Camera SPECTATOR to SELF 2 |
| Life seconds withdrawn to UNKNOWN | – | 598 |
| Round start candidates (229 Rounds) | 183 | 221 |
| Starts of the replayed run (221) with a fresh candidate within 2 s | 166 | 221 |
| Fresh candidates more than 2 s from every replayed start | 12 | 0 |
| Pairs of overlapping start candidates | 6 | 0 |
| Max start width (s) | 5 | 5 |
| Human labels sampled by the fresh run (72 of 78): correct / abstained / incorrect | 72 / 0 / 0 | 72 / 0 / 0 |

Per match (Round, Life UNKNOWN seconds before to after): DEV2 465 to 132, 554
to 206; issue_oldfull001 531 to 276, 535 to 268; issue_oldfull002 951 to 474,
288 to 204; issue_oldfull004 622 to 257, 309 to 139; issue_newfull001 759 to
346, 428 to 229; issue_newfull002 874 to 392, 367 to 212; issue_freshfull003
739 to 369, 367 to 210; issue_newfull004 942 to 425, 519 to 317;
issue_freshfull005 477 to 154, 266 to 158; first_new_cold 711 to 329, 426 to
265.

The fresh run agrees with the replay of the stored observations: of 21,999
seconds, Round differs between two known values in 41 seconds, Life in 30 and
Camera in 44 (the base engine alone differs in 38, 82 and 44).

Implementing-agent visual review (not human GT):

| Sample | Result |
| --- | --- |
| All 13 seconds revised from ACTIVE to BUY | 13 show the purchase phase (buy menu, purchase banner or purchase countdown) |
| Life DEAD to ALIVE, 24 seconds drawn at random from 442 | 24 show the recorder alive in the purchase phase |
| Camera SPECTATOR to SELF, both seconds | 2 show the recorder's own view in the purchase phase |
| Withdrawn DEAD in issue_oldfull002, 5 seconds | 5 show the recorder alive with its own HUD (the DEAD was wrong) |
| Early start candidates retired, 5 in issue_freshfull003 | 5 inside the purchase phase, before its countdown ends |

The early candidates came from single unmeasured ACTIVE frames
(`observed_purchase_barrier_loss`) inside the purchase phase; the base timeline
had 12 of them and 6 overlapping pairs.

## Limits

- The fixed comparison replays existing native observations; the fresh run
  repeats all ten from the recordings but on the same development matches.
- The purchase rule needs a measured BUY anchor before the unmeasured ACTIVE
  value and either a later BUY anchor or two countdown readings; without them
  an early start candidate is kept.
- Sub-second boundary error, unseen-match generalization and recorder
  ownership accuracy remain unmeasured.
- The 1:40 countdown and the display lead are competitive-format values.

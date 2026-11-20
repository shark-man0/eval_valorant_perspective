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
| Countdown after a decided Round | An existing end edge whose upper frame is ENDED (measured, or a one-point score increment) with one clock reading `r` at `t`; earlier or later rows of the same segment reading `t + r - t_k` | The single Round clock counts down one second per second within a phase; at least two matching readings | Matching rows, and rows without a reading between two matching ones, without a measured ACTIVE or purchase cue become ENDED (`post_round_countdown_after_measured_end`). If the chain starts before the edge (at most the display lead), the edge moves to its first row; the lower bound is the frame before it when that frame shows another clock reading, otherwise the display-lead walk (`lower_sample_basis: post_round_countdown`, rule samples kept) |
| Zero-width end at the first result display | An existing end edge whose lower and upper frame are the same frame with a measured result cue | The result is displayed after the Round is decided, so the decision lies before that frame | Lower bound moved back through same-scope frames with no result, BUY or intermission cue and one old score at most, to the latest measured ACTIVE cue or the display lead (`lower_sample_basis: result_display_lead`, `rule_lower_sample` kept). Frame values are unchanged |
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
| Stale death hypothesis | An open (`UNKNOWN`-alternative) death hypothesis still latched after the score increased **and** a measured BUY or a Round start candidate since the hypothesis began | A death hypothesis cannot outlive its Round; the score rises with the result while the dead recorder keeps spectating until the next purchase phase | Withdrawn to UNKNOWN, or ALIVE under the respawn conditions above |

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
| Life UNKNOWN seconds | 5,322 | 2,031 |
| Camera UNKNOWN seconds | 4,118 | 4,016 |
| Matches where any UNKNOWN count rose | – | 0 of 10 |
| Seconds changed between two known values | – | Life DEAD to ALIVE 451, Camera SPECTATOR to SELF 9 (all inside a purchase countdown) |
| Life seconds withdrawn from DEAD to UNKNOWN (abstentions) | – | 33 |
| Fixed 69 attributes: correct / incorrect / abstained | 69 / 0 / 0 | 69 / 0 / 0 |
| Supplemental 9 and 6 attributes | 9/9, 6/6 | 9/9, 6/6 |
| Rounds with a start candidate (229 Rounds) | 167 | 221 (220 indexable by a later score reading) |
| Rounds with an end candidate (plus 5 final-Round ends after the last score display) | 197 | 220 |
| Duplicate start/end candidates for one Round | 0 / 0 | 0 / 0 |
| Start bracket width median / p90 / max (s) | 1 / 3 / 5 | 1 / 3 / 5 |
| End bracket width median / p90 / max (s) | 1 / 2 / 3 | 3 / 5 / 14 |
| Frames: DEAD recorder with a first-person camera | 223 | 215 |
| Frames: DEAD recorder in a purchase phase | – | 0 |
| Named or state edges disagreeing with their frames | 57 | 0 |
| Formal Facts/Events | 0 | 0 |

Before the purchase countdown rule (9b76cae) the same replay gave Round 3,975,
Life 3,401, Camera 4,016 and 1,138 withdrawn seconds; the Round start and end
candidates are identical with and without that rule. Before the stale death
hypothesis rule required a new Round (see the run-level review below) it gave
Life 2,771 with 772 withdrawn seconds; Round and the 69 attributes are
identical.

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

Withdrawn seconds are therefore not confirmed errors; the run-level review of
the fresh run below measures them.

### Fresh full-length analysis: all ten matches (2026-11-18)

The existing acquisition command (`generate`, 1 s sampling, ScreenCueObserver)
was run again on all ten DEVELOPMENT recordings from the original video files
in a Linux container (21,999 seconds), and each result was rebuilt with and
without the pass. Holdout recordings were not used.

| Measure | Before | After |
| --- | ---: | ---: |
| Round UNKNOWN seconds | 7,071 | 3,154 |
| Life UNKNOWN seconds | 4,059 | 1,620 |
| Camera UNKNOWN seconds | 3,333 | 3,218 |
| Matches where any UNKNOWN count rose | – | 0 of 10 |
| Seconds changed between two known values | – | Round ACTIVE to BUY 13, Life DEAD to ALIVE 451, Camera SPECTATOR to SELF 9 |
| Life seconds withdrawn to UNKNOWN | – | 10 |
| Round start candidates (229 Rounds) | 183 | 221 |
| Starts of the replayed run (221) with a fresh candidate within 2 s | 166 | 221 |
| Fresh candidates more than 2 s from every replayed start | 12 | 0 |
| Pairs of overlapping start candidates | 6 | 0 |
| Max start width (s) | 5 | 5 |
| Human labels sampled by the fresh run (72 of 78): correct / abstained / incorrect | 72 / 0 / 0 | 72 / 0 / 0 |

Per match (Round, Life UNKNOWN seconds before to after): DEV2 465 to 132, 554
to 186; issue_oldfull001 531 to 276, 535 to 228; issue_oldfull002 951 to 474,
288 to 113; issue_oldfull004 622 to 257, 309 to 108; issue_newfull001 759 to
346, 428 to 118; issue_newfull002 874 to 392, 367 to 174; issue_freshfull003
739 to 369, 367 to 149; issue_newfull004 942 to 425, 519 to 189;
issue_freshfull005 477 to 154, 266 to 132; first_new_cold 711 to 329, 426 to
223.

The fresh run agrees with the replay of the stored observations: of 21,999
seconds, Round differs between two known values in 28 seconds, Life in 96 and
Camera in 44 (the base engine alone differs in 38, 82 and 44).

Implementing-agent visual review (not human GT):

| Sample | Result |
| --- | --- |
| All 13 seconds revised from ACTIVE to BUY | 13 show the purchase phase (buy menu, purchase banner or purchase countdown) |
| Life DEAD to ALIVE, 24 seconds drawn at random from 442 | 24 show the recorder alive in the purchase phase |
| Camera SPECTATOR to SELF, both seconds | 2 show the recorder's own view in the purchase phase |
| Withdrawn DEAD in issue_oldfull002, 5 seconds | 5 show the recorder alive with its own HUD (the DEAD was wrong) |
| Early start candidates retired, 5 in issue_freshfull003 | 5 inside the purchase phase, before its countdown ends |

The 1,010 DEAD seconds withdrawn at 1da4bd7 (reproduced by replaying that
commit on the same stored observations) were abstentions, not confirmed errors.
In the current replay 663 of them keep the base DEAD, 331 are ALIVE (purchase
phase or the own HUD with health, see the run-level review) and 16 remain
UNKNOWN; 33 seconds are withdrawn in total.

Protected recordings (2026-11-19, with the user's permission, one final run):
all four full_match_5 recordings (7,414 seconds), acquired from the originals
with the same command. Nothing was tuned on them. UNKNOWN seconds before / with
this option / combined with #151: Round 2,206 / 762 / 762, Life 1,318 / 556 /
255, Camera 1,112 / 1,089 / 355. No match rose in any domain. Round start
candidates 77 to 81, end candidates 76 to 84. Every second of the combined run
that changed between two known values was viewed (248 seconds, AI review): 247
consistent, 1 contradicted (a measured spectator value carried 1 s into the
next purchase phase by the existing 2 s carry, #151). Of 84 sampled
withdrawals the old value was wrong in 67, right in 3 and undecidable in 14.

Round boundaries against human GT (2026-11-19): the user marked, on frames one
second apart, the first frame of 12 Round starts (purchase countdown replaced by
the combat clock) and 12 Round ends (result banner), drawn at random from the
combined fresh run without seeing any prediction. Candidate containing the
human second / error in seconds when not / no candidate:

| Kind | Base | Combined |
| --- | --- | --- |
| Start | 10 contain, 0 missed, 2 no candidate | 12 contain, 0 missed, 0 no candidate |
| End | 8 contain, 3 one second off, 1 no candidate | 9 contain, 3 one second off, 0 no candidate |

The three one-second end errors were zero-width candidates (lower and upper on
the same frame) identical in the base engine; the human marks the result banner
one second earlier. The zero-width rule above (2026-11-20) moves their lower
bound back.

A second boundary sheet (2026-11-20): 30 boundaries drawn at random from all
fourteen matches (the ten above and the four protected recordings), again
marked by the user without seeing a prediction. One end lay before the window
shown and is excluded. Candidate containing the human second, with both sheets
together (24 + 29 boundaries):

| Kind | Base | Combined, before the zero-width rule | Combined, with it |
| --- | --- | --- | --- |
| Start | 18 contain, 6 no candidate | 24 contain | 24 contain |
| End | 18 contain, 8 off by 1 to 4 s, 3 no candidate | 22 contain, 7 off by 1 or 2 s | 29 contain |

Every remaining miss before the rule was a zero-width candidate. On the
fourteen fresh runs the rule widens 57 of 95 zero-width ends (median end width
3 to 5 s, maximum unchanged at 17 s) and changes no frame value. The fixed
comparison is unchanged in every domain and keeps 69/69. The 38 zero-width ends
left have no measured result cue on their frame and were not sampled by either
sheet. The 33 of them in the ten development matches were viewed on the
originals, two seconds before to one second after (AI review, not human GT):
in 27 the edge frame is the first frame after the Round end (post-round clock
or result banner); in 6 the post-round clock was already shown one second
earlier, so the edge is one second late. The 5 in the protected recordings were
not viewed.

The countdown rule above (2026-11-20) addresses those late edges. Fixed
comparison: Round UNKNOWN 3,202 to 3,131 seconds, 14 seconds ACTIVE to ENDED,
Life and Camera unchanged, 69/69 kept, no consistency violation added. Fresh
runs: five of the six late edges now contain the end; the sixth shows a frozen
spike clock, not a countdown, and stays. Fourteen matches: Round UNKNOWN 3,154 to 3,077 in the ten and 762 to 752
in the protected four; ACTIVE to ENDED 28 and 18 seconds; zero-width ends 38 to
32. One end candidate the second human sheet marked as later than the actual
end (the Round had ended before the frames shown) was a duplicate of an earlier
candidate and is gone; all other human boundaries stay contained (start 24/24,
end 29/29). AI review of the changed seconds in the ten matches (all 28 ACTIVE
to ENDED and 20 of 77 UNKNOWN to ENDED, at random): 48/48 show the post-round
clock (0:06 to 0:00) or the result banner. The protected seconds were not
viewed.

Rows without a clock reading between two matching readings (added the same
day, after the third human sheet showed an ACTIVE value on a frame with the
result banner whose clock had not been read): fixed comparison Round UNKNOWN
3,131 to 3,076 and ACTIVE to ENDED 24 more seconds (38 in all), 69/69 kept;
fresh runs Round UNKNOWN 3,077 to 3,007 (ten) and 752 to 729 (protected four).
AI review of the changed seconds in the ten matches (all 24 ACTIVE to ENDED and
16 of 70 UNKNOWN to ENDED, at random): 40/40 show the post-round clock or the
result banner.

Third human sheet (2026-11-20): 120 frames drawn uniformly from all fourteen
fresh runs (24 from the protected recordings), labelled by the user without
seeing any prediction; one frame marked unknown is excluded. Correct /
incorrect / abstained, base / this option / combined with #151: Round
77/1/42, 103/0/17, 103/0/17; Life 84/10/25, 105/6/8, 112/0/7; Camera 101/2/16,
101/2/16, 109/1/9. The frames that disagreed with any version were viewed on
the originals (AI review): no labelling error found. Three frames right after
the recorder's death are labelled first-person view and dead; the death is
right, whether the death camera counts as the recorder's own view is a matter
of definition.

Random human GT (2026-11-19): the user labelled 80 frames of the fresh run
without seeing any prediction: 40 drawn uniformly from all 21,999 seconds and 40
drawn uniformly from the seconds that either PR changed. Frames the user marked
unknown are excluded. Correct / incorrect / abstained:

| Sample | Domain | Base | This option | Combined with #151 |
| --- | --- | --- | --- | --- |
| Uniform 40 | Round | 27 / 0 / 12 | 31 / 0 / 8 | 31 / 0 / 8 |
| Uniform 40 | Life | 25 / 1 / 13 | 32 / 1 / 6 | 36 / 0 / 3 |
| Uniform 40 | Camera | 28 / 1 / 10 | 28 / 1 / 10 | 34 / 0 / 5 |
| All 80 | Round | 39 / 0 / 40 | 65 / 0 / 14 | 65 / 0 / 14 |
| All 80 | Life | 38 / 6 / 35 | 62 / 5 / 12 | 76 / 0 / 3 |
| All 80 | Camera | 52 / 3 / 24 | 52 / 3 / 24 | 70 / 2 / 7 |

This option adds no incorrect value; it removes one Life error (a stale death
hypothesis in a purchase phase). The remaining Life errors under this option
alone are DEAD values on the recorder's own HUD that #151 resolves.

Human GT (2026-11-19): the user labelled 36 DEV2 sample frames without seeing
any prediction; frames marked unknown are excluded (Camera 29, Life 34). The
frames were picked for review, not drawn at random. Fresh run, correct /
incorrect / abstained: Life 17 / 0 / 17 before and 25 / 0 / 9 after; Camera is
unchanged by this option (19 / 6 / 4; the six errors are drone views, handled
in #151).

Run-level review of every changed run (one or more frames per run decoded at
the native PTS, implementing agent, not human GT):

| Changed runs | Result |
| --- | --- |
| Life DEAD to ALIVE, all 22 runs (43 frames) | 43 consistent (own HUD with health or the purchase phase), 0 contradicted |
| Life DEAD to ALIVE added by the new-Round condition, 7 seconds | 7 consistent (3 frames checked directly, 4 by the adjacent second) |
| Life DEAD withdrawn, before the new-Round condition: all 121 runs | 57 the DEAD was wrong, 53 the DEAD was right (spectator label visible, mostly after the result), 11 undecidable |
| Life DEAD withdrawn, now: 3 runs, 10 seconds | 3 the DEAD was wrong (own HUD with health) |

All 121 withdrawals came from the stale death hypothesis rule. The 53 correct
values were withdrawn because the score rose with the Round result while the
recorder was still spectating; the stored observations of those rows hold no
other cue. The rule now also needs a measured purchase phase or a Round start
candidate after the hypothesis began, which keeps all 53 and leaves 53 of the 57
wrong values as they were in the base timeline.

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

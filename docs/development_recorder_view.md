# Recorder association, frame reviews and boundary checks

These opt-in Map/Visual APIs provide development evidence, not qualified recorder
ownership. They do not issue Production Facts, Player Events or coaching scores.
Production registries/schemas and HUD recognizer implementations are unchanged.

## Positive evidence chain and its limit

`DevelopmentRecorderView` combines two distinct inputs:

1. A human-reviewed source roster binds a recorder alias and agent to one source
   SHA, physical match identity, anchor image and explicit acquisition allowlist.
2. Current-frame ability glyphs outside the minimap are compared to a small agent
   reference vocabulary. At least two disjoint glyphs need NCC0.90 and a0.12
   runner margin. Multiple glyphs remain **one correlated HUD-agent family**.

A successful match reports `recorder_agent_supported`, not SELF. It positively
supports the recorder-agent association rather than relying on absent spectator
UI. It does not prove account control: the vocabulary is incomplete, UI states
change, agent appearances can be shared, and match/roster uniqueness is not
qualified. Temporal continuity never upgrades this evidence to ownership.

A private profile's optional `development_recorder_view` includes:

- `mode: agent_binding_v1`, exact `frame_size_px`;
- `binding`: `source_id`, `source_sha256`, `physical_match_id`, acquisition IDs,
  `review_kind: human_source_roster`, anchor/review SHA-256, recorder agent/alias;
- two to four nonoverlapping normalized `slots`, disjoint from the minimap;
- two to eight `agents`, each with one to three PNG templates for each slot;
- optional `actor_alias` evidence described below.

`DevelopmentMapTimeline.observe` accepts optional `source_sha256` for this opt-in
binding. Missing/different source identity, unreviewed bindings, geometry errors
or invalid references fail closed. A confidently different agent blocks the
position candidate. An unknown signature stays unknown; it does not discard an
otherwise valid unqualified position merely for failing to recognize the HUD.
Reference fingerprints include actual bytes and the binding; changes break
tracking. No previous predicted identity or calibration transform is reused.
Profiles without this option keep the existing recognition behavior.

References reuse the existing bounded screen matcher, including its contrast and
file-size checks. Preflight **all** references before a replay. An initial real
comparison failed closed because three exemplars were below the loader's existing
contrast requirement. Those entries were removed without lowering recognition
thresholds; an unsupported fourth class was omitted. Both runs remain private.
This authoring repair is not an accuracy improvement or independent qualification.
An explored top-hat stroke method did not improve the old Haven control window
and was not adopted.

## Explicit current-player names

`DevelopmentActorAlias` reads only a reviewed, positively activated name slot.
Configuration supplies exact frame geometry, `name_roi`, `slot_review`,
`slot_kind` and a bounded screen-pattern `activation`. The slot/chrome must be
outside the minimap. OCR is not invoked when activation is absent. Existing
`TesseractTextReader(language="eng")` is reused read-only; missing OCR stays
unknown, and accepted text requires confidence at least0.90. OCR is optional.

`spectated_player_name` always blocks a recorder-view candidate, even when its
text matches the recorder alias. `current_actor_identifier` can record an exact
alias-match candidate for a future recording with an independently reviewed
current-actor overlay. A display alias is not a unique account ID, and this mode
also retains ownership UNKNOWN. Do not use scoreboard, chat or kill-feed text as
though it identified the currently viewed actor.

The source recordings show recorder information in scoreboard rows, whereas
live first-person views do not continuously display the recorder's name. A
spectator panel does show another player's name. This is the remaining
observability gap: HUD/agent similarity and absent spectator controls cannot
establish a qualified account-to-current-camera link. A new recording with an
explicit trustworthy current-actor identifier, or separately sourced camera/
player identity metadata, could supply the missing evidence. Ordinary additional
VODs can still improve agent/context/position evaluation, but do not automatically
solve this identity gap.

## Human labels and safe paths

`compare_view_review` binds a response to one frozen prediction and acquired image
hash. Its roles are `SELF_LIVE`, `SELF_PURCHASE`, `PURCHASE`, `SPECTATOR`, `DEATH`
and `UNKNOWN`. A short clip response is imported as an explicit list of the actual
sampled frame hashes, never as an inferred continuous time interval. These labels
remain separate from automatic agent association and automatic ownership.

The [private benchmark/review CLI](development_map_evidence.md) accepts optional
`view_reviews` alongside coordinate `reviews`. Both share source/acquisition,
frame/time, map/geometry and frozen prediction/image anchors. `PURCHASE` does not
assert owner identity. Non-live human roles break candidate paths. SELF labels
never revive a rejected/missing position, add interpolation or create a Fact.

Path reports distinguish positions with human-reviewed live views from positions
with current-agent support, and count edges whose **two endpoints** have each
kind of support. These spans do not prove ownership or the route between samples.
The viewer presents both evidence types alongside coordinate residuals and gaps.
Duplicate/reversed frame indices now reset the development pipeline and reject
the observation, as do nonincreasing source times. A resumed valid observation
starts a fresh track/Zone dwell; a new acquisition must be explicit.

## Boundary comparison and calibration variation

A coordinate review can set `include_boundary_comparison: true`.
`compare_review_boundaries` compares the frozen position and the independent
three-landmark affine point against **existing registered polygons**. It reports
membership, signed boundary distances and whether single-coordinate +/-annotation
tolerance perturbations change membership. Collinear/singular geometry is rejected.

This finite perturbation diagnostic is not a joint uncertainty bound. No flips
cannot prove a robust interior, and agreement does not validate a full Site or
physical Zone boundary. No thresholds, polygons or canonical GT are fitted to the
responses. Sparse point residuals are not propagated as a whole-path error radius.

For calibration stability, a fixed ROI probe's projected spread and same-image
repeatability are separate from player jitter and true landmark error. Preserve
rejected probes. A moving source window cannot establish stationary-player GT.

## Repeating the comparison on a new recording

Register/split the recording before viewing it. Never open protected evaluation
candidates. Retain native ticks/source hashes and declare short windows and review
ordinals before predictions. Freeze references separately, keep failed windows,
and do not search for successful predictions to select coordinate GT.

Useful additional DEVELOPMENT footage includes:

- another Bind match with a readable roster/recorder row and a source-specific
  agent binding, plus a few first-person, death, spectator-switch and buy samples;
- unchanged/explicit HUD geometry, full minimap, and no cut hidden as continuity;
- short stationary and boundary-crossing clips independently reviewed as such,
  with corresponding static map corners visible;
- for a stronger account link, a visible current-actor identifier or separately
  sourced camera/player identity record, rather than a recorder name watermark.

There is currently no claimed second Bind recording. A new source needs its own
binding; do not transfer one video's agent/alias or a single view label wholesale.
All raw videos, Profiles, aliases, images, frame times/positions, review packets,
HTML and individual results remain private. Publish only aggregate comparisons.

## Current DEVELOPMENT evidence

Three independently reviewed roster rows bind the recorder to different agents
in three sources; no binding is transferred between videos. Human view review of
a separate fixed30-observation Bind clip confirms the displayed30 live views.
A fixed Haven clip instead contains16 death observations followed by14 purchase
observations. Both failed/negative windows are retained; the clip labels are not
fed into recognition or extended to unobserved frames.

| New fixed window | Baseline Map | With recorder evidence | Agent/view support |
|---|---:|---:|---:|
| Bind, 30 human-reviewed live observations | 26 | 26 | 29 agent/view supports, 25 with position |
| Haven, 16 death + 14 purchase observations | 0 | 0 | 1 agent association, 0 eligible view supports |
| Separate Haven recording, 30 unreviewed context observations | 0 | 0 | 0 |
| Haven B-boundary window, 10 observations | 10 | 10 | 0 |

Bind has two candidate segments, longest3.6s. Human-reviewed live endpoints bracket
4.8s in total; agent-supported endpoints bracket4.4s. These describe observed
endpoints, not a guaranteed continuously owned/travelled route. Automatic
ownership is UNKNOWN throughout, with zero formal output. This is a known
DEVELOPMENT comparison, not independent qualification or automatic self precision.

The Haven boundary window has a B-plant region candidate at10 points and1.8s of
same-region endpoint spans, but no accepted namedZone. Its three fixed reviewed
points have ROI differences1/1/2px and approximate Map-reference differences
4.00/4.13/5.31 referencepx, without affine extrapolation. All three agree on the
registered B polygon, but two change membership under a single-coordinate2px
annotation perturbation. The14px assumed boundary disk yields0.4s of interior endpoint spans, still only
under that assumption and not verified dwell.
This does not establish true Site-boundary accuracy or continuous dwell.

Across10 boundary frames, two fixed ROI probes are accepted each time and their
projected spread is0px; the third probe is rejected each time and remains
unmeasured. Three recalibrations of the same image agree. Player stationary
jitter is unmeasured because this source window contains movement.

An old20-observation spectator window yields11 explicit different-alias
candidates and9 unknown text measurements against its own reviewed recorder
binding. Existing context vetoes already rejected positions, so this is new
identity evidence, **not demonstrated false-attribution reduction**. Matching a
known recorder alias in a live current-actor slot is supported by a synthetic
adapter test, not observed in these ordinary live VOD frames.

Four single-thread bounded comparisons take8.37→9.03s,8.91→8.22s,8.13→8.18s and
3.13→3.17s, baseline→variant. Same-process peak207.5MiB includes viewer exports;
it is not an isolated per-recognizer memory comparison or a speedup claim.

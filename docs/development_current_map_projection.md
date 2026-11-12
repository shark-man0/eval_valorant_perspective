# Current Map hypotheses on the shared Source clock

This dependent development Draft builds on #117, #116 and #115. Round, life and
camera state remain defined and inferred only by `temporal.game`. The new
`temporal.map_projection` consumer reads the shared MapState and one-second views;
it has no state machine, tracking memory, position propagation or path builder.
Production/default recognizers, evaluation contracts, GT and fixed windows remain
unchanged. No main merge is requested.

## Current evidence and temporal continuity

Three regression cases demonstrated two different errors. An initial current
ALIVE/SELF observation could not expose a Map candidate while Round was UNKNOWN,
including after a confirmed source break. Conversely, a carried ALIVE/SELF state
could expose a candidate without a current owner observation when Round was BUY.

The common engine now requires current `owner_hud` evidence, resolved ALIVE/SELF,
no spectator/remote/death/downed conflict, no terminal Round hypothesis and no
decode failure. An UNKNOWN Round is retained as UNKNOWN. This permission concerns
an unqualified candidate in the current native image; it does not invent a Round
token, semantic continuity, recorder qualification or an intervening position.
Source breaks still reset temporal state, while valid new current evidence can
support a new current hypothesis. Failed decoding cannot support one.

The shared MapState adds:

- `current_view_contract = development_current_map_v1`;
- `current_recorder_view_evidence_ids`, pointing to original current observations;
- `temporal_path_eligible = false`.

`current_self_position_candidates` keeps exact native pool candidates selected by
the existing current-marker measurement. All pool and Zone candidates remain
available separately. The projection verifies observation digests, current
Source/native PTS/timebase/pixels/dimensions and membership in the exact native Map
pool. It emits original Map samples only; an exact-pixel alias in another
acquisition does not create another Map observation. Nearby timestamps are never
substituted. Its CLI admits every observation and frame through the DEVELOPMENT
Source policy before projecting.

Native rows retain full life/camera/Round estimates, uncertainties, original
sample identity, current-view evidence and marker IDs. Second rows retain the
common states and separate native Map views. Missing rows stay UNKNOWN; no
position is copied into another second. A Source-second can have UNKNOWN common
life because acquisition lanes disagree while still retaining an exact native
current candidate. That candidate is not promoted to the whole second. Paths are
always null and continuous occupancy/semantic continuity/ownership remain
UNKNOWN. Formal outputs remain zero.

## Reproduction and connection API

```sh
PYTHONPATH=.:src python -m valorant_ai_coach.temporal.map_projection \
  --policy /PRIVATE/policy.json --timeline /PRIVATE/new-run/timeline.json \
  --output /PRIVATE/new-run/current-map.json
```

The input is a shared timeline produced with the current MapState contract.
`project_current_map(timeline)` is the in-process API. Outputs are exclusive,
private artifacts outside Git. This consumer performs no video discovery or
decoding, and reads no human review answers. It consumes the engine's estimates
without redefining them. The previous supplier context API remains available and
keeps semantic continuity UNKNOWN; callers must not set it to continuous to force
the legacy tracker to accept a candidate.

## Fixed DEVELOPMENT comparison

The same pinned HUD reader remeasured all 140 existing native Map images using
the same original Source-wide recorder rosters, Profiles/references and thresholds.
Only private roster acquisition allowlists were extended to the exact new epochs.
No image, protected recording, new video decode or new truth label entered this
prediction experiment. Exact sample IDs replace 80 overlapping owner observations;
60 previously absent ones are added, without nearest-time matching.

Both old and corrected engines replay the **same 11,796 observations**, 11,402
acquisition frames and 11,308 physical points. All Round/life/camera estimates,
transitions, boundary candidates and Source-second state rows are identical.
The correction changes current Map candidate samples from two to six: one
carry-only candidate is removed and five directly supported current samples are
added. The removed point has no independent role truth; it is not a proven lost
correct label. These numbers measure evidence eligibility, not position accuracy.

| Measure | Old API, remeasured input | Current API, same input |
| --- | --- | --- |
| Native Map samples / unchanged pools | 140 / 140 | 140 / 140 |
| Current candidate samples | 2 | 6 |
| Round/life/camera UNKNOWN second bins | 963/1149/1137 | 963/1149/1137 |
| Changes to all domain estimates and transition/boundary records | 0 | 0 |
| Actual unchanged legacy Map consumer selections | 0 | 0 |
| Existing reviewed Map self-role losses still unresolved | 4 | 4 |
| Selected exposed three-point life/camera agreement | 3/3 and 3/3 | 3/3 and 3/3 |
| Formal Facts/Events | 0 | 0 |

Recorded same-input replay measurements are 7.228s / 493.1 MiB for the old API
and 7.409s / 499.0 MiB for the current API, excluding image recognition and output
writing. The new projection CLI separately took 4.943s / 635.4 MiB including
imports, input loading, validation, projection and output writing. These are
process reference measurements, not full-match decoder/recognizer E2E performance.
The complete private reproduction reran native-image UI measurement, exact-sample
replacement, all three replays and the actual legacy consumers. It reproduced
observations by ID and all semantic state/transition/projection outputs. Embedded
input artifact hashes and performance metadata remain bound to each run.

The new projection exposes six native candidate samples in four Source-second
bins and retains all 1,170 Source-second rows, including 1,166 UNKNOWN position
bins. It emits no paths or verified Zone/position labels. The unchanged legacy
consumer still requires semantic continuity and remains at zero selections;
the new current-only projection is an explicit development API, not a silent
change to that consumer.

Using the original observations with the new API yields zero current candidates.
Thus measuring the previously missing current HUD evidence and correcting the API
are distinct changes. The additional measurements change no previously known
domain values. Compared with the original observation archive, life/camera UNKNOWN
second bins change from 1151/1139 to 1149/1137. Counts of observations and lower
UNKNOWN totals are not recognition improvements.

All four older reviewed self-role controls still lack spectator-slot observability;
two also lack shared first-person HUD support. The Spike/UI control remains
blocked by current SPECTATOR evidence. No threshold was relaxed and no unread slot
was converted into absence. A separate one-frame role review of one new candidate
is kept private and outside prediction inputs; no result is assumed while its
answer is unavailable. General false attribution, position/Zone accuracy,
continuous recorder-episode truth and internal boundary timing remain unmeasured.

Related validation includes current-versus-carried evidence, initial UNKNOWN
Round, source-break reinitialization, conflicting/terminal states, failed decode,
missing seconds, exact native provenance, alias deduplication, candidate tampering,
foreign Source admission and original observation digest mutation. These tests
validate the API; they are not real-video recognition qualification.

All 143 related tests, full-source mypy (144 modules), the CI Ruff scope and
classified text-I/O pass locally. The dependent Draft requires its own exact-head
CI/Windows/package checks; #117 success is not reused.

HUD follow-up: improve actual spectator-slot observability and current HUD
measurements without inferring absence from non-detection. Map follow-up: consume
the shared current projection, evaluate marker/Zone candidates against exact
independent role evidence and preserve the four existing controls. Common owner:
maintain current-versus-temporal permissions, uncertainty and shared state
definitions, and evaluate independent temporal episodes. No supplier should
reimplement the state definitions.

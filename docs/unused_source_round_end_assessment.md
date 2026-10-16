# Frozen baseline End assessment on an additional unused recording

## Outcome and provenance

The previous blocker was lack of an unexposed End source. The user supplied an
additional original recording and explicitly confirmed it had never been used
for recognizer development/evaluation and was unedited. This resolves source
availability; it does **not** automatically qualify the existing model.

Source SHA256:
`06919642d69f68895ac123b505bfd7d3643dd28d903585008fcdc2b7f1b7e3fd`.
Metadata: 2329.266016 seconds, 3,641,953,546 bytes, H.264 1920×1080 at 60 fps,
video timebase 1/15360. This hash is absent from existing tracked source manifests
and aggregate reports searched; that search alone is not proof of exposure history.
The user's unused-source confirmation is recorded separately from this check.
No match_002 labels, source or profile are used.

Freeze before viewing/prediction: current commit
`f53e055f4f7f60cf02f84174b16f015d3f8946a8`, recognizer
`5b32ea0c5be3d23aadd5e1ef4057619c10c7104d3d210a69d39433bffea6dfc8`, guarded profile
`60b029cb987fe0d7447853e3b4cd791d5defb0918dfaa25a401bd45d2b64c813`, unchanged
reader/NCC thresholds and original training assets. Preregister the first
0–180 seconds as discovery/review candidate and the whole additional source as
**evaluation-only for this frozen baseline**. Do not fit on it. Any future fitting
on this source invalidates its blind status for that changed method. No original
label/split ledger was provided; new assistant source transcripts are not claimed
to be recovered historical labels.

## Source review before reader predictions

Use 13 approximate discovery images at frozen 15-second intervals. They identify
one first-End candidate with a Spike icon before numeric inter-round timer,
score changing 0–0 → 0–1, and a complete `LOST` caption. Approximate extraction
positions are not native PTS or End GT. Do not claim the whole 38-minute video
has been evaluated or that every End was located.

Then decode all **163** native frames in the explicit 72.8–75.5 second window:
integer ticks 1118208–1159680, step 256, original timebase 1/15360, one actual
decoder epoch, 384 MiB acquisition budget. Retain verified private raster copies
and original decoder source identities, encoded/pixel hashes. Temporary decoder
images are removed on exit; the private cache remains for review. Encoded window
payload is **274,451,572 bytes**; discovery/review images are additional storage.
No native epoch is joined to another window.

Before any reader prediction, freeze assistant visual transcription of 10 source
supports: timer representation, visible score and complete-caption presence.
Ambiguous animated captions are excluded from result comparison rather than
invented as complete. Supports represent **one physical End episode**, not ten
independent events. Four exact native supports are presented to the user for
independent source review; confirmation is pending at this checkpoint. These
assistant-transcribed labels are provisional evaluation evidence, not independently
approved full temporal GT. No canonical validation pack is made for this recording.

## Actual native system entrance fails safely

Try the unchanged `observe_native_system_frames` over the complete native window
with the preregistered 45–45.02 second native geometry prefix and the separately
user-assured contract for this new source. A prefix is geometry-only; it cannot
supply continuity, active Start state, player ownership or End proof.

Actual result: **HudNotCalibratedError: native calibration prefix lacks accepted
anchors**. End patterns are **unmeasured**, not zero false positives or a measured
missed-boundary rate. No qualified bundle, diagnostic substitute event or synthetic
Start is provided. No runtime event, Package or Trace is released.

Measured frozen prefix template scores:

| Anchor | NCC |
| --- | ---: |
| round_timer | 0.856257 |
| top_match_bar | 0.375829 |
| player_hp_armor | 0.558507 |
| abilities | 0.345901 |

All remain below the fixed accepted-anchor threshold. Do not search alternate
prefixes to obtain a favorable held-case result. The explicit failed attempt
takes **24.773 seconds**, after initial source/cache checks; process peak RSS
**100,663,296 bytes** (macOS process only; decoder-child RSS unmeasured).
Terminal source/profile/code/contract/label/image hashes pass.

## Component-only diagnosis, without geometry or event admission

Call the unchanged configured timer/score readers and semantic result reference
at their **original fixed ROIs** on the already frozen ten supports. This is
explicit component diagnosis despite failed geometry, never production observations
or a way around its guard. Save raw predictions before comparing labels.

| Diagnostic unit | Current result | Limitation |
| --- | --- | --- |
| Timer, seven numeric displays | 6 correct / 1 unknown / 0 wrong | Source supports from one exposed evaluation episode |
| Timer, three icon/blank supports | 3 rejected / 0 false accepts | Not three independent negative windows |
| Score, twenty field calls | 19 correct / 1 unknown / 0 wrong | Ten physical images, not twenty events |
| Complete LOST captions, four supports | 0 accepted / 4 unknown | One independent-source episode; human review pending |
| Four selected non-complete caption supports | 4 rejected | Same episode, not broad negative certification |

Two animated-caption supports are not scored as semantic result positives or
negatives. First comparator mistakenly compared score strings with integer labels,
which gave invalid wrong counts. Preserve that invalid comparator output; normalize
the **same immutable raw predictions** with current production
`_normalize_reader_value(..., 'int', ...)`, and evaluate once. No reader rerun,
threshold change, relabeling or unsupported value substitution. Diagnostic runtime
**8.715 seconds**, including separate prefix scoring/acquisition and terminal checks.

Confirm the actual production signal crop equals fixed diagnostic bounds
[842,178,1078,247], then inspect the existing measurement API on four complete
caption supports. Their result scores are all **0.0**. The frozen reference image
reads **TEAM ACE**, with seven glyph supports; the observed caption is **LOST**.
Per-group NCC and glyph-contrast checks reject it. This is a caption-family
coverage limitation, not evidence that a visible LOST is absent, a decoder-shape
mismatch or justification to lower NCC. Detailed private measurements preserve
the rejection evidence; no new reference/mask/glyph assets are generated.

The selected pre-End source contains no numeric clock before the post-End reset.
The current temporal method requires accepted numeric clock decrease before score
update, so Spike-icon cases require a separately designed/qualified source-backed
path. This is an analysis of method prerequisites, **not** an executed whole
active-Start→End producer failure or permission to infer an earlier boundary.

## Interpretation and next implementation conditions

Existing overall decision remains **B** for bounded match_001 Start evidence.
This added source does **not** qualify End, geometry transfer, the new input
contract's visual continuity, or full lifecycle. Do not update match_001 canonical
23/55/4 or the known approximately 3 ms End miss. Full E2E is unjustified.

The new failure materially narrows the work: the guarded profile has source-specific
anchor support, and its semantic reference covers TEAM ACE rather than every
Round result. Score recognition alone is insufficient. No algorithm changes are
made after looking at these evaluation outputs.

For a new implementation, declare the geometry and semantic-caption families and
Spike/numeric temporal method before tuning. Obtain separately allocated real
training cases for those families, preserve current fixed negatives and old
match_001 regressions, and evaluate untouched event-level held cases only after
freezing the new method. Reusing these viewed LOST supports as a new blind holdout
is prohibited. The current additional source can remain a fixed failed baseline
case; it must not silently become a passing tuned qualification cohort. Independent
human/source review and a complete same-epoch active path remain separate gates.

No production code, profile, thresholds, source bytes, ownership or GT change.
All private source frames, profiles, labels, exposure plan, logs and source contract
stay Git-ignored. Only aggregate evidence and hashes are published. All four
Linux/Windows jobs on f53e055 pass (8m13s / 15m24s Linux, 15m18s / 20m10s Windows).
The subsequent report-only commit has separate CI and does not inherit that exact
commit result. No new full local test rerun is required by these documentation-only
changes.

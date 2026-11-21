# Independent context and small coordinate reviews (development only)

`DevelopmentOwnershipEvidence` measures **current-frame screen evidence outside
the minimap**, retaining source/acquisition/frame identity, pixel and reference
hashes, cue families, and reasons. It does not establish recorder ownership.
`DevelopmentMapTimeline` optionally uses it to reject a candidate and break a path,
while preserving the caller's declared view and recording contradictions.
Production schemas, registries, HUD recognizers, Events and coaching are unchanged.

## Context evidence

Configure optional `development_ownership_evidence` in a private Map profile:

```json
{
  "mode": "screen_context_v1",
  "frame_size_px": [1920, 1080],
  "slot_review": "source_reviewed_not_qualified",
  "probes": [
    {
      "claim": "spectator_controls",
      "roi": [0.0, 0.8, 0.2, 0.9],
      "template_path": "/private/reviewed-switch-glyph.png"
    }
  ]
}
```

The ROI is illustrative, not a supplied calibration. Review exact screen slots
for each source/geometry first. One to eight probes use the existing bounded,
content-hashed screen matcher at NCC0.90. Supported claims are
`spectator_controls`, `death_report`, `menu_overlay`, and `first_person_hud`.
Invalid/missing references, mismatched frame size and any minimap overlap fail
closed. Optional `spectator_icon_roi` and `menu_close_roi` reuse the existing HUD
`detect_icon`/obscuration helpers **without modifying their implementation or
thresholds**. An icon slot requires an independent source-context geometry review.
These declarations are unqualified authoring attestations, not calibration proof.

- Switch controls/dedicated spectator structure suggest a non-recorder context.
  An overlay or configured unavailable probe vetoes the position candidate too.
- A death report can persist while spectating. It does not establish that the
  currently viewed actor, or the recorder at this instant, is dead.
- HP/ability/weapon HUDs are shared with spectators. Positive HUD patterns and
  unobserved spectator patterns cannot positively identify the recorder.
- Duplicate/correlated cues stay in one family. There is no vote count that can
  turn several template matches into independent ownership proof.
- Every result retains ownership UNKNOWN and `positive_recorder_ownership_evidence:
  false`. Unmeasured actor/death/self states remain unknown. Sparse human labels
  apply only to those exact frames; references and temporal continuity do not
  expand their scope.

No recognition result, previous UI state or previous transform is cached as
current evidence. Reference bytes are checked on every call. Changes in the
context-reference fingerprint break tracking in addition to the existing
source/acquisition/Profile/ROI/geometry/time guards. The feature is opt-in;
disabled profiles retain the existing recognition behavior.

## Coordinate review API

`compare_position_review` compares frozen candidate positions to a human-reviewed
ROI center and three corresponding reference corners. Each review binds source,
acquisition, exact frame/time, map/geometry, acquired frame hash, reference asset
hash and full prediction fingerprint. Pending/model-generated labels, fitting
labels, changed/mismatched anchors and collinear corners are rejected.

Results retain annotation tolerance, missing predictions, affine extrapolation,
and the distinction between ROI center difference and **approximate** Map-reference
difference. Few residuals never establish a transferable error radius, world
position accuracy, stationary jitter or population recognition precision.
`position_review` can attach this result to its one frozen record. Path analysis
rejects a mismatched attachment and breaks on a reviewed nonself/spectator/death
context. A reviewed SELF label does not promote automatic ownership or fill a gap.

The viewer shows current screen evidence, scoped human labels and measured
residuals. `coordinate_review_coverage` separately reports reviewed/unreviewed
points and edges with both endpoints reviewed. Even two reviewed endpoints do
not prove the route between them. Original candidate/Zone spans remain separate;
assumed boundary disks and motion parameters are still sensitivity assumptions,
not confidence bounds inferred from a few successful samples.

## Repeatable workflow for another video

First register/verify DEVELOPMENT eligibility with the private intake/exposure
ledger. Never use a protected evaluation candidate. Declare bounded native-time
windows and first/middle/last review ordinals **before predictions**; preserve
unsuccessful/negative windows. Acquire actual frames with native ticks and image
hashes, without interpolating frames. Separate references/fitting from comparison.

`scripts/development_map_benchmark.py` accepts already acquired images, explicit
DEVELOPMENT/exposure attestations, exact tick/time agreement and image hashes,
two private profile paths, source/acquisition identity and per-frame view evidence.
It performs no video scan/decoding, OCR, fitting, uploads or E2E invocation.
Declarations do not by themselves prove split eligibility; check the intake first.
Use short windows, one OpenCV thread, and a **fresh** private output directory
outside Git checkouts. The script refuses to overwrite frozen evidence.

```sh
PYTHONPATH=src python scripts/development_map_benchmark.py \
  --manifest /private/bounded-case.json --output /private/comparison-new
```

The manifest extends the [path replay format](development_map_paths.md) with
`exposure: DEVELOPMENT`, `native_time_base`, `baseline_profile_path`,
`variant_profile_path`, and per-observation `pts_tick`, `image_sha256` in addition
to source time, frame index, image path and declared view.

Outputs include both private viewers/observations, counts/timing/reasons and
implementation/Profile hashes. `review_packet_PRIVATE.json` selects fixed
ordinals and links raw source images, **without pre-filling predicted centers or
landmarks as GT**. Review only a few representative/high-risk cases; leave unclear
ones pending/UNKNOWN. Fill source-derived centers/corners and tolerances, mark
`human_confirmed`, and import against the original saved variant predictions:

```sh
PYTHONPATH=src python scripts/development_map_benchmark.py \
  --observations /private/comparison-new/variant_observations_PRIVATE.json \
  --reviews /private/owner-responses.json --output /private/reviewed-new
```

Import verifies anchors, computes scoped differences and regenerates the viewer
from cached frames without rerunning recognition or changing the frozen input.
All videos/images, individual positions/times, Profiles, review packets, JSON,
HTML and previews remain private. Publish aggregate results only.

## Bounded development evidence

Existing Bind198 retains ROI112, calibration149, Map70, named Zones3. Existing
Haven validation retains Map40/50, seven segments, longest2.6s. The prior
switch-pattern veto15/20 becomes20/20 contextual vetoes when the independently
located death-report evidence is included. The generic spectator structure is
retained as its own measurement; overlapping screen cues do not multiply identity
confidence. No automatic self ownership is established.

Four separately declared new six-second DEVELOPMENT windows give:

| Window role from source-context inspection | Baseline Map | With context evidence | Context veto |
|---|---:|---:|---:|
| Bind spectator/death display, 30 observations | 0 | 0 | 30 |
| Haven live-context candidates, 30 | 28 | 28 | 0 |
| Haven spectator context, 30 | 0 | 0 | 30 |
| Bind next-round context, 30 | 27 | 27 | 0 |

Negative windows deliberately receive erroneous upstream LIVE evidence to stress
the veto; this is not a measured Production false-attribution rate. Sparse context
inspection is not an all-frame human role label. The original negative Bind window
is retained; a separate predeclared next-round window tests coordinates without
searching until success. References come only from already exposed old scouts,
not new-window predictions. This is known DEVELOPMENT comparison, not independent
qualification. New automatic ownership remains UNKNOWN120, formal outputs zero.

The reusable review API reproduces prior independent source annotations: Bind has
3 reviewed observations, 2 available positions, ROI-center mean difference1.83px,
maximum2.24px, approximate Map-reference differences5.98–9.74px (mean7.86px).
Haven has3 reviewed observations/3 positions, ROI mean1.47px/max2.00px, approximate
Map-reference differences6.07–7.50px (mean6.96px). Annotation tolerance is2px on
source/reference corners. All three Haven references extrapolate outside their
landmark triangle; none of the Bind ones do. These are scoped comparisons, not
exact world GT. Unavailable predictions stay in the denominator.

Two additional fixed-middle source observations were independently confirmed,
with 2px annotation tolerances and landmarks bracketing the center. Bind has one
available candidate: ROI difference2.00px, approximate Map-reference difference
6.24px, without affine extrapolation. The fixed Haven observation has no predicted
position: it remains in the two-observation denominator, with error unmeasured.
Two high-risk spectator/death-display observations were separately confirmed as
non-recorder views and both contextual vetoes agree. These four labels apply only
to their exact observations; they neither fit references nor label whole windows.
No confirmed wrong attribution was found in these two negative checks; population
false-attribution and positive ownership precision remain unmeasured.

New Bind/Haven live-context paths have27/28 candidate points respectively, in
4/2 segments, with longest observed spans3.6/2.6s. Only the one available Bind
position has a new coordinate comparison; no path edge has both endpoints reviewed.
The new windows have no named Zone observations, so they add no measured Zone dwell
or transition evidence. Existing Zone/region spans remain unchanged. The viewer
keeps unreviewed endpoints and assumed boundary disks separate from measured
point residuals; no transferable accuracy bound is established.

On these four windows, recognition processing (excluding preview export) takes
7.50→6.76s, 7.81→8.00s, 7.07→7.06s, and7.56→7.72s for baseline→context respectively.
Single runs do not establish a speedup. Same-process peak RSS409.8MiB includes
multiple embedded-image viewer exports and is not isolated recognizer memory.
The unchanged198-observation replay takes36.12s, recognition peak164.9MiB, with
zero differences in the compared recognition/coordinate/tracking fields. The
remaining baseline Haven50/spectator20 replay also has zero compared-field
regressions. A final context-only replay preserves all decisions and scores;
its sole intentional metadata difference adds the generic icon to the existing
spectator cue family, rather than counting a new independent identity vote.

Remaining priorities are a recorder-to-current-view identity link with independent
support/exclusion evidence, robust positive context across HP/UI changes, more
independently reviewed coordinates near region borders, and transfer to another
registered Bind recording when one becomes available. No additional Bind recording
is currently claimed, and no unobserved route/Callout/Topology is invented.

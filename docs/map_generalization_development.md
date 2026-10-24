# Cross-recording Map development APIs

These APIs produce unassigned visual candidates. They never identify the
recorder, qualify a source, issue a Self Position Fact/Player Event, or score
positioning. The ordinary Production registry and recognizer are unchanged.
Acquisition registration, DEVELOPMENT allocation and Exposure logging remain
prerequisites handled by the existing dataset workflow. Neither a directory of
videos nor this API's input declaration is an allocation authority.

## Separate appearance, view and recorder identity

`PortablePortraitTracker` accepts an explicit `portable_portrait_v1` profile:

```json
{
  "mode": "portable_portrait_v1",
  "feature_mode": "gray_shared_v2",
  "templates": [
    {"path": "PRIVATE/portrait-a.png", "source_id": "author-a",
     "role": "portrait_appearance_only", "image_sha256": "EXPECTED_SHA256"},
    {"path": "PRIVATE/portrait-b.png", "source_id": "author-b",
     "role": "portrait_appearance_only", "image_sha256": "EXPECTED_SHA256"}
  ]
}
```

A reviewed teammate can contribute portrait texture to a different recording.
Its original semantic role is not transferred. The bounded pool has 2–48 PNGs
of identical odd geometry, 9–65 pixels, with content/texture validation. Every
observation rechecks reference bytes; content/profile/source-exclusion changes
reset tracking. `excluded_source_id` supports recording-excluded comparisons.
Private reference images and profiles must remain outside Git.

A candidate requires portrait texture, a spatial yellow annulus and inner
texture. Color alone, a tracking streak, or a best match among several supported
icons cannot assign a candidate. Multiple candidates and a truncated search are
UNKNOWN. The optional BGR and grayscale modes have separate fingerprints;
`gray_shared_v2` computes binary-mask normalized correlations with shared
current-frame statistics and bounded incremental response memory. It does not
reuse an old frame response. Floating-point and semantic parity must be checked
on an experiment's fixed inputs before switching modes.

For `DevelopmentMapTimeline`, portable profiles require
`coordinate_scope="unassigned_visual_candidate"` and
`reference_identity_confirmed=false`. Each observation requires source ID, SHA,
acquisition ID and an explicit unqualified view envelope:

```python
view = {"primary_state": "unknown", "values": {"view_state_unqualified": True}}
```

Independent death/spectator/purchase/overlay vetoes still apply. Missing vetoes
never prove a live recorder view. Outputs retain UNKNOWN ownership,
`position_subject="unassigned_visual_candidate"`, no qualified view state and
no formal fact. The existing path/benchmark CLIs accept the explicit profile
field `development_coordinate_scope` for this opt-in; old profiles keep their
previous behavior. The path manifest must include the real source SHA.

`DevelopmentRecorderView` additionally supports `agent_appearance_v1` without a
recorder binding. This mode rejects a supplied binding and reports visible Agent
appearance only. Source/acquisition identity remains required. Unknown Agent
vocabulary alone does not veto an unassigned Map candidate. Matching an Agent,
a shared first-person HUD, account identity and camera ownership are separate
claims; this mode never fills the latter two.

`ContrastiveAppearancePool` offers the separate `appearance_pool_v1` mode with
1–4 libraries, each declaring `source_id`, `role="appearance_contrast_only"`
and a `matcher` containing the existing positive/control template specification.
It automatically evaluates the frozen libraries without selecting a recording.
Original appearance thresholds and control margins remain intact. Multiple
successful libraries or ambiguity within any member remain UNKNOWN. Invalid
or missing controls invalidate the pool; changed reference bytes reset it.
Original self/nonself authoring roles never transfer to a different recording.
This mode also requires the explicit unassigned coordinate scope. A larger
unstructured portrait vocabulary and a contrastive library pool are different
experiments, not interchangeable identity evidence.

## Map coverage and acquisition

`DevelopmentOutlineMapSelector(map_ids=(...))` compares the current image against
all explicitly configured development Maps. One accepted outline yields a
geometric Map candidate; two accepted Maps remain UNKNOWN even when their
scores differ. No nearest-map fallback is used. A timeline must still calibrate
each current frame. Source/epoch changes discard frame alignment and tracking.
Only immutable reference preprocessing survives those changes: analyze rechecks
its content SHA, geometry and actual ROI-shape key, with the existing memory cap.
No transform or previous-frame response survives. Explicit reset still clears
all work. Map identity and client-build correspondence are unqualified.

The isolated development bundles now include Bind, Haven, Lotus, Corrode and Summit.
The additional public references use lossless, fixed authoring rotations
(Lotus CCW180; Corrode CCW270; Summit unchanged). Summit orientation is
independently anchored to the pre-existing registered reference, and its new
development bundle does not activate or change Production zones. Their provenance files contain upstream URLs,
original/reference/visible-floor SHA-256, coordinate bbox and Site-anchor
transforms. Zones are only the public shaded footprint exteriors assigned
one-to-one to published Site anchors. They are not whole Sites, authoritative
plantability, callout boundaries, topology or visibility. There are no registered
client builds; strict alignment failures remain `calibration_required`. Public
reference version differences and unsupported rotation/cropping remain failure
conditions, not reasons to loosen acceptance.

`map_sampling_targets` provides a content-blind, bounded coarse timeline and
three short dense windows. Freeze the requested grid before image inspection;
retain failures in its denominator. An actual decoder must select and verify
native PTS rather than manufacture ticks from FPS. Separate native acquisitions
remain separate epochs. Discovery images with frame-index/FPS offsets can be
used for spatial failure exploration, but must retain NULL native time and
cannot establish continuous paths, durations or Round associations.

## Paths and Round candidates

The existing viewer displays unassigned subject/view qualification alongside
position, ownership evidence and uncertainty. Dashed chords join adjacent
observations only; they are not recovered routes. Missing observations, source,
acquisition, reference/profile, geometry, ordering or speed discontinuities
break paths. Zone-boundary uncertainty and assumed error radii do not become
continuous dwell time or qualified precision.

`associate_lifecycle_witnesses` consumes explicit offline candidate witnesses;
it does not import or change HUD contracts. Association requires identical
source ID/SHA, native tick/time base, acquisition epoch, encoded-frame SHA and
pixel SHA. Nearby times, another decode of the same PTS, missing identity and
conflicting candidate/phase claims remain unassociated. Even a match assigns
neither a Round ID nor recorder ownership. Associations apply only to that
observation and never fill intervals.

## Experiment interpretation

Compare reference coverage, Map registration coverage, feature changes and
additional sampling separately. A larger catalog can reduce retrieval by
creating ambiguity; do not accept it merely because it finds more raw matches.
Reference authoring observations are excluded from effect measurements. Known
DEVELOPMENT replays and recording-excluded DEVELOPMENT tests are not independent
qualification. Candidate counts, correct refusals, verified misattributions,
UNKNOWN, annotation differences and unmeasured absolute precision must be
reported separately. Private per-recording positions, PTS, profiles, images and
HTML must not be uploaded with public aggregate reports.

## Development comparison snapshot

Ten registered DEVELOPMENT recordings (five newly registered) supplied 1,330
observations: 979 native-time observations and 351 previously acquired discovery
images with unverified offsets. Dense-window starts can repeat a coarse native
frame; these are observations, not independent precision trials. Registration
and acquisitions retain source SHA, physical-match identity, allocation and
Exposure provenance. Protected recordings were not used for Map development.

The automatic contrastive library pool returned 143 Map candidates, compared
with 150 from the development-only union of the unchanged legacy matchers.
Seven additional ambiguous candidates were withheld; their correctness is
unmeasured, so this is a safety tradeoff rather than an accuracy gain. The
new-recording portion returned 58/529 with either pool. New Map coverage, extra
sampling and appearance changes are separate contributions. A broad public
portrait catalog was not adopted as a default: its transfer recording retrieval
was worse, including after a second rendering experiment.

On a separate previously reviewed 30-observation Haven repeat, the optional
reviewed-portrait grayscale pool increased Map candidates 27→30, Named Zone
resolutions 15→20 and longest observed segment 4.0→5.8 seconds. Three existing
independent center/landmark annotations gave ROI differences 1/0/0 pixels and
approximate reference-image Map differences 1.16–1.35 pixels. Two annotations
share a stationary location. Their stated annotation tolerances remain 2 pixels;
these are not world-coordinate precision, population accuracy or an error bound
for other frames. The 18 reviewed stationary observations remain 18/18 with zero
observed diameter, which does not mean zero absolute error. No new human review
was requested. Automatic recorder ownership and formal outputs remain zero.

On the fixed 529 new-recording inputs, shared grayscale statistics preserved
candidate coordinates/status/rejections/tracks in every observation. Matcher
time was 122.63→34.51 seconds in one paired Mac run, with maximum accepted score
difference below 0.000004. This is not a qualified speed guarantee. Existing
198-observation results (ROI112/Map70/Named3), Haven50 Map40, earlier Bind/Haven
30-observation results and spectator controls were replayed without recognition
regressions. Detailed inputs, native times, individual positions, uncertainty,
comparison failures and viewers remain private.

These opt-in development bundles and CLIs are used from the source checkout.
They are not added to the ordinary packaged Production Map registry.

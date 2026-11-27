# Comparing recorder evidence across DEVELOPMENT recordings

These opt-in Map/Visual APIs retain ownership UNKNOWN. They do not change HUD
recognizers, Production contracts, GT, registries or qualification thresholds.
See [source binding and frame review](development_recorder_view.md) for the
existing source-specific recorder roster and exact sampled-frame review contract.

## Glyph features and context

`development_recorder_view.glyph_feature_mode` defaults to `gray_v1`. The optional
`positive_contrast_v1` suppresses broad background lighting before matching:
subtract a Gaussian background (sigma3 pixels), retain positive residuals, then
smooth with a3x3 Gaussian (sigma0.6). Both source crop and template use the same
transform at the exact reviewed frame geometry. It is still one correlated
HUD-agent evidence family, with the unchanged NCC0.90, runner margin0.12 and
two-disjoint-glyph requirements. An incomplete vocabulary can remain ambiguous.

This addresses background-dependent matching, not identity or the meaning of a
glyph. Reference file bounds/contrast checks remain enforced. Cache keys include
the feature mode and content SHA; missing/replaced references cannot keep stale
features. Changes to the Profile or fingerprint break development tracking.
No transform, ownership or predicted position is carried forward.

`DevelopmentOwnershipEvidence` also accepts an optional `purchase_phase` probe.
It positively observes an authored purchase banner outside the minimap, rather
than inferring purchase from absent combat UI. A probe can opt into the same
feature transform. Purchase presence blocks the live candidate path and breaks
tracking. Banner absence remains unknown; it does not prove a live phase or a
recorder view. The feature and context probes must be evaluated separately: more
agent matches in purchase/death frames are not more successful self recognition.

## Separate evidence factors

Set the private Profile's `development_identity_assessment: true` to include
`recorder_view_evidence.identity_factors` and trajectory `identity_outcomes`.
The viewer presents agent association, shared first-person HUD observations,
current-name support, missing qualified actor/view evidence and human labels
separately. A shared first-person HUD also occurs while spectating. Even an
exact display alias match is not a qualified, unique account/camera link.
Neither correlated probes nor human labels automatically promote ownership.

`summarize_reviewed_identity(records)` checks each optional `view_review` against
the frozen prediction and acquired frame hash. It reports separate groups for
SELF_LIVE, SELF_PURCHASE, SELF_PHASE_UNKNOWN, PURCHASE, DEATH, SPECTATOR, UNKNOWN
and unreviewed frames. SELF_PHASE_UNKNOWN preserves a human-confirmed recorder
view when the sampled frame's live/purchase phase was not independently specified.
It earns neither live-self support nor non-live rejection credit. It breaks the
reviewed candidate path without erasing the frozen position candidate; a model's
purchase-banner prediction must not supply the missing human phase label.
It distinguishes:

- agent correspondence and eligible-view support candidates;
- human-reviewed live-self support candidates;
- explicit context rejection of reviewed non-live frames;
- non-live position/support candidates that escaped context rejection;
- unreviewed samples and missing account-ownership qualification.

A position missed only by its appearance matcher is **not** credited as correct
context rejection. Missing references, marker-authoring mismatches and upstream
view declarations are counted separately from observed context rejection.
A new reason on a previously rejected position is additional
evidence, not a measured attribution improvement. DEATH/PURCHASE labels describe
view state; they do not by themselves identify another account. Qualified self
counts stay0 and qualified account misattribution rate is unmeasured.

## Stationary spread and missing points

`compare_stationary_review(records, review, reference_size_px=...)` measures
diameter and RMS spread about the mean only for explicitly listed samples whose
stationarity has been independently reviewed. The review must declare:

- `status: human_confirmed`, `label_origin: source_stationary_sample_review`;
- `not_used_for_fitting: true`, `sample_scope: listed_observations_only`;
- exact ordered `prediction_sha256` and acquired `frame_sha256` lists, including
  frames where the position was missed.

The output anchors the review SHA and preserves missing observations. Missing
points and context/acquisition/time discontinuities split runs. A single-point
run has no measured spread. The API neither smooths predictions nor interpolates
gaps, and its observed spread is not absolute position error, a transferable
accuracy radius or proof of continuous stationarity between sampled frames.
Do not assert stationary GT merely because predicted positions look stable.

The existing review CLI accepts optional `stationary_reviews` objects with these
fields and ordered unique zero-based `observation_indices`. Reports are included
in the private JSON and viewer. They do not modify the frozen recognition output
or provide points to a candidate path. A review whose every position is missing
still reports its full sample count and misses.

## New-recording comparison

Use the common intake, allocation and Exposure ledger before content access.
Only accepted DEVELOPMENT sources and explicitly allowed acquisitions may enter
Profiles. Each source needs its own recorder/agent and marker-reference review;
a roster binding cannot repair another agent's minimap template. Retain failures.

An optional `development_marker_binding` guards explicitly reviewed marker
references with `source_id`, `source_sha256`, `recorder_agent_id`, `review_sha256`
and the `SelfMarkerTracker.reference_fingerprint`. When a position would otherwise
be eligible, a mismatch blocks its coordinates and resets tracking. The reference
fingerprint includes actual content, mode and paths. A blocked-view frame does
not imply that its reference binding has been freshly measured. This guard is an
authoring boundary, not semantic or Production qualification.

Freeze methods/references separately from comparison windows. Declare window
times, sample frequency and coordinate-review ordinals before scoring, including
misses in the denominator. Human responses are attached to individual actual
frame hashes and may be imported against each frozen method's predictions without
feeding them into recognition. Never treat known DEVELOPMENT replay as independent
qualification. Mark reference-authoring observations and use separate intervals
for subsequent performance comparison.

Report by source, acquisition and human view role. Include raw candidate counts,
explicit rejection, unreviewed/UNKNOWN, missing points, candidate segments,
coordinate residuals/boundary sensitivity, elapsed time and memory. Keep individual
times, positions, aliases, Profiles, images, HTML and video private; publish only
aggregate measurements. New ordinary VODs help measure transfer and failure modes,
but qualified recorder ownership still needs independent current-actor identity
and view-state validation.

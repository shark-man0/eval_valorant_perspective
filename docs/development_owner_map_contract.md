# Offline HUD owner-state and Map integration

This opt-in experiment connects current image UI readers to the existing
`DevelopmentSelfTimeline`, then injects a marker provider into
`DevelopmentMapTimeline`. It has no Production entry point or formal Event/Fact
output. It does not change the default Map tracker or HUD thresholds.

## Inputs and provenance

`DevelopmentOwnerMapPipeline(profile, tracking="local" | "legacy").observe(...)`
requires a BGR uint8 image, frozen native sample, and the existing accepted
DEVELOPMENT `FrameRecord`. The caller verifies private registry/allocation hashes
and encoded frame bytes. The adapter verifies current pixel SHA, integer PTS,
rational timebase, Source/acquisition identity, Profile/reference fingerprint,
Exposure scope and Map build. Receipt-backed adjacency is required for carry;
missing receipts, cuts, duplicate PTS, a gap above 0.3 s, or changed context reset it.
A native cadence receipt is not proof of semantic continuity or ownership.

`cached_ui` must have the current reader/Profile/reference fingerprint and exact
sample binding. `initial_review` optionally imports an existing exact-frame human
SELF_LIVE review. It is a separately reported initialization ablation, not an
automatic detector, qualification label or per-frame answer.

## Owner and camera evidence

Life, camera and round hypotheses remain separate. The current UI producer reuses
agent association, shared first-person HUD, spectator, Report and purchase readers.
A shared HUD or agent appearance alone does not identify the recording account.
Unobservable spectator pixels do not become verified absence. Remote view,
direct death animation and special return detectors are unconfigured and must
remain unverified on real video.

Killfeed roles and Combat Report presence/persistence/reappearance never assert
owner death. An anchored self-to-spectator edge may produce one inferred death
candidate with native endpoint evidence; it is not an internal death timestamp.
An unanchored spectator observation has no observed death boundary. The reused
state machine retains its reentry latch across contradictory/repeated own-HUD
observations after death/downed/spectator; revival and round reentry require
positive cues. Synthetic exception coverage is not real-video validation.

## Initial marker identity versus tracking

Initialization needs a current or continuously inherited owner anchor AND a
Source-reviewed marker/UI reference binding. A failed first marker observation
does not discard a still-valid owner anchor. Its provenance remains explicit.
After initialization the experimental provider searches a bounded local region,
uses the authored portrait foreground, retains existing reference and nonself
separation gates, and additionally requires temporal appearance and uniqueness.
It does not select a new owner from all candidates each frame.

A short missing appearance retains an ID without coordinates. Missing current
pixels, blocked Geometry, ambiguity or a jump never emits an interpolated point.
Death/spectator/remote/contradiction and changed context stop tracking. Reentry
requires a new owner/marker association. All coordinates, nested ZoneResolution
and route edges retain UNKNOWN ownership and development-only qualification.
Route edges are chords between observations, not recovered walkable movement.

## Fixed development comparison and decision

Three previously registered development sources supplied 263 existing native
images, including 80 Map observations and three reviewed short self-death-negative
windows. No protected evaluation video or new human label was used.

Automatic owner initialization failed on the reviewed live sequence. Shared HP
pixels varied with the displayed value, the ability signature lacked sufficient
support, and the spectator slot was unobservable. Neither raw-gray matching nor
existing oriented-edge glyph matching resolved the ability signature under the
unchanged thresholds. Automatic owner/Map accuracy improvement is **not shown**.

With one exact human live-view initialization, the following 29 reviewed live
frames were retained as alive/self. This is conditional temporal utility, not
automatic initialization or an independently qualified episode. The known live
sequence produced 27 Map coordinates / 15 named Zone observations with the legacy
provider, and 24 / 13 with the local provider. Both agreed with the two subsequent
human coordinate checks under their existing tolerance; there was no additional
confirmed correct coordinate. The local provider is therefore **not adopted as
the default**. The fixed input comparison exposed its remaining appearance loss.

The tested spectator/death-display sequences produced no own-position candidates;
unreviewed frames are not included in a semantic accuracy denominator. A complete
live-to-death-to-spectator-to-return episode remains unverified. Formal qualification
and Production adoption remain out of scope.

## Reuse and incremental inputs

The existing `DevelopmentFeatureCache`, `append_snapshot` and trial history carry
Source/pixels/PTS/Exposure/Profile/build fingerprints. Stateful results additionally
need a fingerprint of the complete ordered input prefix, continuity receipts and
initial review; a per-frame cache key alone is unsafe. Store full private envelopes
with content hashes alongside bounded cached features and reject changed evidence.
New videos enter through existing registration/allocation before this adapter.
Physical groups must remain isolated across training/comparison splits. Cache hits
and accumulated data are processing results, not recognition gains.

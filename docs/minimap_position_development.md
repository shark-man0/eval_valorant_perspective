# Minimap appearance positions: development experiment

This page preserves the initial appearance-v1 milestone and its original
measurements. The subsequent portrait-v2 / Bind coordinate milestone is in
[Bind development map](bind_development_map.md). Its isolated development map
does not change the production registry described below.

The current default path has no self-marker profile. Static map calibration
cannot supply a player point, and the production registry contains only Summit.
Two bounded DEVELOPMENT recordings also have different minimap geometry from
the registered reference. They must stay unresolved rather than be assigned
Summit. Existing calibration, `ZoneResolver`, and `MapEventConsumer` are reused;
no new map, zone system, movement event, or scoring rule is introduced.

## Implementation and use

`visual/self_marker.py` implements fixed-scale, textured portrait matching with
positive and nonself reference PNGs. Color equality alone cannot accept a
proposal. It requires NCC >= 0.80, a 0.12 margin over spatial alternatives and
nonself controls, and a unique spatial candidate. It resets on missing evidence,
blocked ownership, frame-size change, gaps > 0.3 seconds, duplicate/out-of-order
timestamps, or jumps > 0.4 ROI units/second. Three consecutive measured points
are needed for `tracked`. Track IDs never bridge a rejected observation, and
missing points are never interpolated. The speed limit is a development guard,
not a game-speed model; teleportation and changing minimap transforms can break
tracks.

Opt in through an explicitly supplied Visual profile:

```json
{
  "validated": false,
  "rois": {"minimap": [0.01, 0.04, 0.25, 0.44]},
  "minimap_self_marker": {
    "mode": "appearance_v1",
    "positive_templates": ["private/portrait.png"],
    "negative_templates": ["private/teammate.png", "private/icon.png"]
  }
}
```

The example ROI is illustrative; inspect the actual recording before use.
References must be textured, odd-sized PNGs, 9..65 pixels in each dimension,
all with the same dimensions. At most four positive and eight negative
references are accepted. Use full-frame source context to select references;
do not use a predicted location or zone as an identity label. Keep reference
assets private and freeze their provenance before comparing results. The
profile loader resolves relative paths and the analyzer fingerprint hashes
reference contents, preventing old checkpoints from silently reusing new assets.

`PixelMeasurementExtractor.measure()` exposes measured coordinates through
`measurement_meta.minimap_self_observation`. The standalone `SelfMarkerTracker`
can also process ROI images directly. A caller can save each `to_dict()` result
alongside its original source timestamp; only actual matched points are returned.
`x_roi_norm` and `y_roi_norm` are relative to the **ROI**, not to a map mask or
world coordinates. `appearance_score` is a similarity score, not a probability.
`candidate_count` counts spatial local maxima above threshold, including rejected
ambiguous proposals. `status` is `candidate`, `tracked`, or `unknown`.

Every result retains `identity=UNKNOWN` and `qualification=development_only`.
The profile does not authorize identity or view ownership. The extractor also
requires existing live-first-person/player-HUD eligibility and blocks known
nonself views and transition/buy/end flags. The direct tracker API requires an
explicit external eligibility decision. That decision must not be inferred from
portrait similarity. In this opt-in mode, even `validated=true` cannot promote
positions into strict minimap self fields, displacement, Zone facts, or scoring.
The ordinary analyzer result schema is unchanged; callers doing development
capture the measurement metadata, rather than reading it as a gameplay fact.
Legacy profiles retain their existing behavior; the old color-only path is not
newly qualified by this change.

## Bounded recording comparison

Two DEVELOPMENT recordings, one short interval each, 5 sampled frames/second,
100 observations total. The first observation of each recording supplied one
positive and two nonself references. The following table excludes those two
reference observations. Source selection and preliminary template probes were
exploratory; the method and comparison plan were subsequently frozen. This is
same-recording development evidence, not a blind test or independently qualified
recognizer. Full videos, profiles, frames, per-case identifiers, timestamps,
source hashes, source-context notes, and the exposure journal remain private.
The four qualification/final-holdout candidates were not opened.

| Measurement | Before | Candidate |
|---|---:|---:|
| Comparison observations | 98 | 98 |
| Source-reviewed view-eligible observations | 76 | 76 |
| Accepted map calibrations | 0 | 0 |
| Appearance candidate proposals above threshold | not evaluated | 34 |
| ROI position observations | 0 | 34 |
| Observations with >=3 consecutive measured positions | 0 | 17 |
| Independently established self identity observations | 0 | 0 |
| Map-mask coordinates / Zone resolutions | 0 / 0 | 0 / 0 |
| Coordinate-free candidate results | 98 | 64 |
| Identity UNKNOWN | 98 | 98 |

The candidate positions comprise 16 observations from one recording and 18
from the other. Of 64 results without coordinates, 42 fail appearance similarity
and 22 are blocked by source-reviewed ownership context. The 34 emitted
positions have 11 track segments; the longest uninterrupted segment spans
2.0 seconds (11 observations), so continuous movement reconstruction remains
incomplete. Reference observations are excluded from these counts and segments.
Visual inspection of the emitted position overlays found no obvious switch to
a different icon, but this is developer review, not pixel GT or a measured
localization error/precision estimate.

The interval includes 22 death/report/spectator observations. They produce zero
coordinates with the contextual gate; a separate permissive stress replay also
returns zero positions for these observations. This small exposed control set
does not establish a false-attribution rate. Context eligibility in this
experiment was supplied by developer source inspection, **not** an automatic
HUD recognizer or human-certified GT. No unobserved enemies, ally actions, or
lines of sight were generated.

Single-process measurements on the same Mac, one OpenCV/decoder thread:

| Resource (100 observations, including references) | Before | Candidate |
|---|---:|---:|
| Pixel measurement time | 1.19 s | 1.90 s |
| Map calibration attempts | 3.14 s | 3.18 s |
| Peak process RSS | 138.9 MiB | 147.6 MiB |

These are one-run timings, not throughput guarantees. Peak RSS includes loaded
frames and, in the candidate process, an additional permissive stress tracker.
Acquisition, image I/O, and the stress replay are excluded from the pixel timing.
No whole-video recognition or concurrent large decoding was run.

## Zone connection and next work

The real-video connection reaches the existing resolver, but both maps remain
unselected and all map coordinates/zones remain unknown. A separate synthetic
reference-image integration test accepts actual SIFT calibration, measures the
appearance position, and verifies that the unqualified position still cannot
become a Zone fact even with `validated=true`. Existing qualified synthetic
color/calibration/resolver/event tests remain unchanged. Synthetic success is
not a real-video Zone accuracy result.

Priorities:

1. Source-review a small set of full-frame identity anchors and similar nonself
   controls; separate appearance identity, view ownership, and qualification.
   Improve orientation/overlap robustness and continuity on DEVELOPMENT only.
2. Add the actually observed maps with reviewed reference/mask geometry, build
   provenance, zones and topology using the existing registration procedure.
   Do not infer their geometry or map ID from a desired Zone result.
3. Connect independently supported ownership and calibrated map transforms;
   measure localization error and cross-recording performance before authorizing
   any production self/Zone field. Qualification candidates stay closed until
   the qualification protocol is explicitly ready.
4. Once reliable positions exist, use existing zone dwell, path and rotation
   consumers. Ally relations need separate observed ally identity/tracks;
   isolation and GOOD/IMPROVE additionally need reliable situation evidence.

Related: #22 remains a separate confidence-contract decision; Fact confidence
and schema semantics are unchanged. #32 remains open; these candidate ROI
positions do not qualify any of the 44 coaching rules. HUD, Round End, Self Death,
canonical datasets, registered map geometry, and other workers' files are not
changed by this implementation.

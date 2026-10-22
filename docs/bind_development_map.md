# Bind positions and plant footprints: development milestone

The opt-in `DevelopmentMapTimeline` now extracts measured portrait candidates
from real DEVELOPMENT footage, converts them into registered Bind map-mask
coordinates, and feeds the existing `ZoneResolver` and `MapEventConsumer`.
The separate development envelope always retains `identity=UNKNOWN`,
`qualification=development_only`, and `formal_self_position_fact=null`.
Human confirmation of a few source examples is recorded separately; it is
neither an automatic ownership classifier nor recognition qualification.

## Implementation

`portrait_v2` matches the textured central portrait with masked normalized
correlation. This reduces sensitivity to a changing external direction wedge
and overlapping icons. The original `appearance_v1` remains available. Both
require similarity >=0.80 and a 0.12 margin over spatial alternatives and
nonself templates. Duplicate matching portraits remain UNKNOWN. A track is
continuity evidence, never ownership evidence. The smaller mask can lose role
information; an identical portrait in a nonself context is still a known risk.
There is no qualified enemy/teammate/ping/spike/ability classifier.

`OutlineMinimapCalibrator` searches scale and translation of the whole public
map footprint. It requires unique alignment, bidirectional edge support and
support in every quadrant. It rejects missing/partial/rotated/skewed/wrong-map
geometry in tests. It does not recover rotating or zoomed partial minimaps.
SIFT remains the ordinary runtime calibrator. Similarity/calibration scores are
heuristics, not calibrated probabilities or localization accuracy.

`DevelopmentMapTimeline` explicitly requires an identified map, a minimap ROI,
private positive/nonself templates, and independent view evidence. Only an
eligible live-first-person view can emit a candidate point. Transition,
buy/end banners and nonself/unknown views block it. The experiment supplied
view evidence through source inspection, not a qualified HUD recognizer.
Coordinates are normalized within the registered reference-mask bounding box;
they are distinct from ROI coordinates and are not world meters or a 3D map.
Points outside the public visible-floor raster are rejected.

Tracks break on absent measurements, gaps >0.3 seconds, out-of-order time,
changed appearance tracks, or jumps >0.4 normalized map units/second. Missing
intervals are never interpolated. Zone dwell and the existing consumer reset
on gaps; the consumer also resets while Zone is UNKNOWN. The speed threshold
is a development guard rather than a physical player-speed model.

## Registration and provenance

`config/map_zone_development/bind` is an isolated non-production registry using
the canonical schemas and runtime contract. The default Summit registry and
its geometry are unchanged. A custom registry root alone cannot enable this
bundle through the ordinary application path; the developer loader explicitly
supplies the canonical schema directory. `MapRegistry(schema_root=...)` and
`MapTimeline(registry=...)` are optional injection points with unchanged
defaults. No shared schema or HUD code changed in this milestone.

Map identity uses the [official Bind map page](https://playvalorant.com/en-gb/maps/).
The reference PNG and callout-point metadata come from the public
[Bind asset API](https://valorant-api.com/v1/maps/2c9d57ec-4431-9c5e-2939-8f9ef6dd5cba).
`provenance.json` preserves upstream URLs/UUID, hashes, extraction recipes and
limitations. The reference is a public asset, not a private recording frame.
Its upstream game build is unknown. A client build was read privately from a
source frame; that does not date the published asset. Runtime correspondence
is mandatory and `client_build_unverified` remains visible.

The map contains exactly two reviewed polygons: the visible A/B shaded plant
footprints. They are **not the full A/B sites**. Boundaries are contours of
the public shaded regions, with at most one source-pixel simplification.
The recording owner confirmed Bind and this limited region interpretation.
All other areas return Zone UNKNOWN. Public callout anchors are preserved as
unmapped provenance, not invented callout polygons. Active callouts and
topology edges are empty. No corridor, spawn or teleporter connectivity is
fabricated. The operational QA mask covers only an independently eroded A
plant core; its coverage result says nothing about whole-map Zone coverage.
The visible-floor raster records 2D texture support, not 3D walkability or LOS.

## Developer use

This API and development assets are used from a source checkout. The ordinary
packaged application's resource set and production selection are unchanged.

```python
import cv2
from valorant_ai_coach.visual.development_map import DevelopmentMapTimeline

cv2.setNumThreads(1)
# Private profile: inspected ROI, positive/nonself PNGs, and explicit Bind ID.
profile["minimap_self_marker"]["mode"] = "portrait_v2"
profile["map_zone"] = {"manual_map_id": "bind"}
timeline = DevelopmentMapTimeline(profile)
result = timeline.observe(
    frame, source_time_sec, source_frame_index,
    view=independently_observed_view,
    evidence_kind="source_review",  # or "unqualified_hud_observation"
)
# Persist only as private development evidence, separately from formal facts.
```

`view` uses existing `primary_state`, `values.player_specific_hud_valid` and
`state_flags`. Callers must not derive it from the portrait prediction.
Freeze profile/reference hashes, model/config/asset hashes, source exposure and
view-evidence provenance before evaluation. The standalone API does not create
VisualObservations, RoundPackages, production self/Zone facts or coach scores.

## Bounded recording comparison

Two DEVELOPMENT recordings were used; the four evaluation candidates remained
closed. Two reference observations are excluded. The initial two windows are
exploratory regression data. Two additional bounded windows on the same Bind
recording were acquired after freezing templates and method parameters. The
first was buy phase and is retained as a blocked-view control; the next was
selected from the buy countdown context, not marker/Zone predictions. These
are same-recording development checks, not independent qualification. No
threshold or template was fitted to the additional windows.

The comparison replays each method from a fresh tracker and uses the same view
gates. The baseline is appearance-v1 plus SIFT with the same public Bind
registration; the candidate is portrait-v2 plus outline calibration. The other
map remains unregistered and is never forced into Bind. Per-case sources,
profiles, frames, exact times and hashes remain private.

| Measurement | Baseline | Candidate |
|---|---:|---:|
| Scored observations (references excluded) | 198 | 198 |
| Source-reviewed view-eligible / blocked | 126 / 72 | 126 / 72 |
| Above-threshold spatial proposals | 50 | 117 |
| ROI positions | 50 | 112 |
| Appearance observations with >=3 consecutive points | 22 | 91 |
| Bind calibration accepted / attempted | 0 / 149 | 149 / 149 |
| Unregistered-map observations (no forced calibration) | 49 | 49 |
| Registered map coordinates | 0 | 70 |
| Named Zone resolutions | 0 | 3 |
| Automatic ownership UNKNOWN | 198 | 198 |
| Formal self position facts / development events | 0 / 0 | 0 / 0 |

The initial two windows yield 34 -> 68 ROI points; the additional eligible
window yields 16 -> 44. The candidate has 86 coordinate-free appearance
results: 72 view-blocked, nine below threshold and five spatially ambiguous.
All blocked views emit zero points in this gated replay; this does not measure
an automatic spectator/death detector's false-attribution rate. Forty-two ROI
points belong to the unregistered map and remain without Map/Zone coordinates.
The 70 Bind map points form seven uninterrupted segments, six with >=2 points;
the longest has 28 observations spanning 5.4 seconds. No missing interval is
counted as path continuity. All three named resolutions are A plant footprint;
the added window is outside the limited polygons and has no named Zone.

Single-process, one-thread replay excluding decoding/image I/O: baseline
processing 5.13 seconds, candidate 55.24 seconds for 198 observations. Peak RSS
was 332.6 / 122.0 MiB respectively, including image buffers and algorithm
allocations. These are one-run measurements, not throughput or memory
guarantees. The whole-footprint search is materially slower and remains an
opt-in bounded experiment. Acquisition used one decoder thread in short
intervals rather than whole-video processing.

Two source-reference examples and three separate validation examples were
confirmed as self by the recording owner. Only those five examples carry that
human label; the validation subset has three self and zero confirmed nonself
cases. This is not a measured population precision or false-attribution rate.
Every automatic ownership output remains UNKNOWN. Exact coordinate GT is
absent, so real-video position accuracy is **unmeasured**.

The named Zone resolutions demonstrate real-video pipeline flow into the
limited plant polygons. They do not independently validate coordinate accuracy
or full-site coverage. No enemy positions, unseen ally actions or lines of
sight are inferred. Existing event consumers are connected; no GOOD/IMPROVE
rating is authorized by these observations.

## Next priorities

1. Independently review same-portrait nonself/spectator controls and strengthen
   per-frame ownership/view evidence before promoting any self field.
2. Measure coordinate error on a small independent set of manually checked
   source points; verify cross-recording settings and build correspondence.
3. Register the other observed map with source-backed orientation/geometry;
   expand Bind Zone boundaries/topology only with reviewed evidence.
4. Validate longer continuous paths, stopping/moving, Zone dwell and site entry.
   Rotations require authored connecting zones/topology; ally relations require
   separately observed ally identities/tracks. Situation ratings remain later.

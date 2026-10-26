# Unassigned cross-shape observations

Add an opt-in shape observer to PR #87's exhaustive marker backend. A single
confirmed development appearance supplies a **private color profile**; four
opposing diagonal arms and weaker axial controls supply shape evidence. Matching
color alone is insufficient. This covers some minimap cross appearances that the
portrait/rim proposal paths miss, without changing either detector's defaults.

```python
from valorant_ai_coach.visual.development_marker_cross import (
    DevelopmentCrossMarkerProposals,
)

# appearance_profile is an explicit, private dict, not a recorder identity.
engine = DevelopmentCrossMarkerProposals("bind", appearance_profile)
# Same frozen native sample, ROI, appearance bank, current-frame calibration
# profile and context_eligible inputs as DevelopmentExhaustiveMarkerProposals.
```

The appearance profile must specify mode `unassigned_cross_shape_v1` and bounded
integer `hue_center`, `hue_tolerance`, `saturation_min`, `value_min`. Unknown keys
including `validated` are rejected. The observer copies/fingerprints the profile;
profile/reference/pixel changes during observation invalidate the result.
Profile values and training images are not included in this repository.

## Evidence and safety

The result describes **unassigned cross appearance**, not a dead player, recorder,
camera state or Death Event. It can observe shapes on spectated/death screens
without making those frames self eligible. `semantic_marker_class` and ownership
remain UNKNOWN. No player position, Zone, track, interpolation, Fact or Event is
qualified. Native source/SHA/PTS/epoch/pixel binding and the current-frame geometry,
visible-floor and Map-build gates are inherited unchanged.

The parent proposals retain their centers and geometry. Nearby NCC/rim/cross
observations are retained separately with UNKNOWN overlap associations, using both
window overlap and distance. No close observation is suppressed or averaged by
this new stage. A connected component is pixel support, not a physical-marker
identity; all25 tested center hypotheses are retained as measurement evidence.
The parent's heuristic NCC canonical selection remains unchanged; no physical
NCC duplicate accuracy gain is claimed.

The bounded ROI is at most1024px. Component bounding boxes are7–25px; local
sampling tiles are at most45×45 float pixels, replacing a full-ROI temporary per
component. At most128 eligible components receive shape tests and the combined
proposal limit remains128. Unchecked component counts, output overflow and
truncation are explicit; supported observations remain in search evidence even
when the output budget is exhausted. Nothing is cached from a previous frame.

## Measured development comparison

One previously annotated image supplies the color profile. All other annotations
remain unchanged. These are exposed DEVELOPMENT comparisons, not independent
qualification. Class labels, center correspondence, camera ownership and qualified
Map positions are separate measurements.

| Same inputs | Parent #87 | With cross observations | Change |
| --- | ---: | ---: | --- |
| Known20 recorder-marker matches /15 | 8 | 8 | neutral |
| Known20 teammate matches /61 | 25 | 25 | neutral |
| Previously reviewed10 PLAYER matches /46 | 13 | 15 | 🟢 +2 |
| Three complete ROI center matches /17 | 3 | 7 | 🟢 +4 |
| Three complete ROI precision at2px | 30.0% | 50.0% | 🟢 +20pp |
| Three complete ROI recall at2px | 17.6% | 41.2% | 🟢 +23.5pp |
| Different-recording death-center matches /4 | 0 | 3 | 🟢 +3 |
| Existing matched-point losses | 0 | 0 | neutral |

The three complete ROIs contain12 normal PLAYER and5 death-marker annotations.
Four added candidates match death annotations: one training-image match and three
on a different recording. The parent7 unmatched candidates remain:4 confirmed
PLAYER objects with center discrepancies,2 UI and1 background. Their absolute
count has not fallen. No new unmatched candidate is added in these three ROIs.
One inconsistent OUT_OF_SCOPE review is still unmeasured; its labels are preserved.
The earlier16 object labels remain10 PLAYER /2 UI /4 UNKNOWN.

Across72 identical native observations, every parent proposal center/geometry
remains equal, and all33 cross centers and core features exactly match the private
full-ROI prototype. The local-tile port changes storage, not those measurements.
An isolated OpenCV4.12.0/NumPy2.2.6 environment reproduces all72 cross-search evidence
records versus4.14.0/2.5.4. This is measured portability, not universal qualification.

Additional candidate counts: known20 gets11, fixed40 gets10, new12 gets12. Known20
raw geometry40→46; fixed40 raw geometry85→91; new12 raw geometry21→24. These are
unassigned geometry-only hypotheses. Extra objects in incompletely annotated
images remain unreviewed, and these counts are not recognition precision.

## Center and numerical limits

The three prior NCC center misses remain2.236px; the four unsupported recorder
appearances remain limited by overlap/rim isolation. Neither GT tolerance nor
NCC acceptance changes. Existing paired center differences do not change:
known20 n35 mean1.244px/median1.414/max2; reviewed10 n13 mean1.028/median1/max2;
new complete ROIs n3 mean1.333/median1/max2. Improvements/worsenings of these
existing paired centers are0/0; per-image pair differences are retained privately.

Conditional statistics on **all** newly matched points use a different cohort:
reviewed10 n15 mean1.013/median1/max2; new complete ROIs n7 mean1.412/median1.5/max2.
The latter mean is larger because four new observations enter the cohort, not
because old centers moved. Different-recording new matches n3 have mean1.360px,
median1.5 and max1.581. These are differences from human clicks, not absolute Map
error; annotation-center accuracy was not independently remeasured.

This stage does not reinstate approximate screening. Parent exhaustive NCC and
its original complete-NCC fallback remain unchanged. Semantic/numerical backend
qualification remains false; unverified Map identity/build and recorder ownership
are not promoted by extra shape evidence.

## Timing and verification

Same18 registered-Map inputs, three isolated single-threaded processes per method,
alternating order; expected digests only, all digests equal the frozen predictions.
Image decoding is excluded. Constructor, first5 per-Map observations and subsequent13
are recorded separately. Python3.12.15, macOS arm64, OpenCV4.14.0/NumPy2.5.4.

| Method, later paired run | Median sec (range) | Median peak RSS MiB (range) |
| --- | ---: | ---: |
| Parent exhaustive E | 14.660 (14.064–14.823) | 314.30 (311.36–315.95) |
| E plus cross observations F | 14.509 (14.295–15.567) | 311.13 (282.67–314.72) |

Ranges overlap, so no speed or memory reduction caused by the added stage is
claimed. Separate profiling measures0.210s in cross observation over18 images
(including0.186s local shape sampling). Parent #87 documents the earlier A–E
three-run comparison on the same inputs. Versus that #86 median23.306s/332.56MiB,
F is37.7% faster and6.4% lower RSS; measurements are from different rounds.
Versus the earlier reported23.18s/345.03MiB, differences are37.4%/9.8%. 🔴 F remains
slower and larger than single-scale A (9.198s/276.45MiB). RSS is process peak,
not Python allocations; observed spread is not a confidence bound.

26 focused synthetic tests cover cross/plus/ring/arrow/solid controls, disconnected
components, nearby NCC/cross retention, limits/overflow, full-image/local-tile
parity including borders, profile validity/fingerprints, late mutation and raw
geometry isolation.380 related tests, Ruff src/tests and mypy160 sources pass.
Default Bind/Haven/spectator regressions are checked separately from the added
unassigned observations. No HUD, intake, Production contract, Registry or default
recognizer changes; no protected/unregistered recordings or Full E2E.

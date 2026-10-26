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

## Controlled timing and verification

A final audit found that the historical timing labels did not establish the
actual BLAS thread limit. NumPy uses Apple Accelerate, so OPENBLAS/OMP variables
alone are insufficient. Earlier timing values remain historical observations;
the following controlled rerun supersedes their single-thread interpretation.

Same18 registered-Map inputs, three isolated processes per method, no large
prediction fixtures. OpenCV parallel regions are disabled with request0 and
getNumThreads reports1; OpenCL is disabled. Accelerate BLASSetThreading selects
SINGLE_THREADED on the executing thread, and BLASGetThreading is checked before
and after every observation. CPU user/system time is recorded separately from
wall time. The observed recognition CPU/wall ratios are0.988–1.000. Constructor,
first5 per-Map and subsequent13 observations are separated; decode is excluded.
Python3.12.15, macOS arm64, OpenCV4.14.0/NumPy2.5.4.

OpenCV's GCD getter can report the processor pool limit despite request1; the
controlled run uses request0/getter1 instead. See the
[OpenCV threading implementation](https://github.com/opencv/opencv/blob/4.x/modules/core/src/parallel.cpp).
Accelerate mode meanings were verified against the installed SDK thread_api.h.
These controls affect the benchmark process/thread only.

A–D runtime code is unchanged. E/F below include early release of row windows,
patches, partial products and per-reference normalization scratch. Full output
records remain bit-identical on72 frozen observations, including ownership and
all geometry/diagnostic fields. Every controlled timing-run digest also matches
its original expected result. No recognition threshold, center or GT changes.

| Controlled method | Median sec (range) | Median peak RSS MiB (range) |
| --- | ---: | ---: |
| A: before #83 | 9.222 (9.188–9.584) | 270.53 (270.12–272.33) |
| B: #83 | 36.425 (36.335–36.537) | 295.39 (291.45–297.14) |
| C: screen | 22.906 (22.876–23.611) | 317.17 (313.95–318.62) |
| D: #86 | 23.386 (23.353–23.815) | 315.48 (300.77–316.64) |
| E: exhaustive + scratch release | 13.947 (13.931–13.997) | 299.00 (297.88–300.91) |
| F: E + cross observations | 14.051 (14.018–14.087) | 302.16 (286.70–305.48) |

🟢 F versus controlled D: recognition time falls39.9%, median peak RSS4.2%.
Versus the previous reported23.18s/345.03MiB, the values are14.051s/302.16MiB
(39.4%/12.4% lower); historical thread control was not verified, so that is not
a controlled causal comparison. 🔴 F still costs52.4% more time and11.7% more RSS
than the less capable single-scale A.

The lifetime-only change lowers E peak RSS306.89→299.00MiB and F306.72→302.16MiB
in the same explicit control conditions. E time14.113→13.947s, F14.664→14.051s.
F RSS ranges overlap substantially; the small sample does not establish an
all-input memory guarantee. RSS is process peak, not Python allocations, and
observed spread is not a confidence bound. The extra cross stage itself is not
claimed to reduce runtime/RSS. Separate profiling previously measured0.210s cross
work over18 images, including0.186s local shape sampling.

26 focused synthetic cross tests and22 exhaustive-NCC tests pass.380 related
tests, Ruff src/tests and mypy160 sources are checked after the lifetime change.
Controls cover cross/plus/ring/arrow/solid appearances, nearby observations,
disconnected components, explicit budgets, local/full tile parity, profile/late
mutation and raw geometry isolation. Bind/Haven/spectator regressions are checked
separately. No HUD, intake, Production contract, Registry or default recognizer
changes; no protected/unregistered recordings or Full E2E.

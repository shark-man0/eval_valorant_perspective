# Exhaustive development marker observations

PR #86's opt-in screen repeats approximate correlations before full masked NCC,
retains substantial floating-point temporaries, and has no universal numerical
rejection certificate. This separate opt-in method evaluates every valid window
with bounded integer row correlations and shares current-scale moments across
reference libraries. It does not use the approximate screen. Defaults, the
Production detector and the previous comparison methods are unchanged.

```python
from valorant_ai_coach.visual.development_marker_exhaustive import (
    DevelopmentExhaustiveMarkerProposals,
)

engine = DevelopmentExhaustiveMarkerProposals("bind")
# Same explicit, frozen native sample / ROI / appearance bank / profile inputs
# as DevelopmentQualityMarkerProposals.observe(...).
```

This is an algorithm comparison, **not OpenCV masked-NCC output equivalence**.
Normalization differs from OpenCV at low image variance. Acceptance remains .80;
center matching tolerance remains 2 native pixels. Neither a match to a recorder
reference nor a continuous detection authenticates the camera or recorder.

## Arithmetic, memory and fallback

For uint8 BGR inputs, odd square 9–65px references and contiguous binary mask
rows, each row dot sums at most195 nonnegative products. Its maximum is below
2**24, making IEEE binary32 products/additions exact regardless of reduction
order. Integer row accumulation fits int32; bounded integral sums and integer
normalization numerators fit exactly in float64. Square root and division remain
floating point. The runtime checks the floating-point format and representative
GEMM reductions. This is a prerequisite check, not a universal runtime certificate.
Unsupported masks, inputs, arithmetic failures or a failed runtime check use the
original **complete** masked-NCC inspector; they do not silently reject a library.

At most12 references are processed together, in64-output-row tiles. Identical
reference content is computed once per group; moments are shared within the exact
current image and mask. Integer correlation storage is reused for score planes.
Frame arrays, moments and score maps are cleared on entry, return and exception.
Reference content is re-read and fingerprinted by the inherited loader and verified
again before return. No previous-frame marker or transform is reused.

`execution_evidence` records the runtime check, fallback calls and library versions.
`numerical_backend_qualified` remains false. An untested environment is not
independent recognition qualification.

## Nearby observations are unresolved

`observation_alternatives` retains every accepted raw NCC observation and supported
circle observation, including observations suppressed by canonical selection.
Overlap and distance generate **UNKNOWN** associations, possibly to multiple
canonical proposals. They do not prove that two observations depict one physical
marker. Unlinked observations are retained explicitly. Canonical proposals remain
stable display/geometry selections; the inherited `duplicates_removed` field is a
heuristic selection count, not a physical-marker duplicate count.

No transitive merging, center averaging, death/portrait role inference or actor
identity is added. Alternative observations are not scored as extra detections and
are not new Player Events, tracks or qualified Map positions. Exact same reference
content is computational deduplication only.

## Fixed DEVELOPMENT comparison

The same60 prior native images retain canonical candidate counts, coordinates and
2px matches with no previously correct point lost:

| Input | PR #86 | This method | Change |
| --- | ---: | ---: | --- |
| Known20 recorder-reference marker matches /15 | 8 | 8 | neutral |
| Known20 teammate markers /61 | 25 | 25 | neutral |
| Previously reviewed10 PLAYER /46 | 13 | 13 | neutral |
| Known20 candidates / raw Map candidates | 68 /40 | 68 /40 | neutral |
| Fixed40 candidates / raw Map candidates | 138 /85 | 138 /85 | neutral |
| Previously correct point losses | 0 | 0 | neutral |

Raw alternative observations retained:130 in known20 and269 in fixed40. These are
measurements, not399 physical markers. Existing16 object labels remain10 PLAYER,
2 UI and4 UNKNOWN; they are not exhaustive ROI annotations or ownership labels.

Matched known20 click differences: mean1.244px, median1.414px, maximum2.000px
(35 matches, including2 OTHER). Reviewed10: mean1.028px, median1.000px,
maximum2.000px (13 matches). Paired center improvement/worsening:0/0. These are
conditional click differences, not absolute Map error or full-video precision.
The three residual center misses remain2.236px. A local subpixel variant was
rejected after losing3 teammate matches. Four unsupported appearances remain
limited by overlapping portraits / insufficient isolated rim contrast and support;
new references, lower thresholds and wider GT tolerance were not introduced.

## Repeated isolated-process benchmark

Same18 registered-Map images, three runs each, rotating method order, single CV
and BLAS threads, macOS arm64, Python3.12.15, OpenCV4.14.0, NumPy2.5.4. Each child
loads expected record digests, not large prediction fixtures. Every expected digest
matches. Constructor, first5 per-Map observations and subsequent13 are recorded
separately; image decoding is excluded from recognition time. RSS is process peak,
not Python allocations. The range is observed variation, not a confidence bound.

| Method | Median sec (range) | Median peak MiB (range) |
| --- | ---: | ---: |
| A: before #83 | 9.198 (9.149–9.773) | 276.45 (274.33–278.05) |
| B: #83 | 36.325 (36.287–36.329) | 302.17 (299.91–306.56) |
| C: screen | 22.965 (22.791–23.019) | 332.92 (331.30–336.03) |
| D: #86 | 23.306 (23.282–23.585) | 332.56 (318.00–338.94) |
| E: exhaustive | 14.004 (13.989–14.014) | 310.80 (310.31–311.98) |

🟢 E versus contemporary D:39.9% less recognition time and6.5% less median peak
RSS. Versus the previous single-run23.18s /345.03MiB report:39.6% /9.9% less;
that historical comparison includes environment variation. 🔴 E still takes52.3%
more time and12.4% more RSS than the less capable single-scale A. Center accuracy
and confirmed UI suppression have not improved.

All results are exposed DEVELOPMENT diagnostics. Ownership stays UNKNOWN;
version-compatible positions, selected self positions, formal Facts/Events and
strategic evaluations remain zero. Native source/hash/PTS/epoch/pixel checks,
current-frame geometry, floor and build gates are inherited. Protected recordings
and unregistered additions are not used. No Full E2E is run.

## New intervals and exhaustive ROI review

Before prediction or decoding, four approved DEVELOPMENT sources were selected
at37% of registered duration, with three native observations250ms apart per source.
Selection failures were not replaced by successful detections. Four central images
were reviewed once: first all visible marker centers with predictions hidden, then
candidate object types. Model parameters were frozen before the saved answers were
read. No new reference fitting used these12 observations. They remain exposed
DEVELOPMENT, not a new qualification set.

Three complete, internally consistent ROIs contain12 PLAYER and5 death markers.
A fourth image marks4 candidates OUT_OF_SCOPE without a corresponding exclusion
region; its whole-ROI precision/recall remains **unmeasured**, preserving those
labels without inventing background GT. No additional human review is requested.

| Three complete ROIs, fixed2px matching | A | B /C /D /E |
| --- | ---: | ---: |
| Canonical candidates | 6 | 10 |
| One-to-one matched markers /17 | 3 | 3 |
| Precision at2px | 50.0% | 30.0% |
| Recall at2px | 17.6% | 17.6% |

For D/E,3/12 normal PLAYER centers match;0/5 death centers match. Among7 unmatched
candidates, human object labels identify4 PLAYER objects with localization misses,
2 UI objects and1 background object. Thus70% unmatched at2px must **not** be
reported as70% background false detections. Conditional matched center differences
are mean1.333px, median1.000px, maximum2.000px (n=3). D/E agree; no accuracy gain
is established. Death markers, center localization and UI/background suppression
remain major limitations.

Across all12 new observations, D/E canonical centers agree:7,14,16 and8 candidates
per three-observation source interval. Current-frame unique outline candidates
are Bind and Haven for the first two intervals (7 and14 raw geometry candidates);
the other two remain UNKNOWN (no raw Map positions). This establishes measured
transfer parity on these inputs, not verified Map identity, ownership or absolute
Map accuracy. Neither trajectories nor continuous dwell are inferred from them.

The new observation index organizes existing raw measurements; it does not turn
previously suppressed observations into additional scored detections. Physical
NCC/circle equivalence remains unresolved. The heuristic native-first canonical
selection itself is unchanged; no physical deduplication accuracy gain is claimed.


## Validation and remaining gates

-22 focused synthetic tests pass;354 related tests pass locally (focused tests
  are a subset). Full source/tests Ruff and mypy159 sources pass.
- An isolated OpenCV4.12.0 /NumPy2.2.6 environment reproduces all20 known-image
  canonical centers and checked raw NCC/circle/alternative evidence exactly,
  compared with OpenCV4.14.0 /NumPy2.5.4. The runtime arithmetic check passes.
  This is measured transfer, not a guarantee for every OpenCV build or input.
- Existing Bind198 remains ROI112 /calibration149 /Map70 /Named3; Haven40/50;
  subsequent Bind27/30 and Haven28/30; spectator20/20 explicit blocks;
  defaultR27 /Named15, portableR30 /Named20 and static18/18 are retained.
  These default recognizers were rerun unchanged, separate from E's comparison.
- Separate profiling finds exhaustive NCC7.236s, shared moments1.995s,
  Map calibration3.974s, resize1.355s, Hough0.376s, reference loading0.077s,
  grouping0.0004s and alternative linking0.0006s. Cumulative times overlap;
  do not sum them. E screening time is zero. Large row-patch copies and NCC
  remain the main costs; no historical transform/position cache is introduced.

Next priorities are center localization without losing existing matches,
nearby/death-marker separation and confirmed UI/background rejection on additional
fixed DEVELOPMENT input. Absolute Map error, physical duplicate truth, recorder
ownership and Map-build compatibility require independent evidence. Newly provided
recordings remain unused until registration and DEVELOPMENT allocation are verified.

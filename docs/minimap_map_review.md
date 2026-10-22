# Minimap / Bind pre-integration technical review

Later development adds partial interiors and a candidate-path viewer; see
[development_map_paths.md](development_map_paths.md). Results below describe the
pre-extension review baseline.

The review keeps the existing development-only boundary: no qualified self
identity, Production Self Position Fact, gameplay event or GOOD/IMPROVE score.
The default Production registry, event contract, schemas and HUD components
are unchanged. The review baseline contained only the reviewed shaded plant footprints.

## Confirmed findings and fixes

1. `DevelopmentMapTimeline` called the Production `MapEventConsumer` even
   though ownership remained UNKNOWN. The consumer's default actor is player
   and it does not understand the development qualifier. A synthetic seam with
   adjacent stable Zones reproduces a player-shaped event. Current real Bind
   windows emit none: gaps/pending resolutions usually clear its path. This is
   a boundary/design risk, not a claim of observed real-video event leakage.
   The development path now never calls that consumer. Its optional transition
   record has `candidate_kind`, UNKNOWN ownership and development qualification,
   without Production `type`, `actor`, `confidence` or `start_sec` keys. The
   nested resolution also carries UNKNOWN/development tags, intentionally fails
   the formal resolution schema, and is explicitly rejected by the Production
   consumer (including ally inputs). Qualified Production behavior and its
   schema/contract are unchanged. Synthetic immediate debounce is
   used only to exercise this seam; registered thresholds are unchanged.
2. `SelfMarkerTracker` keyed decoded references only by mode and filenames.
   Same-path replacement, corruption or deletion could keep old pixels while
   the analyzer fingerprint already reflected new files. Reproduction tests
   failed before the fix. Bounded content reads/hashes now key the cached
   decode; changes reset tracking, unavailable/bad references fail closed, and
   repaired files can be loaded again. The existing analyzer fingerprint still
   hashes reference contents. Empty negative references were already rejected;
   a regression test confirms this rather than inventing a new empty-list bug.
3. A malformed non-string mode, nonnumeric timestamp or failed decoder image
   could raise instead of returning UNKNOWN. These inputs now fail closed.
4. An invalid development observation could leave earlier tracking state
   intact. A replaced Map-options dict could still calibrate using old Bind
   selection/options. Both have failing reproduction tests. Invalid calls now
   discard state; map selection is rechecked, current options are used, and a
   changed/unknown Map requires a new timeline. Explicit source/acquisition IDs
   and context changes prevent bridging independently acquired intervals.

## Calibration correctness and error measurements

The 149/149 accepted calibrations are correspondence-gate results, never a
count of correct coordinate transforms. Existing blank/noise/grid, wrong Map,
partial crop, rotation, skew and duplicate-placement rejection tests remain.
Additional synthetic scale/translation and ROI-size changes compare complete
cached/uncached results (including transforms). Reference hash changes cannot
reuse an accepted transform. Synthetic accuracy is separate from footage.

Three fixed-index DEVELOPMENT examples were selected without filtering on
accepted predictions. Source centers and three static landmark pairs per
example were manually proposed from raw images, without model coordinates.
The recording owner confirmed the three self centers and landmark matches
within two original pixels. These labels were never used for template fitting,
thresholds, registration or calibration adjustment. They are same-recording
development checks, not independent qualification.

Two examples have emitted positions; one abstains. ROI center point-estimate
errors are 1.41 and 2.24 pixels (mean 1.83). With the reviewed two-pixel radius,
the respective possible error intervals are [0, 3.41] and [0.24, 4.24] pixels.
Relative to an independent affine comparison from the human landmark pairs,
the two end-to-end errors are 5.98 and 9.74 public-reference pixels (mean 7.86),
or 0.00706 and 0.01174 in normalized Map space. These are approximate comparison
references, not exact world-position GT; landmark and center annotation
uncertainty both matter. Real-game distance accuracy remains unmeasured.

Across nine landmark comparisons the maximum point-estimate calibration
residual is 6.65 reference pixels. Source/reference annotation tolerance permits
up to 13.59 pixels at that worst pair, and every pair's tolerance interval
includes zero. This limited evidence supports rough correspondence; it cannot
prove subpixel accuracy, all-frame correctness or boundary-accurate Zones.
Three independent cold recalibrations of each example give identical results.
Pure position jitter remains unmeasured without independently labelled stopping;
ordinary frame-to-frame differences contain actual movement.

The three new positive labels join two earlier reference and three earlier
validation labels. No human-confirmed nonself controls exist in this small set;
zero confirmed mistakes among reviewed examples is not a population FPR.
All 198 automatic ownership outputs remain UNKNOWN. Cross-source geometric
transfer to another Bind recording remains unmeasured. The other observed,
unregistered Map is never forced into Bind.

## Safe performance improvement and fixed regression

Profiling the same 198 observations before optimization took 57.59 seconds:
7,003 reference resizes consumed 31.58 seconds, template matching 21.15 seconds
(including marker matching), Canny 2.30 seconds and image reads 1.40 seconds.
The earlier unprofiled milestone timing was 55.24 seconds. Repeated resizing
and reference edge extraction were the main avoidable cost.

The cache contains only immutable reference gray pixels and per-scale edge
weights/populations. Keys include reference path/content SHA, geometry version,
mask box and actual ROI shape; feature storage is bounded to 64 MiB for one key.
Oversized suffixes are recomputed. The Bind reference is checked against its
registered provenance hash. Acquisition/profile/ROI/geometry changes discard
the development context/cache. No previous frame transform, target edges,
search result or candidate location is reused. Every frame still runs full
scale/placement search, two-way support, spatial support and ambiguity gates.
Unknown geometry changes must pass fresh correspondence or return UNKNOWN.

The measured optimized replay took 22.28 seconds (2.58x), with peak RSS
124.7 -> 145.0 MiB. Resizes fell to 141 and Canny calls to 290; template matching
is now the dominant cost. These are one-thread, one-run profiled measurements,
excluding decoding/image I/O. Increased memory buys immutable preprocessing,
not permission to reuse alignment. Final source replay is recorded privately.

All 198 regression records retain identical appearance outcomes/reasons,
calibration status/confidence/diagnostics, coordinates, segments, speeds, Zone
results and zero events/facts. The two nested safety tags are intentional
metadata additions; they are excluded from numeric/semantic regression.
Counts remain ROI112, Bind calibration149/149,
Map70, Zone3, seven segments, longest5.4 seconds. Source-reviewed blocked views
remain72 with zero points; they do not qualify an automatic view recognizer.
The three Zone resolutions still mean only the development A plant footprint.

## Review boundary

The source API is reviewable only as an opt-in development component. It cannot
be adopted as a qualified ownership, position or coaching producer. Remaining
work includes independently checked nonself/spectator controls, more precise
coordinate labels and another recording/settings/build, stationary jitter GT,
and reviewed wider geometry/topology. Full-site boundaries, rotations and
unseen ally/enemy information are not manufactured to fill these gaps.

Private source frames, profiles, timestamps and annotations remain local.
Only DEVELOPMENT recordings were reused; evaluation candidates stayed closed.
No full private-video E2E was launched. The PR remains Draft and unmerged.

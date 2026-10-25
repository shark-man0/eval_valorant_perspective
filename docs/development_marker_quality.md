# Opt-in marker quality and screening

This builds on [PR #83's detector](development_marker_detection.md), without
changing its default implementation, Production recognition, thresholds or maps.
It provides two separate comparisons rather than attributing all differences
to an optimization.

## Screening backend

`ScreenedMarkerDetector` shares masked image moments between references for the
same scale and exact current ROI pixels. Circular binary masks are summed as
contiguous row intervals using integer intensity integrals and float64 squared
integrals. For the bounded uint8 input these sums and variance numerators are
representable as exact integers.
Unmasked correlation supplies a rejection screen with a deliberately loose
rounding allowance; surviving libraries use the unchanged full inspector.
Acceptance remains 0.80. Invalid or uncertain screen calculations fall back to
that inspector. Unmasked reference profiles always use the original inspector.

The correlation allowance is an experimental numerical guard, not a certified
bound for every OpenCV implementation or input. It must be checked against full
search on the actual input/runtime. Complete proposal evidence, scores, centers,
truncation and rejection results matched PR #83 on the fixed 60 development
images. This does not qualify the screen for Production or arbitrary images.
Execution counters are separate from proposal evidence; no role is inferred.

Only moments of the current scale are cached, keyed by exact pixel digest,
shape and mask bytes. There are at most four libraries. All state is cleared at
observation entry and on return or error. Reference content is still re-read
and fingerprinted before and after observation. No prior-frame position,
transform, source/epoch result, or calibration acceptance is cached.

## Independent center method

`QualityMarkerDetector` adds a bounded ALT Hough circle observation to the
screened detector. It uses the existing texture, chromatic rim and gradient
support test, without lowering its gates. This is a different proposal method,
with its own fingerprint, not an output-equivalent optimization.

NCC anchor positions are retained. An original circle is refined only when one
supported ALT circle is within 3px and that circle corresponds to just one
original candidate. Two nearby candidates cannot be moved onto one circle.
Original circles are retained when ALT misses them; requiring agreement for
all circles regressed existing correct observations and was rejected. Newly
supported ALT circles farther than 4px from retained candidates can be added.
There are at most 128 raw ALT checks, 64 supported observations and 128 final
candidates. Truncation, center shifts and suppressed nearby alternatives are
explicit. Nearby alternatives retain `same_physical_marker=UNKNOWN`; candidate
count is never a distinct-player count. Original NCC grouping is unchanged,
including its remaining native-first/overlap limitations.

`DevelopmentQualityMarkerProposals` connects this method to the unchanged native
sample/pixel binding, current-frame calibration and floor checks. Map-build
compatibility and recorder ownership remain UNKNOWN. Context-blocked geometry
is diagnostic only. Ordinary positions, Zone resolutions, self selection,
Facts, events, tracks and interpolation remain empty. Neither circle agreement
nor current map alignment authenticates a player or current camera.

## Exposed-development comparison

Known 20 images and the previously reviewed separate 10 are now method
development data. Their results must not be described as independent accuracy.
Original 2px matching tolerance and one-to-one assignment are retained.

| Same inputs | PR #83 | Center method |
| --- | ---: | ---: |
| Known 20: recorder-marker matches / 15 | 7 | 8 |
| Known 20: teammate-marker matches / 61 | 19 | 25 |
| Known 20: OTHER matches / 2 | 2 | 2 |
| Known 20: candidate count | 63 | 68 |
| Known 20: unmatched, role unknown | 35 | 33 |
| Separate 10: PLAYER matches / 46 | 11 | 13 |
| Separate 10: candidate count | 27 | 29 |
| Separate 10: unmatched, role unknown | 16 | 16 |
| Fixed 40: raw geometry candidates | 78 | 85 |
| Fixed 40: images with raw geometry | 23 | 23 |

No previously matched annotated point was lost in these comparisons. One of
the four known 2–5px recorder-marker center misses improved from 2.12 to 1.41px;
three remain at 2.24px. Global ellipse/gradient or all-anchor circle correction
lost existing teammate matches and was rejected. Overlapping portraits,
direction triangles and rim/background contrast remain limitations. Additional
references were not added; missing supported appearances are not automatically
missing Agent identities.

Unmatched observations are not background false positives. The 16 previously
unmatched candidates require a separate, prediction-exposed human diagnostic
review. That review cannot qualify the adjusted method independently. Do not
calculate population precision from incomplete annotations. Center offsets,
candidate recall and recorder ownership accuracy remain different quantities.

Benchmark the same registered-map 18 images in separate, single-threaded
processes. Record constructors, first observations per map, subsequent
observations, excluded decoding and process peak RSS separately. Compare the
full search, screen-only and center method rather than mixing their costs.
Keep private native identities, frames, profiles, coordinates and timestamps
outside the public repository.

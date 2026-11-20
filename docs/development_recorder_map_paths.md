# Recorder Map trajectories for development replay

The exporter reads exact native images and the existing application's common timeline.
It emits a sidecar with native observations and their existing one-second rows.
Map coordinates are pixels in a versioned map reference image. An empty second
has UNKNOWN coverage. Segments stop at missing observations, acquisition or map
changes, and selection gaps. Intermediate points are never interpolated.

```sh
python -m valorant_ai_coach.temporal.map_recorder_export \
  --bundle-path timeline_PRIVATE.json --frame-manifest acquisition_PRIVATE.json \
  --policy-path policy_PRIVATE.json --catalog public_reference_catalog.json \
  --layout config/hud_layout_1080p_v3.json --zones-path reference_zone_index.json \
  --output recorder_paths_PRIVATE.json
```

The frame manifest supplies `frames` with `sample` and `path`, from the native
acquisition contract. The catalog uses the existing public Map reader's `maps`
format. Optional `characters` entries provide `name` and `minimap_portrait`
relative to the catalog. The selector emits a named Agent only when a validated
current Map portrait agrees with shared HUD Agent evidence. The Zone index
provides a `maps` array. Each entry supplies `map_id`, `reference_sha256`, and
`polygons` mapping zone IDs to vertex pairs in the exact reference image's space.
The Zone reader abstains on missing coverage, overlapping polygons, and
boundaries within four reference pixels. Use authored geometry for the exact
registered texture. The sidecar has development-only position hypotheses.

`--recover-supported-portraits` enables a research option. It follows a
bounded, visible Map candidate when the top-ranked shape is unresolved,
only if the measured current view still belongs to the recorder. The
candidate must match the previous portrait and have noncompeting current
support. A partial fit cannot start a track or supply a tip. The public
ranking and the default selector behavior stay as approved in the prior PRs.

| Fixed 150-frame replay outcome | Count |
| --- | ---: |
| Current view evidence conflicts | 41 |
| Current SELF and ALIVE unavailable | 31 |
| Top portrait shape unresolved | 33 |
| Insufficient consecutive observations | 24 |
| Recorder anchor missing | 7 |
| Competing marker or overlap | 5 |
| Current view and recorder identity disagree | 3 |
| Recorder anchor unusable | 3 |
| Marker pool empty | 1 |
| Strictly correct research selections | 2 |

Five-match replay of the optional selector and 29 public minimap portrait
references reproduced two selections and 148 abstentions. A named Agent
match was not established for the selected real frames. The earlier
100 ms comparison experiment remains one correct selection and four
abstentions across five targeted comparison endpoints. These measurements
do not establish a recognition gain for this PR.

The CLI reproduced three Lotus coordinates over 0.4 seconds, joined to one
original common timeline second. This segment falls outside the authored site
polygons. The held endpoint and the second training sequence remain without an
accepted coordinate transform. The Zone polygon checks pass controlled tests.
All 100 frozen ranking scenes retained the established ordering.

## External game knowledge mode

Pass `--knowledge-asset-cache <cache directory>` when the game knowledge API
from PR #153 is available in the evaluation checkout. The exporter verifies
the pinned image cache through that API. It reads the viewed Agent from
distinct bottom-HUD ability slots and compares that Agent UUID with the
portrait inside each candidate's warm rim. The exact-sample Camera and Life
guards still apply, including combat-report and perspective conflicts.
Distinct matching markers and overlapping fitted rivals cause abstention.
The recognition mode preserves the existing candidate IDs and ranking.

A strongly fitted portrait with an attached tip can contribute a single
observed point. A tipless fit needs a matching adjacent observation of the
same Agent, Camera producer, Source, acquisition, and Round. A one-second
row may contain a single point. Path edges require adjacent observations
within 250 ms and split when the evidence starts a new track. Each point and
track remains a development hypothesis. The mode only reads the common
timeline. It issues no position Facts, Player Events, or tactical assessments.

### Evaluation with the revised common timeline

| Fixed 150 native frames across five DEVELOPMENT matches | PR #156 | Latest common inputs | With knowledge |
| --- | ---: | ---: | ---: |
| Selected research candidates | 2 | 2 | 23 |
| Correct among six reviewed recorder markers | 2 | 2 | 5 |
| Wrong among reviewed selections | 0 | 0 | 0 |
| Selected candidates with unresolved correctness | 0 | 0 | 18 |
| Abstained | 148 | 148 | 127 |
| Current view evidence conflict | 41 | 40 | 40 |
| Current SELF and ALIVE unavailable | 31 | 41 | 41 |
| Top portrait unresolved | 33 | 28 | 27 |
| Insufficient native continuity | 24 | 24 | 5 |

The common inputs use the health-digit camera gate from #151 and the
continuity revisions from #150. They rejected additional insufficiently
supported views. The held-out DEVELOPMENT comparison subset selected one
of 60 candidates. That new selection has no owner label. All 25 native
observations classified as SPECTATOR by the revised timeline abstained.
These counts measure development coverage and reviewed agreements.

The public exporter was run on the same 250 retained images (50 per match)
using whole-recording one-second bins. Map-reference points increased from
3 to 21 across Lotus and Corrode. Seconds with any point increased from
1 to 9 out of 11,487. Observed edges increased from 2 to 13. Named Zone
coverage remained zero. The other seconds were unobserved by this replay
or had no accepted point. The five-match test used sparse native coverage
and short dense windows. Absolute coordinate error and full-density match
coverage remain unmeasured.

### Selection conflicts and location names

When two accepted research methods place the recorder marker at different
physical markers, the frame abstains and contributes no witness to either
side of the path. Different candidate IDs may still refer to the same
physical marker if their fitted rim and centers agree. The exporter resets
the legacy witness at a conflict. Explicit visual ambiguity can also veto a
legacy selection. A missing UUID reading alone preserves the legacy path.

Map-reference coordinates are bounded by the selected reference image.
Registration reports a 95th-percentile inlier fit residual in reference
pixels, which is used as a lower bound on the Zone boundary margin. The
residual describes the features used to fit the transform. Absolute marker
error requires independently measured landmark or recorder ground truth.

In Knowledge mode, registered callout anchors whose image digest matches
the Map reference also supply a `callout_candidate`. A near anchor must
clear distance and runner-up margins even after including the fit
residual. Authored polygons remain the source of `zone_candidate`.
Callout points do not define polygon boundaries or dwelling intervals.

Knowledge mode fills absent Map reference IDs from verified displayicons
in the same asset cache. An explicitly provided readable reference takes
precedence for its Map ID. The alignment and runner-up thresholds apply to
the expanded inventory. The Bind and Haven development polygon
registries can be used after verifying the texture bytes. The Haven
authoring image is an exact quarter turn of the displayicon, so those
polygons need the inverse authoring transform before export.

## Native cadence and coverage

For continuous trajectory analysis, acquire native frames at 5 Hz over the
relevant intervals. The shared match acquisition supports
`--full-density --dense-seconds 1/5` for a whole recording. Retain each
native sample ID and its original image in the frame manifest, and join to
the existing application timeline. Map export keeps the one-second rows.
An isolated point remains `isolated_points`. An observed edge of at most
250 ms puts `native_edge_observed` in its endpoint bins. A missing frame,
camera or acquisition change still breaks the path.

`operable_coverage` uses bins whose observed frames all carry current
SELF, ALIVE and measured recorder-view evidence. Missing or contradictory
evidence is excluded from that denominator. A bin containing an edge need
not have an uninterrupted path throughout the second. A 1 Hz experiment
can measure observed position availability but does not measure subsecond
trajectory availability.

`--recover-knowledge-track` allows a 250 ms UUID hold only within the
same measured camera, acquisition and round and only while finding a
current compatible marker. A partially fitted local marker needs a single
strong UUID match on its current pixels and may not seed a track or be
followed by another partial fit. Candidates rejected only by the quick
rim prescreen can be fitted again. This branch requires an attached tip
and a strong full fit in addition to the original UUID thresholds.
`--recover-map-alignment` rechecks an abstaining alignment using exact
descriptor matching. It requires the original best Map, agreement at four
points across the ROI, and the existing Map acceptance gates.

Both recovery options are development modes. Callouts remain point
proximity hints. Named Zones require a registered polygon for the exact
reference texture.

## Direct minimap portrait search

Add `--direct-detector cascade` to run full-minimap portrait search with the
verified knowledge asset cache. The default exporter and the existing Map
candidate ranking keep their prior behavior. This option consumes the common
timeline's native Camera and Life observations and runs without a Map candidate
list. It establishes the recording Agent UUID from at least three distinct,
spaced readings of the player's ability HUD with exact SELF/ALIVE evidence.
The recording UUID persists when the camera changes. Each position requires
current view evidence, an independently confirmed portrait and rim, and a
registration to a verified reference image.

The cascade uses compact color templates first. If no candidate passes UUID
and rim validation, it tries an augmented grayscale search and applies the
same color validation again. Separated competing markers cause abstention.
For comparison, `external`, `augmented`, and `fast` use individual search
variants. A lower-confidence observation needs fresh adjacent support inside
the same Camera, Round, Source, and acquisition. A lost observation breaks
the path. The one-second export exposes `direct_stage_counts` and
`direct_selection_reasons` for these stages. A position candidate supplies
no ownership or position authority.

Five registered DEVELOPMENT recordings contributed 900 same-input dense
observations. The cascade increased Map positions from 149 to 234 and native
edges from 110 to 183. Seconds with positions went from 38 to 51 of 86 observed
operable seconds. Seconds with a native edge went from 31 to 45. A separate
Corrode recording contributed 360 comparison frames and produced 36 to 60
positions and 23 to 48 edges. Among six previously reviewed recorder
markers, five selections matched the reviewed center vicinity (within five
original-frame pixels) and one abstained. No selections occurred on the 25
fixed spectator controls. The remaining selections need independent role
verification. These are development coverage counts.

An experimental learned augmentation used the separate continual-learning
feature and model registries, with TRAIN, VALIDATION, and DEVELOPMENT
comparison assigned by physical match. The learned kernel tied the
augmentation baseline on the validation recording (8 of 21 eligible
seconds with a position, 7 of 21 with a native edge). The model gate
rejected the new kernel. The exporter does not load trained weights.

### Rim-guided search and recording Map identity

Use `--direct-detector guided` with `--knowledge-asset-cache` and
`--recover-map-alignment` to compare the augmented grayscale proposals with a
full-color search. The color search counts warm annular pixels before choosing
peaks. Both searches verify each proposal against competing Agent portraits.
Spatially distinct accepted markers cause an abstention.

The Map reader can recover a rejected projection after three spaced accepted
registrations bind a Map UUID to the recording. It requires a fresh alignment
on contrast-enhanced pixels, the same leading Map in the original image, and
agreement of the two transforms across the ROI. When a recent native
registration exists, it checks relative rotation and scale. It reports the
recording Map UUID alongside the development-only one-second output.

To compare an existing fitted-marker stream on the same native images, add
`--corroborate-direct-with-legacy`. A matching measured UUID and fitted center
can corroborate a provisional direct marker. A current conflict drops both
its selection and its path support.

For a development learning experiment, `fit_registered_rendering` fits a
shared BGR transform from external portrait patches and weak 9×9 patches
in the continual-learning feature store. Supply acquisition hashes, extractor
IDs and feature file digests for the TRAIN recordings. Compare the resulting
rendering on validation recordings before adopting it. The learned color
transform supplies proposals only in the research comparison.

With guided search, `--recover-native-flow` can recover an adjacent frame's
projection using tracked minimap features and a current reference match.
It checks forward/backward flow, inlier spread around the actual marker, and
agreement with the current reference transform at four locations. The anchor
must have a projected, selected marker on the same native acquisition and
track within 250 ms. Each recovery consumes the anchor. A recovered transform
cannot start another recovery.

`--recover-adjacent-portrait` adds an opt-in comparison after guided search
abstains. The preceding frame must have a selected and projected recorder
portrait. Within 250 ms, the current portrait must still favor the recorder's
Agent, retain warm rim support, closely match the preceding pixels, and land
near the preceding marker. Distinct eligible centers cause an abstention.
The current frame must independently align to the bound recording Map.
A recovered portrait supplies only its observed point. It does not seed a
following recovery, vote for the Map binding, or anchor optical flow.

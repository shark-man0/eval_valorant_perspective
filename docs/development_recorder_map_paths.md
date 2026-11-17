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

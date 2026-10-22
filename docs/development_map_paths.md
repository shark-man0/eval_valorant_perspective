# Development candidate paths and offline playback

The source-checkout API now connects `DevelopmentMapTimeline` observations to
`analyze_candidate_path` and a private offline HTML viewer. The viewer pairs each
Map observation with the same acquired source frame, plays in source-time order,
and exposes missing positions, acquisition cuts and reference appearance scores.
It needs no server, external scripts, uploads or network requests. Open its HTML
file locally. This is a development feature; the desktop coaching pipeline does
not consume these paths.

## Safety and interpretation

- Ownership stays UNKNOWN in every observation, edge, segment and transition
  bracket. No Self Position Fact, Production Event or GOOD/IMPROVE is generated.
- An edge joins two adjacent measured positions in the same source, acquisition,
  profile/ROI/geometry context and upstream segment, at increasing source times
  no more than 0.3 seconds apart. Invalid/missing positions and blocked views break
  the path. Source/frame/time reversals and position jumps start a new segment.
  No sorting, gap interpolation, inferred route, walkability or LOS is used.
- Lines are **chords between observations**, not observed movement between them.
  Segment spans sum adjacent source-time intervals; single points have zero span.
- Same-Zone observation spans count only edges with identical, clear, unheld,
  explicitly development-tagged named Zone endpoints. They do not prove continuous
  occupancy. Zone-change brackets record different accepted endpoints along an
  uninterrupted measured path; the crossing time and intermediate Zones remain
  unknown. Pending/unknown Zones never acquire dwell time.
- Coarse or pending polygon candidates remain separate in
  `development_region_candidate` and `region_candidate_observation_spans_sec`.
  A low geometry cap does **not** raise the canonical Resolver's named-Zone
  acceptance threshold. Candidate-region spans never become named-Zone spans.
- Motion labels describe a window ending at each observation. Endpoint
  displacement above twice the assumed uncertainty gives `moving_candidate`;
  a complete window with diameter no greater than twice it gives
  `low_displacement_candidate`; otherwise the result is indeterminate. These
  labels do not prove an instantaneous move or stop. Defaults are 1 second and
  14 reference-image pixels, with separate horizontal/vertical bbox scales.
  The uncertainty is an exploratory sensitivity parameter, not a population
  error guarantee. Distances are reference pixels, never world metres.

## Marker evidence

Optional `MarkerReferenceInspector` compares positive and nonself-control
portraits at local peaks using the same textured reference loading, masked NCC,
0.80 similarity and 0.12 separation gates. It returns bounded appearance proposals
and their separate positive/control scores. Categories describe **reference
appearance**, not actor identity. Duplicate portraits, overlapping reference
classes and spectator/buy views cannot establish recorder ownership.

This evidence is isolated from the existing marker tracker and Map transform:
inspector proposals cannot fill a rejected position or start/continue a track.
It can show appearance evidence in a blocked view while its Map position and
region stay unknown. The optional inspection is disabled by default because it
adds full-ROI template comparisons. It has its own content-hashed reference
loader, no historical position ranking or decoded-frame cache. Actual reference
fingerprints must agree with the tracker within an observation; replacement
between the two reads discards the candidate and tracking state.

## Bind partial interiors

The isolated, non-Production Bind registry adds five **limited interior patches**:
Defender Spawn, B Long, B Window, A Lamps and A Shower/Bath. These supplement the
two original shaded plant footprints. They are not full callout or Site geometry.
The public [Bind texture](https://media.valorant-api.com/maps/2c9d57ec-4431-9c5e-2939-8f9ef6dd5cba/displayicon.png)
and [callout metadata](https://valorant-api.com/v1/maps/2c9d57ec-4431-9c5e-2939-8f9ef6dd5cba)
supply the spatial evidence. Local review corrected an initially mislabelled
Lamps entrance to the upper room and accepted Window/Shower locations only
approximately. Patch borders follow the visible-floor contour where necessary;
they are explicit measurement limits, not surveyed game callout boundaries.

The new patch geometry cap is 0.7, an uncertainty limit rather than a measured
probability. The existing plant definitions/caps, reference asset SHA-256, runtime
thresholds and operational QA mask are unchanged. Active location-label Callouts,
Topology edges and unverified build status remain unchanged. No corridor/rotation
connectivity or unobserved ally/enemy movement is inferred.

## Use

Acquire only an authorized bounded DEVELOPMENT interval first. Prepare a **private**
manifest with explicit image/source times and view evidence. Paths below are
illustrative; no private dataset is distributed:

```json
{
  "source_split": "DEVELOPMENT",
  "qualification": "development_only",
  "source_id": "local-development-source",
  "acquisition_id": "one-continuous-acquisition",
  "profile_path": "/private/local/profile.json",
  "view_evidence_kind": "source_review",
  "inspect_reference_appearances": true,
  "observations": [
    {
      "image_path": "/private/local/frame.png",
      "time_sec": 0.0,
      "frame_index": 0,
      "view": {
        "primary_state": "live_first_person",
        "values": {"player_specific_hud_valid": true},
        "state_flags": []
      }
    }
  ]
}
```

The profile must explicitly select the identified registered Map, define the
actual minimap ROI and provide private positive/negative reference paths. Manifest
split declarations are caller attestations, not proof of dataset eligibility.
Use the private intake/exposure ledger to establish eligibility before acquisition.
The CLI accepts only DEVELOPMENT declarations, 1..5000 already acquired images,
and does not scan or decode arbitrary videos or invoke full E2E.

```sh
PYTHONPATH=src python scripts/development_map_path.py \
  --manifest /private/local/manifest.json --output /private/local/path-output
```

`path_PRIVATE.html` embeds individual times, coordinates and optional source
frames. `observations_PRIVATE.json` contains the raw development envelopes and
analysis. **Keep both private; never attach them to issues/PRs or commit them.**
The slider, acquisition menu and previous/next controls select exact observations.
Playback stops at an acquisition boundary. UNKNOWN observations have no current
Map marker or bridging chord. R/N overlay labels mean positive/nonself reference
appearance matches, not known self/ally ownership.

## Same-recording development checks

The frozen 198-observation comparison retains ROI 112, accepted Bind calibration
149/149, Map coordinates 70 and named Zone results 3. These are counts, not
recognition or coordinate accuracy. Automatic ownership is UNKNOWN198 and formal
Facts/Events/evaluations are zero. Existing recognition/coordinate/track outputs
have no unintended regression; added coarse polygon candidates are intentional.

The 70 Map points form seven segments (one single-point segment), with six
multi-point spans totalling 12.6 seconds and a longest span of 5.4 seconds.
Named A plant observation spans total 0.4 seconds. Separate candidate-region
spans total 1.2 seconds in the A plant patch and 3.2 seconds in the B Window
interior. There are 24 polygon-candidate observations, including 18 coarse
B Window candidates; named Zone count remains 3. There are no actual accepted
Zone-change brackets in these clips; synthetic adjacent-Zone tests exercise that
path. The motion sensitivity check at 7/14/21px yields moving-candidate spans
5.2/1.8/0.0 seconds and low-displacement spans 2.8/6.6/8.4 seconds. This variation
shows why these labels cannot be reported as measured stops or world speeds.

The two original nonself-control portraits are now locally confirmed as allies;
this verifies their meaning only in the reference observation. Later appearance
proposals are not human-labelled allies. No new fitting, threshold adjustment or
independent qualification followed from that confirmation. Full-frame view
association, population false attribution, another Bind recording and exact
callout boundaries remain open work. The other previously exposed Map remains
unregistered. Evaluation candidate recordings were not opened.

A one-thread local replay with optional reference inspection enabled took 39.55
seconds for recognition, with 161.9 MiB process peak before export. The path
analysis itself took 0.00085 seconds. Embedding 149 private source previews into
the offline viewer raised the total process peak to 250.3 MiB (14 MiB HTML file).
An earlier same-data replay without optional inspection took 23.49 seconds;
these single-run timings are not a controlled benchmark or a new calibration
speedup claim. Disable inspection when only paths are needed. Coordinate and
tracking results were identical in both runs. Private hashes, per-observation
comparisons, sensitivity results and playback evidence remain outside Git.

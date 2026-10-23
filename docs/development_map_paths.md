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
interior. There are 24 polygon-candidate observations, including 17 new coarse
B Window candidates and one pre-existing coarse A plant candidate; named Zone count remains 3. There are no actual accepted
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

## Haven transfer and boundary sensitivity

The opt-in development loader now accepts explicit `manual_map_id: haven` as well
as Bind. Neither Map is installed in the ordinary Production registry. The
[public Haven texture](https://media.valorant-api.com/maps/2bee0dc9-4ffe-519b-1cbd-7fbe763a6047/displayicon.png)
and [published Site anchor metadata](https://valorant-api.com/v1/maps/2bee0dc9-4ffe-519b-1cbd-7fbe763a6047)
are recorded in `config/map_zone_development/haven/provenance.json`. A lossless
90-degree counterclockwise authoring transform puts A left, B centre and C right;
this does not add runtime rotation recovery. Reference/floor SHA-256 and the
visible-floor bbox are explicit. Only three shaded plant footprint **exteriors**
are registered, not whole Sites, exact plantability, obstacle holes, Callouts or
Topology. Client build correspondence remains unverified. Calibration acceptance
is not coordinate ground truth. Unregistered Maps are still rejected.

`portrait_consensus_v3` is an optional experimental marker mode. When the circular
core is below 0.80, a unique full-icon match of at least 0.80 may propose a position
only if the unique core peak agrees within one pixel and both comparisons separate
nonself references by 0.12. Whole-icon spatial ambiguity is still rejected. The
selected full-icon coordinate and `consensus_appearance_only` reason are recorded;
this is a changed **appearance proposal** policy, never ownership evidence.
Existing `portrait_v2` remains available unchanged. Temporal continuity never
selects the subject. Reference fingerprints include mode and actual file bytes.

A private profile can optionally configure `development_view_veto` with mode
`spectator_switch_v1`, `template_path`, normalized `roi`, and integer
`reference_frame_size_px: [1920, 1080]`. A reviewed switch-player UI glyph is
matched only in that authored screen region at 0.90 NCC. A match vetoes even
erroneous upstream live eligibility and breaks the position track. Invalid or
missing configured references also veto. Each output retains declared view and
separate `development_view_veto` evidence; absence of the pattern never authorizes
live/self ownership. This source-specific prototype is not a general spectator,
death or menu classifier. It does not modify or replace the Production HUD code.

Set optional `map_zone.candidate_error_radius_reference_px` to a finite
non-negative **assumption** to inspect boundary sensitivity. Each region candidate
then records signed distance to its actual polygon border in anisotropic reference
pixels and whether the assumed error disk intersects that border. An unspecified
radius stays unmeasured. `region_interior_spans_under_assumption_sec` separately
counts only adjacent, otherwise eligible same-region endpoints whose entire disks
are interior, using the same radius. This is not a calibrated confidence interval,
continuous occupancy, an accepted Zone, or an ownership claim. The viewer exposes
these fields alongside the original, unchanged candidate and named-Zone spans.

### Bounded second-source development comparison

A fixed map/context scout of the three remaining DEVELOPMENT recordings found no
additional Bind recording. The first new source was Haven (owner-confirmed),
another supplied spectator controls, and the remaining Map stayed unregistered.
Protected evaluation candidates were not opened. A single fitting scout supplied
one owner-confirmed self and two ally portrait references. Those labels apply only
to that observation. Fit and validation windows were declared before predictions;
selected native timestamps agree between bounded ffprobe and decoder output.
Private images, Profiles, times, individual paths and HTML remain local.

| New-source window | Circular core v2 | Consensus v3 + UI veto |
|---|---:|---:|
| Fitting, 20 observations: ROI / Map positions | 15 / 15 | 17 / 17 |
| Validation, 50 observations: ROI / Map positions | 40 / 40 | 40 / 40 |
| Validation calibration acceptance | 50 | 50 |
| Validation named Zones | 0 | 0 |
| Spectator control, 20: blocked by UI pattern | 0 | 15 |

The two recovered fitting observations extend its longest connected span from
0.8 to 2.0 seconds. **Held-window recognition did not improve**: seven validation
segments (including two isolated points), longest 2.6 seconds, total adjacent
observation span 6.4 seconds, ten appearance-threshold UNKNOWNs. A separate
exploratory replay of the unchanged whole-icon v1 mode gave 29/50 positions;
this comparison is not another independent qualification. All automatic ownership
remains UNKNOWN. Known scout labels and sparse visual context cannot label every
later marker. No formal Facts, Player Events or coaching scores are emitted.

The 20 spectator controls already yielded zero accepted positions with these
references before the veto. Afterward 15 explicitly block by UI pattern; five
lack that detection and still reject the appearance. No reduction in observed
false attribution or population false-positive rate is established. Even a
counterfactual spectated-subject reference stress replay yielded zero positions
before and after, so it is not evidence of recovered ownership accuracy.

The fitting window has five B-plant polygon candidates, with 0.4 seconds bracketed
by same-region endpoints, but all five touch a 7/14/21px assumed error disk: guarded
spans remain zero. Validation never produces a plant-region candidate. On the
existing Bind data, the unchanged raw A/B-Window candidate spans of 1.2/3.2 seconds
reduce to 1.0/0.8 seconds under a 7px interior assumption and zero under 14 or 21px.
This exposes boundary sensitivity rather than certifying continuous dwell time.

New-source validation processing was 12.67 seconds with v2, 12.75 with consensus,
and 13.09 with consensus plus veto; same-process peak RSS reached 157.6 MiB across
all runs. These are single bounded runs, not isolated speed or memory benchmarks.
The frozen 198 observations retain ROI112, calibration149, Map70, named Zones3,
seven segments and longest5.4 seconds, with no changed recognition/coordinate/
tracking fields. Inspector-enabled replay took35.85 seconds and164.3 MiB recognition
peak RSS, versus historical39.55 seconds/161.9 MiB; no speedup claim is made.

Haven exact world-position accuracy, stationary jitter, all-frame self ownership,
false-attribution rates, general spectator recognition and another Bind-source
transfer remain unmeasured. Few fixed marker/landmark proposals were prepared
independently of acceptance for optional human verification; unconfirmed points
are not GT. Geometry and view-context evidence still limit tactical interpretation.

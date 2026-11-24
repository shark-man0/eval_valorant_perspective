# Development minimap CNNs

The two models answer different questions. The portrait network classifies a
17-pixel BGR crop by Agent UUID. The marker network evaluates a 19-pixel
receptive field on the minimap at stride two and proposes center locations.
Evaluation can use the CNN proposals with existing portrait matching, or
compare them with CNN portrait classification. The tracker still checks
recorder view, rim evidence, competing centers and the independent reference
portrait. Its output remains development-only.

Training requires PyTorch in the development environment. Use the checkout's
package for the knowledge catalog and source guard.

```sh
PYTHONPATH=src python scripts/map_learning/train.py \
  --recording-catalog /path/to/private/catalog \
  --map-catalog /path/to/private/map-index.json \
  --asset-cache /path/to/private/knowledge-cache \
  --training-receipt /path/to/private/receipt.json \
  --output-directory /path/to/private/output
```

The receipt has schema `map_cnn_training_receipt_v1` and a `recordings` list.
Each row contains `recording_id`, `source_sha256`, `recorder_agent_uuid`,
`patches` and `sha256`. Each content-pinned NumPy archive contains
`positive` and `negative` arrays of 25 × 25 uint8 BGR center crops from the
named physical recording. Positives use a conservative previously measured
recorder marker. Negatives use a different candidate in the same frame or a
region separated from the measured marker. These labels are weak; keep
human-reviewed samples and independent matches separate from training.

For observation-bound training, export the reference replay with
`export_paths.py --learned-stage reference --training-evidence`. Pass that
report and the same `--native-manifest` to `prepare_crops.py`. Archived
comparison replays can supply a matching `--view-context` and `--method`.
The resulting record
adds `lineage` and `lineage_sha256`. Pass these records in a receipt with
schema `map_cnn_training_receipt_v2`. Each native crop is checked against its
frame's sample ID, source, bounds, category and crop hash. When the timeline
provides observation IDs, the extraction retains those as well. Competing
peaks are weak non-recorder examples. Empty regions supply a background class
for the portrait model and model-scored hard negatives feed the marker head.
Unlabelled examples still require high confidence and agreement under
augmentation before being used as Agent pseudo-labels.

Supply a private `--model-registry` path to register the two weight files as
development candidates. The registry records their source receipt and model
hashes. Model files and source-bound manifests live outside Git checkouts.

The loader verifies DEVELOPMENT and TRAIN membership in the recording catalog,
checks the source and crop bytes, and rejects duplicate physical matches.
Training combines real crops, synthetic variants of the knowledge portraits,
augmentation consistency, and high-confidence pseudo-labels for real crops
whose Agent is unknown. The marker model also trains with randomly exchanged
portrait centers so the rim can contribute independently from Agent identity.

Use `runtime.load_models` to verify the output weight digests and Agent order.
Calibration and comparisons require a separate validation set. Run
`export_paths.py --help` for the native-frame replay arguments. Select the
validation threshold and choose `--learned-stage marker` to evaluate the CNN
detector with the reference-based Agent classifier. Use `--learned-stage both`
to evaluate the two CNNs together. Both stages export the standard
development-only one-second Map report. Weight files, crop archives,
reference images, and private receipts stay outside the repository.
In the two-head mode, `--refine-center` retries a failed center measurement
using nearby native pixels. It requires two neighboring crops to support the
same marker at the original rim, portrait and reference thresholds. A
previously accepted center is retained.
Use `--recording-portraits` to search for previously unresolved portraits
against two earlier, independently accepted crops from the same recording.
The current rim, reference Agent and native continuity must also agree.
The new decisions retain the original anchor observation IDs.

Use `--path-quality` to report observed chain lengths, gaps in covered play,
and the number of seconds with Named Zones or nearby callouts. For maps
without an authored Zone file, `export_sites.py` can add only a shaded
planted area whose pinned atlas and published site anchor agree. Authored
Zones take precedence.

The trainer's `--experiment` option isolates the background class,
hard pseudo-labels and per-recording balance. The retention variant takes
a pinned incumbent to preserve established predictions while learning.
Use `--separate-head-seeds` for matched ablations so a portrait-side change
cannot also change the marker head's initialization or synthetic examples.
For an independent detector comparison, `--marker-models-directory` keeps
the portrait checkpoint while loading the detector from a second receipt.
The replay records the digest of each model receipt.

To measure a conservative complement, export the same native manifest twice
with `--learned-stage reference` and `--learned-stage both`. Give both outputs
and their common bundle to `compose_paths.py --help`. The composer retains the
reference path and uses selected CNN points only where the reference reported
unresolved portrait evidence on that exact frame. It also checks the recorder,
view evidence, and Map texture. CNN segments retain their own measured links.
The optional `--link-corroborated` records a cross-detector edge only when the
CNN measured that edge and both methods measured the same endpoint on the
same native sample with agreement within three reference pixels. The
original segments and coordinates are retained.

Use `recover_gaps.py` with the composed report and its original reference
replay to recheck vacant seconds against the exact native frame manifest. It
builds recording references from prior marker measurements agreed by the
public atlas and a base recognizer. It keeps measured primary coordinates and
edges. Pass the marker-companion composition and its base CNN replay with
`--companion-report` and `--companion-baseline` to include verified companion
positions. Conflicting new positions are left unresolved.

For continual learning, `compose_paths.py --marker-companion` takes two
two-head exports with the same portrait receipt and distinct marker
receipts. It keeps the incumbent coordinates and admits only new selected
positions with at least two native observations from the companion where the
incumbent left the portrait unresolved. Evaluate each model and the composed
result on the same admitted footage before using it.

`valorant_ai_coach.temporal.viewer --development-map-report` and the
desktop menu 「開発用: Map軌跡」 display the path alongside its exact timeline.
The timeline evaluation CLI accepts the same option to report coverage and
observed Named Zone seconds in the development report. Both verify the
timeline digest and native observations. Map candidates stay out of Fact
creation, promotion and scoring.

`export_paths.py --registration exact` uses deterministic exact descriptor
matching. `--registration recording-anchors` additionally attempts to register
an otherwise unresolved current frame against two successful earlier frames
from the same source, acquisition and minimap geometry. Both independent
matches must agree on landmark probes and the measured marker center. The
report retains the two native anchor IDs. This feature does not interpolate
trajectory gaps.

`--registration recording-anchors-contrast` additionally retries unresolved
alignments of measured positions with two deterministic contrast transforms of
the current minimap. Both atlas fits must agree on the recording Map and on
the marker and four reference probes. Recovered fits cannot become tracking
anchors.

## Replay a complete DEVELOPMENT recording

`run_recording.py` admits the exact original recording through the recording
catalog and the source policy. FFmpeg decodes the first native video frame in
each 200 ms bin, and the replay checks its PTS against the original packet
clock. The common timeline supplies the current view and life evidence for
the Map recognizers. Set `VALORANT_RECORDING_CATALOG` to your local catalog
and use a new private output directory outside the checkout. FFmpeg and
ffprobe must be installed.

```sh
PYTHONPATH=src:. python scripts/map_learning/run_recording.py \
  --policy-path "$SOURCE_POLICY" --source-sha256 "$SOURCE_SHA256" \
  --hud-config "$HUD_CONFIG" --spectator-label "$SPECTATOR_LABEL" \
  --layout config/hud_layout_1080p_v3.json \
  --map-catalog "$MAP_CATALOG" --asset-cache "$ASSET_CACHE" \
  --zones-path "$ZONES" --models-directory "$CNN_MODELS" \
  --threshold "$CNN_THRESHOLD" --output "$RUN_OUTPUT"
```

For the companion detector, supply both `--companion-models-directory` and
`--companion-threshold`. The full-frame cache can use tens of gigabytes. Use
`--frame-cache` to place it on a separate volume and `--acquisition` to replay
a receipt created by `acquire_native.py`. Hardware decoding is optional via
`--hwaccel`. `--lossless-webp` uses a smaller native frame cache with an FFmpeg
build that provides libwebp. Compare decoded pixel hashes before treating
runs from different decoders or encoders as equivalent.
With `--camera-hint`, the replay passes a private placed-camera reference to
the existing shared timeline recognizer. Use a reference for the capture
settings under evaluation and record the option when comparing coverage.
`--screen-atlas-void` also abstains on standard-pass positions well outside the
atlas artwork. A veto clears the local position chain before a rejected
candidate can supply a portrait or flow anchor. Use the default settings to
reproduce the existing six-recording benchmark. Try `--portrait-mode reference`
to keep the learned marker detector and use the external portrait matcher.
Use a fixed development comparison to select between modes.
`--contrast-registration` enables the two-fit contrast retry in this workflow.
`--verify-adjacent-learning` allows the two-head tracker to recheck a current
unresolved peak using the previous independently measured portrait. It requires
current rim and independent reference evidence, admissible continuity, and a
current direct atlas fit. Either retry remains a development candidate and
cannot seed this retry or enter newly extracted weak training labels.

The run writes `map_standard_PRIVATE.json` and `map_recovered_PRIVATE.json`,
their separate analysis directories, the shared one-second timeline, and a
completion receipt with counts, timings and artifact hashes. Compare coverage
over the seconds with current operability evidence. The separate position and
trajectory counters reflect observations and measured edges. A missing
position remains UNKNOWN.
Exact, stateless atlas fits are shared between the passes of each run. The cache
key binds the native observation and geometry configuration. Use
`--no-shared-alignment-cache` for a timing comparison. When the recorder or
Map cannot be bound, the run still saves a development result with the recovery
status and the observations it could retain.

To add a training candidate stream, use `--training-candidates` and pass the
reference report and its native manifest to `prepare_crops.py`. Points clearly
outside the atlas are excluded from this stream. The crop tool enforces the
registered TRAIN split. Keep reviewed examples for scoring.
Run `compare_runs.py --baseline … --candidate … --output …` with the two
completion receipts to compare standard and recovered coverage on the same
source, native PTS and decoded pixels. `evaluate_review.py --bundle … --report …
--review … --output …` accepts a private `development_map_independent_review_v1`
packet. Supply `timeline_sha256`, reviewer (`HUMAN` or `AI_VISUAL`) and `cases`.
Each case contains `sample_sha256`, `view` and `candidate_role`. Bind a reviewed
selection with `candidate_sha256` (the canonical evidence digest of the exact
point). A reviewed SELF point may also supply `independent_atlas_px` and its
`reference_sha256`. See the evaluator for accepted view and role values.

Gap recovery rejects a new point well outside the exact atlas artwork when
the atlas provides a transparent background. Its rejection counts are separate
from positioning coverage. Original points and links remain in the report.

```sh
PYTHONPATH=src python -m valorant_ai_coach.temporal.viewer \
  --policy "$SOURCE_POLICY" \
  --bundle "$RUN_OUTPUT/timeline/timeline_PRIVATE.json" \
  --development-map-report "$RUN_OUTPUT/map_recovered_PRIVATE.json" \
  --standard-map-report "$RUN_OUTPUT/map_standard_PRIVATE.json"
```

The viewer shows the registered atlas, current measured points, recent
measured links and registered Named Zone polygons. Each link joins observed
endpoints. When the selected second has no position, the viewer displays
UNKNOWN and leaves the current marker empty. The replay and viewer export
development Map candidates only.
The Map switch keeps the video at its current time. The next-recovery and
next-UNKNOWN controls seek both the video and timeline to the selected second.

### Batch replay and stratified review

`run_batch.py --plan … --output …` accepts a private JSON plan with
`schema: development_map_batch_v1`, `recording_catalog`, `run_options` and
`recordings`. Use the same kebab-case option keys as `run_recording.py`, such
as `hud-config` and `threshold`, and list any switches in `run_flags`
without the leading dashes. Each entry in `recordings` has a registered
`recording_id` and can specify either `acquisition` or `frame-cache`,
an optional `baseline_run` completion receipt, or `prepare_weak_crops:
true` on a registered TRAIN recording outside regression. Resolve paths
relative to the plan file or supply absolute paths. The batch journals
development use, runs the same one-second analysis for each recording,
produces weak crop lineage for eligible sources and compares each specified
baseline on exact native inputs. Review per-stage failure states in the
private batch receipt. Keep all batch data outside Git.

For a disk-constrained native acquisition, use `--png-compression` in
`acquire_native.py` or `run_recording.py`, or set `png-compression` in batch
`run_options`. Levels 0 through 9 select the lossless PNG compression level.
The default is 1. Higher levels trade encoding time for less scratch space.
Native PTS selection and decoded pixel checks still apply.

`sample_review.py --bundle … --standard … --recovered … --output …`
freezes a per-recording draw before human annotation. Its strata cover
retained, new, lost and abstained selections, with separate excluded and
uncertain view controls. Each stratum contributes at most one sample per
second and the plan includes the population size. Run `evaluate_review.py`
with `--sample-plan` and bind the review's `sample_plan_sha256` to the
exact plan. Review the chosen marker role and select its independent atlas
position separately. Leave occlusion and ambiguous matches UNKNOWN.
The report gives separate abstention and role error rates for the reviewed
sample, plus per-stratum counts and coordinate errors. An equal-quota
sample describes the review strata and needs population weighting for an
overall estimate.

Use `evaluate_review.py --candidate-report` to compare decisions with the
reviewed baseline on the same timeline. Removed `OTHER` selections, removed
`SELF` selections and removals without an exact baseline label have separate
counts. Excluded views have a separate count and can overlap those role
counts. New or changed selections require their own review to measure role
accuracy. This report preserves HUMAN or AI_VISUAL provenance and leaves the
fixed-input non-regression gate in place.

`--strict-recovery-tracking` clears the local recovery chain when reference
evidence vetoes a point, no usable atlas projection is obtained, or the
companion and portrait recovery disagree. The default remains the
reproduction setting for the six-recording development baseline.


The optional `require_non_regression` per-recording switch needs
`baseline_run`. The gate reports lost position seconds, selections or native
edges, changed Map references, and lost Zone candidates even if total
coverage grows. It also rejects any coordinate drift for a retained selection
on the same atlas and reports changes to the exact set of evidenced
operable seconds, including swaps with the same denominator. Keep the
digest-bound `map_reference_PRIVATE.json` alongside each run receipt.
`review_samples_per_stratum` freezes private review work from the run with
separate camera and death controls. Neither option requires an immediate
human answer. TRAIN rows that finish successfully produce a combined
`training_receipt_PRIVATE.json` for `train.py`. The batch admits only one
TRAIN recording per physical match and separates it from comparison matches.

`summarize_runs.py --run … --run … --output …` accepts completed run
receipts and verifies their matching Map reports. It keeps standard and
recovered coverage separate and aggregates counts by Map and recorder Agent
candidate. Coverage rates use the sum of evidenced operable seconds for
each group. Failures are counted separately by reference, learned and gap
recovery stage. Unbound Map or Agent candidates remain UNKNOWN.

`export_sites.py --plant-core-seeds scripts/map_learning/plant_core_seeds_v1.json`
supports public atlases whose plant shading cannot be traced as a simple
footprint. A core uses shaded pixels around a site seed tied to that exact
atlas hash. Sunset has A and B cores. Split A, Breeze B and Pearl A fill
previously missing plant areas. Use `--existing` to extend an exact atlas
without replacing its registered polygons. The timeline and evaluation reports count
selected observations with a unique Named Zone separately from support-only
observations and conflicting Zone candidates. All remain development evidence.

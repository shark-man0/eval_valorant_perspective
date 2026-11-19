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

`export_paths.py --registration exact` uses deterministic exact descriptor
matching. `--registration recording-anchors` additionally attempts to register
an otherwise unresolved current frame against two successful earlier frames
from the same source, acquisition and minimap geometry. Both independent
matches must agree on landmark probes and the measured marker center. The
report retains the two native anchor IDs. This feature does not interpolate
trajectory gaps.

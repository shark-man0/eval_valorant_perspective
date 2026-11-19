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

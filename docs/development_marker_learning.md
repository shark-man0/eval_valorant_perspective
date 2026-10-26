# Local development marker learning

This optional experiment compares visual features for tiny minimap patches. It
does not replace the default marker detector. A PLAYER-like appearance does not
establish recorder identity, camera ownership, a death, Map compatibility, or a
formal player location. Ownership stays UNKNOWN and formal outputs stay empty.

Install the optional research dependencies in an isolated environment:

```sh
python -m pip install '.[marker-learning]'
```

The research extra pins Torch 2.14.1 / Torchvision 0.29.1. Runtime loaders reject
Torch older than 2.10: [GHSA-63cw-57p8-fm3p](https://github.com/pytorch/pytorch/security/advisories/GHSA-63cw-57p8-fm3p)
affects weights-only loading through 2.9.1. Exact trusted hashes remain required;
`weights_only=True` is not blanket permission to load untrusted model bytes.

The normal application and CI do not require Torch, private weights or videos.
No API in these modules downloads weights or uploads images. Acquire any model
separately from its primary publisher, verify its license and exact SHA-256, and
retain the bytes outside Git. Keep images, embeddings, fitted classifiers, model
weights, source identities, native timestamps and labels private.

## Four distinct experiments

1. The existing NCC/circle/cross generator supplies unchanged candidate centers.
2. `handcrafted_features` supplies a fixed color/gradient comparison baseline.
3. `FrozenMobileNetFeatures` loads explicitly supplied Torchvision
   `MobileNet_V3_Small_Weights.IMAGENET1K_V1` state-dict bytes. `local64` uses the
   first four feature blocks and 2x2 pooling (96 dimensions); `global224` uses the
   full backbone and global pooling (576 dimensions). Both apply BGR-to-RGB,
   ImageNet normalization and area resizing. These are deliberately different
   patch experiments, not the standard ImageNet whole-image accuracy protocol.
4. `train_masked_encoder` trains a small three-convolution encoder and decoder on
   admitted unlabeled SSL_TRAIN patches. It reconstructs randomly masked 4x4
   blocks of 32x32 inputs. It is a domain SSL model trained from scratch, **not**
   DINO training or fine-tuning of the frozen ImageNet backbone. The two sources
   of features must be reported separately.

Upscaling a tiny crop adds no original pixel detail. A patch classifier cannot
recover markers that the candidate generator never proposed, and cannot improve
their centers merely by assigning a semantic class. Close objects, overlapping
portraits, ambiguity and clipped patches remain separate measurement problems.

## Admission, physical-match splits and labels

`development_learning_dataset` records accepted source receipts, trusted manifest
and allocation hashes, source SHA, integer native PTS, canonical timebase,
acquisition epoch, frame/pixel hashes, actual ROI, extraction and Exposure
fingerprints. The caller must validate the real registry and independently
obtain the trusted anchors; equal caller-supplied strings alone are not admission.

Fix these roles by physical match before feature fitting:

| Role | Permitted use |
| --- | --- |
| SSL_TRAIN | Unlabeled self-supervised fitting, train-only clustering |
| DEVELOPMENT_TRAIN | Human-confirmed supervised fitting, train-only clustering |
| DEVELOPMENT_VALIDATION | Method and rejection-policy selection |
| DEVELOPMENT_FROZEN_TEST | Human review and evaluation after method selection |

Unknown physical duplicates must share a conservative leakage group. Different
file hashes or generated source IDs do not establish independent matches. A
group, source SHA, encoded frame or decoded frame cannot cross roles. Multiple
patches in one frame bind their labels to distinct explicit ROIs. A label with
no ROI is rejected when it could refer to multiple patches.

Unlabeled, pseudo and human-confirmed labels have separate origins. Unlabeled
records stay UNKNOWN. Supervised fitting accepts only non-UNKNOWN human labels
from DEVELOPMENT_TRAIN; neither pseudo labels nor visual clusters become GT.
Do not use frozen-test images for SSL, pseudo labels, clustering fit or method
selection. Previously exposed development images remain exposed, regardless of
the name of a new local split. A development frozen test is not independent
whole-model qualification, particularly with UNKNOWN_EXPOSURE history.

## Feature, model and inference contracts

`bound_patches` independently checks exact native sample/pixel identity, copies
complete bounded local windows and returns an acquisition fingerprint. It does
not pad clipped observations or infer unseen pixels. Model encoders accept at
most 256 patches per call and use bounded inference batches. Weight files are
rehashed before and after each inference, and loading uses `weights_only=True`.

`fit_centroids` consumes validated human patch labels. Class centroids, feature
configuration, distance and margin rejection enter the classifier fingerprint.
These scores are cosine distances and margins, **not calibrated probabilities**.
Low support, ambiguity, unknown appearances and missing class coverage require
UNKNOWN rather than a forced label. Fitting and saving a classifier is not proof
that its policy generalizes.

`save_centroids`/`load_centroids` use bounded tensor/JSON NPZ snapshots with exact
file SHA verification, bounded decompressed members and `allow_pickle=False`.
They never overwrite snapshots. Serialized unit prototypes are preserved exactly
instead of renormalized again on reload; this avoids floating-point fingerprint
drift. Fit receipts bind datasets, human labels and feature fingerprints.

`review_proposals` adds a separate `appearance_class_review` to each existing
unassigned proposal. It deep-copies the result, rechecks native pixels, rejects
formal/assigned locations and Zones, and retains all original coordinates and
candidates. It does not filter, interpolate, generate tracks or emit events.
Current-frame geometry, Map-build qualification, context rejection and ownership
remain the existing producer's independent responsibilities. A research harness
may compare explicit filtered subsets, but must separately report abstentions,
candidate-generation recall and previously correct detections lost.

## Bounded SSL experiment

`MaskedTrainingBudget` limits image count, epochs, updates, wall time and batch
size. Training requires explicit one-thread CPU control and uses no semantic
labels, temporal positive pairs or inferred marker identity. Patches bind to
admitted SSL frames and frozen content hashes. The caller retains immutable
native acquisition evidence; the learner does not recreate it from metadata.
The exported encoder is a small tensor-only state dict, independently hashed.

Record the selected budget before training. Report effective updates and stop
reason as well as the requested budget. Masked reconstruction loss is not marker
accuracy, clustering purity, camera-state accuracy or owner evidence. Report a
failed/ineffective model without adopting it. The wall budget is checked between
updates; it is not a hard operating-system deadline for a single update.

## Evidence and acceptance

Compare all methods on the same native observations and unchanged human labels,
using the existing 2px one-to-one localization criterion. Separate normal PLAYER,
death-marker, UI, background, UNKNOWN and unreviewed/out-of-scope cases. Only
complete, consistent annotation scope supports detection precision/recall.
Classification on GT-centered crops and end-to-end candidate detection are
different measurements. Show TP/FP/FN, F1, confusion/UNKNOWN, center errors and
old-correct losses with denominators, source roles and method-selection exposure.

Use the same 18-input benchmark for existing methods and hybrid inference.
Separate model load, features, classifier, proposal/geometry and decode time;
record effective library thread control and process peak RSS. An isolated-process
median/range is not an all-input guarantee. Do not compare Python allocations to
process RSS or claim unverified environment settings are effective thread limits.

Torch-free synthetic tests cover source/split/label safety, model-change rejection,
native-bound proposal review, classifier snapshots and deterministic clustering.
Real local model fits and inference must additionally pin weight hashes,
dependencies, device, threads, seeds, datasets, timing and output digests. CI
success is a contract check, not recognition qualification.

## Model sources and terms

- [Torchvision V3-small weight description](https://docs.pytorch.org/vision/stable/models/generated/torchvision.models.mobilenet_v3_small.html)
- [Pinned model implementation](https://github.com/pytorch/vision/blob/v0.29.1/torchvision/models/mobilenetv3.py)
- [Torchvision code BSD-3-Clause license](https://github.com/pytorch/vision/blob/v0.29.1/LICENSE)
- [Pretrained-model terms and preprocessing caveats](https://docs.pytorch.org/vision/stable/models.html)

The library code license does not establish rights to all pretraining datasets
or blanket permission to redistribute a fitted application. This experiment
does not publish weights or approve Production use. DINO-family code and each
specific weight release also require separate checks; a model name alone is not
a license or a suitable tiny-patch feature specification.

Related: #21 (identity evidence), #62/#84 (private intake), #89 (unassigned
cross-appearance baseline). No main merge or HUD/Production schema change.

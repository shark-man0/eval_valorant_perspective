# Offline HUD feature experiments

These helpers compare local image features with frozen HUD readers. They do not
implement qualified Score, Round End, Start, identity, Fact or Event producers.
No application entry point imports them. Torch and private weights are optional
research dependencies, excluded from the production package and ordinary CI.

Freeze the verified registry allowlist, physical-match grouping, train/validation/
frozen-test roles, original Reader/Profile/assets, Native acquisition plan, model
versions, seed and compute limits before observing experiment outputs. A new SHA
does not establish a different physical match. SSL consumes image content even
without semantic labels; frozen-test matches must not enter SSL fitting.

`hud_feature_contract.validate_split` checks physical group, source, exact parent
image, Profile and patch bindings. The allowlist must come from a separately
verified private registry receipt. `fit_verified_dataset` additionally restricts
fitting to explicitly selected `SSL_TRAIN` spatial samples with no labels. It
passes image pixels only into the network. Source IDs, hashes, timestamps, epoch,
Round number and expected scores are integrity metadata, never model inputs.

The optional `hud_feature_learning` backend provides a 55,920-parameter CNN and
same-image contrastive training. Positive views use bounded brightness/noise;
there is no glyph-removing crop, flip, warp, reconstruction-as-evidence, or
assumption that adjacent frames share a semantic state. Repeated HUD states can
still create false negatives in contrastive learning. A decreasing loss alone
does not prove semantic recognition. This is a small local experiment inspired
by [SimCLR](https://proceedings.mlr.press/v119/chen20j.html), not a reproduction
of that paper's ImageNet training or results.

The generic baseline loads explicitly supplied, SHA-bound Torchvision
[MobileNetV3 Small](https://docs.pytorch.org/vision/0.24/models/generated/torchvision.models.mobilenet_v3_small.html)
weights. ImageNet supervised pretraining is reported as supervised generic
pretraining, not self-supervised VALORANT training. Whole small ROIs are
letterboxed without a centre crop. Record original ROI dimensions and the effect
of resizing; a feature vector is not a transcription. Review upstream model/data
terms independently from the Torchvision BSD licence. No weights are downloaded
implicitly or redistributed with this code.

Private callers record Source SHA, integer PTS, rational timebase, acquisition
epoch, original encoded/pixel hashes, ROI, Profile, patch hashes, split and
Exposure. `verify_patch` validates the retained patch bytes and ROI; it does not
replace Native decoder/source acquisition verification. Keep original receipt
anchors and verify the source before and after acquisition using the existing
decoder. Append actual training, inference and review exposures without rewriting
the initial UNKNOWN history. Keep model/checkpoint hashes and a pinned environment
beside the private experiment output. `load_encoder` verifies size/hash and uses
`weights_only=True`; do not load arbitrary pickled models.

Fit clustering centres on training features only and assign other sets to those
fixed centres. Report source/background/ROI distributions; do not name clusters
as confirmed semantic classes. Any Human-labelled prototype/head is supervised
readout, separately reported from SSL. Group cross-validation by physical match.
Incomplete vocabulary and absent labels require UNKNOWN or an explicitly
unaccepted diagnostic hypothesis. Never report unlabelled consistency as accuracy.

`adjacent_change` refuses foreign sources, epochs, duplicate/reversed/missing PTS
and incompatible timebases. It emits image-change measurements, not semantic
End/Start or visibility transitions. Content cuts can occur despite regular PTS;
keep visual continuity UNVERIFIED until independently established. Existing
Lifecycle and source-continuity gates remain necessary. Display persistence is
not new appearance. Human display brackets do not measure internal game time.

`guarded_score` withholds disagreement, missing Reader evidence or unsupported
Geometry. Agreement is unqualified development evidence. A hybrid that loses
known correct readings or accepts a wrong/dropped digit is not adopted. Preserve
all ten digit competitors and the frozen production thresholds in any actual
reader integration. The appearance prototype experiment itself does not provide
that all-ten-class guarantee and cannot replace the Score reader.

Normal CI runs synthetic admission, hash, split, discontinuity, digit-drop and
UNKNOWN contracts without model weights. Separately run the real pinned model on
the same Native inputs as the baseline, including confirmed labels, natural
controls and fixed regression observations. Record training/inference time,
initialization, CPU/GPU availability, RSS, weight/cache sizes, reproducibility and
data-amount ablations. Unmeasured semantic precision, recall, background masks,
disappearance, FULL interval negatives and internal End accuracy remain unmeasured.
Do not create labels from predictions or publish private frames, paths or hashes.

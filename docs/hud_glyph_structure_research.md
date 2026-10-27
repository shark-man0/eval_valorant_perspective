# Offline Score structure experiments

This optional study builds on the hash/split/Source safeguards in PR #92. It
compares representations that preserve different amounts of spatial detail.
No model, checkpoint, private label or prediction is included in the application
package. No production Reader, Geometry, lifecycle threshold or canonical GT is
changed, and no formal End/Start or player Fact is emitted.

`hud_glyph_learning.StructureConfig` fixes input dimensions, intermediate
pooling, final spatial grid and shallow/deep architecture. Same-image contrastive
fitting uses independent sampling and per-step augmentation RNGs, so changing
input resolution does not silently change subsequent batch ordering or gain and
offset factors. Complete ROIs are letterboxed; there is no glyph-removing crop,
flip, geometric warp, or reconstructed digit as evidence. Initial convolutions
share a seed across paired configurations, and the projection head is seeded
separately. Grid changes also change projection parameter count: do not attribute
their effect to spatial resolution alone. A shallow encoder changes multiple
factors and is a candidate comparison, not a single-factor causal test.

Freeze configs, budgets, actual input identities, Source grouping and readouts
before inspecting new outputs. Reuse separately verified DEVELOPMENT admission
and the existing Native decoder. Preserve Source SHA, integer PTS/timebase,
epoch, encoded/pixel hashes, ROI, Profile, config and checkpoint fingerprints.
`load_structure` rejects a config/hash mismatch before loading optional weights.
The feature input is pixels only; identifiers and times are provenance, not
neural features. No automatic network downloads occur.

Same-image contrastive fitting is image-only SSL. A class prototype, ridge
readout or supervised CNN trained with Human text is supervised and must be
reported separately. Contrastive loss can treat different images of the same
digit as negatives. Lower loss does not establish digit discrimination. Compare
untrained encoders with the same architecture/initial seed, complete-pixel
features, fixed pretrained features, and a small supervised CNN before attributing
failure solely to pooling, information capacity or label count.

`fit_slot_readout` uses Human-confirmed visible Score strings to supervise length
and left-to-right digit slots, with all ten digit columns present. It withholds
unsupported predicted classes and noncanonical/leading-zero strings. A Human
whole-Score transcription is not automatic pixel-level glyph-box GT. Do not turn
an unverified component proposal, reconstruction, Reader output or game-rule
inference into a Human digit label. `fit_supervised_structure` is a separate
small supervised CNN; its label provenance must be explicit. Fits reject
forbidden physical groups and non-Human/pseudo labels. Synthetic supervision,
when used, remains explicitly synthetic.

Group by physical match. Existing repeatedly used regression points are exposed
development data. New recordings already used in development cannot become
independent qualification material by naming a split `FROZEN_TEST`. Keep current
frozen-match pixels/labels out of all fitting, and do not adjust parameters after
their test outcomes. Per-fold development probes may use different group roles
only when each fold's train/validation groups are disjoint and recorded. In-fit
accuracy, source-held-out probes and fixed-test observations are distinct results.

`score_sequence_report` counts complete scores, withheld outputs, digit drops
and one-to-two-digit errors. Its digit confusion matrix has separate UNKNOWN and
LENGTH_ERROR columns. A length mismatch credits no guessed correspondence; its
unaligned predicted digits contribute to the conservative FP count. Digit
precision/recall is conditional on the annotated points. Support-zero classes
have unmeasured recall. Unlabelled predictions are not false positives, and a
correct digit string says nothing about player ownership or game-internal time.

Keep a baseline-preserving evidence side channel when comparing learners:
Source/Geometry gates still control admission, existing accepted readings are
not silently overwritten, and model-only hypotheses remain unaccepted until
their error/UNKNOWN behavior and transfer are independently supported. Agreement
is not semantic GT. Reject models that add wrong readings, lose known correct
outputs, or cannot reject cropped/occluded digits. Report a failure or negative
adoption decision when the evidence does not justify integration.

Ordinary CI runs config, split, finite-budget, digit grammar, unseen-slot,
supervised-label provenance and length-error contracts without Torch or private
weights. Run real model fitting/inference, device timings and memory measurement
separately in a pinned local environment. Record cold/warm initialization and
inference conditions. Run unchanged lifecycle regression/natural controls, all
relevant tests, Ruff/mypy and Linux/Windows packaged startup checks. Real images,
labels, Source-specific times, checkpoints and detailed outputs stay private.

## Fixed development study outcome

The paired study used 144 unlabelled Score patches from six training matches.
Six SSL variants changed input size, intermediate pooling, spatial grid, or a
shallow architecture. Two supervised CNN controls brought the total to eight
neural fits. Same-image SSL used no digit labels. Human transcriptions added 42
Score fields from 21 images, including all ten digits and seven two-digit
fields: 28 training, four validation and ten frozen-test fields. The frozen
test covers two developmental matches and only one two-digit field. It is not
independent qualification material. No parameters were tuned on its results.

| Fixed representation/readout | Legacy 16 pairs | New validation fields | New frozen fields: correct / wrong / withheld |
| --- | ---: | ---: | ---: |
| Existing Reader, raw numeric output | 15/16 | 4/4 | 9 / 0 / 1 |
| Previous mixed-ROI SSL + Human ridge | 1/16 | 0/4 | 1 / 9 / 0 |
| Shallow spatial SSL + Human ridge | 3/16 | 2/4 | 4 / 6 / 0 |
| Fixed generic pretrained features + Human ridge | 12/16 | 2/4 | 9 / 1 / 0 |
| Small supervised CNN, new-match labels | 1/16 | 2/4 | 3 / 7 / 0 |

The raw numeric benchmark is separate from Geometry admission. Applying the
unchanged Geometry gate to the Reader yields 14/16 legacy pairs and eight
correct/two withheld frozen fields. This is not a new learner regression.
All learner strings in the table remain unaccepted diagnostic hypotheses.

On the source-grouped old-data probe, changing resolution alone did not help.
An untrained shallow encoder with the same ridge readout scored 10/16 pairs,
versus 7/16 after SSL; the current contrastive objective therefore did not earn
adoption. A retrospective audit of the fixed batch sampler found 278 repeated
same-Human-Score negative pairs among 5,395 pairs with both labels known. Only
28 of 144 training images had Human labels, so this is a lower-bound diagnostic,
not a causal estimate or the complete false-negative rate. Feature-space
separation and source associations are descriptive, confounded development
observations. Neither pooling nor resize alone explains the failure.

No learned replacement or numeric-rescue hybrid was adopted: some reduced
UNKNOWN by producing wrong digits, lost known correct readings, or transferred
poorly. A baseline-preserving side channel accepts no extra numbers. Human
background categories were unanswered; automatic border-brightness/texture
bins are provisional diagnostics, not verified background strata. The next
useful study needs diverse confirmed glyph/foreground evidence and meaningful
abstention controls, rather than further tuning against these frozen matches.

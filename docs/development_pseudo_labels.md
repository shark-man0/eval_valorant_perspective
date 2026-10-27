# Human label reuse and development pseudo labels

These opt-in APIs prepare small appearance-classification experiments. They do
not change the default detector, Map geometry, camera/recorder identity, facts,
events, or coaching. Machine labels are hypotheses; ownership stays UNKNOWN and
formal outputs stay zero. No private images, metadata, embeddings, fitted assets
or weights belong in Git.

## Exact-observation human reuse

`HumanReviewReference` retains a `FrameRecord`, the original human `FrameLabel`,
review hash, prediction visibility, prior-use hashes and unmeasured click error.
The caller verifies the actual private review evidence and trusted source registry;
a matching hash string alone is not human confirmation or source admission.

`HumanLabelInventory` deduplicates references without creating labels. Conflicting
human annotations fail closed. Lookup binds Source SHA, frame/pixel hash,
acquisition/epoch, native PTS/timebase, frame size, ROI and study split. Similar
pixels at another time do not inherit the annotation. A known source/frame cannot
be reclassified across splits during lookup. Changed experiment bookkeeping does
not require another annotation of the same native ROI.

A human UNKNOWN answer, an UNREVIEWED observation and an OUT_OF_SCOPE observation
remain distinct. A manual click is not an exact physical-center GT, and 2px
agreement is only the fixed comparison convention, not annotation accuracy.

## Pseudo candidate and admission contracts

`generate_candidate` checks the exact expected teacher fingerprints and native
patch binding, recording distances, margins, shared dependency groups and an aware
generation timestamp. Disagreement, rejection or ambiguity stays UNKNOWN. Scores
and teacher agreement are not calibrated probabilities or independent evidence.

`PseudoLabel` states are PSEUDO_CANDIDATE, PSEUDO_ADMITTED_FOR_TRAINING or UNKNOWN.
HUMAN_CONFIRMED is reserved for the separate original human `FrameLabel`; a pseudo
record cannot use that state. Immutable input fingerprints detect changed Source,
PTS, epoch, pixels or ROI. Classifier thresholds and teacher fingerprints enter the
policy fingerprint and are rechecked during admission and fitting.

`validation_diagnostic` uses separately human-confirmed VALIDATION observations,
not pseudo labels, resubstitution or frozen-test observations. The initial policy
requires at least three predicted positives and observed precision at least .9.
This small-sample gate is a bounded development admission rule, **not** a precision
guarantee or qualification. The caller must retain its actual observations and
error counts. A perfect small sample cannot establish population accuracy.

Version 1 admits semantic pseudo training only for normal PLAYER and only in
DEVELOPMENT_TRAIN. Death, UI, background and UNKNOWN are excluded from pseudo
training because their support/transfer evidence is insufficient. SSL_TRAIN may
supply pseudo candidates or review inputs but never changes its semantic-training
role. Validation and frozen sources cannot receive pseudo labels. Study roles and
Exposure histories remain unchanged.

## Small semi-supervised fit

`fit_semisupervised_centroids` preserves the human-only fitting contract. It
validates the combined lineage and explicit pseudo origin before fitting:

- Machine records require fixed-policy admission and rechecked teacher votes.
- Exact duplicate patches and duplicate native-frame pseudo samples are rejected;
  at most two pseudo samples per source and twice the human class count are used.
- Default pseudo weight is .1, with total pseudo mass capped at .25 of the human
  class mass. These are fixed study settings, not probabilities.
- Human death/UI/background prototypes remain unchanged. A candidate fit that
  makes a formerly correct human-negative training example wrong or UNKNOWN is
  explicitly rolled back; attempted and effective pseudo counts are separate.

This training guard does not prove generalization or preserve every detector
match. Report independent raw candidate generation, crop classification and any
candidate-subset policy separately, including old matches lost. Keep UNKNOWN in
the raw proposal stream and do not infer unseen centers or routes.

## Counting supervision and evaluation

A student with eight human labels cannot claim an eight-label budget if its pseudo
teacher was trained on all 24. Fit each teacher on the same budget as the student,
and also report validation labels used by policy selection. Fixed classical
reference banks have earlier supervision that must not be silently counted as
zero. Retrospective label-budget simulations are not measured human time savings.

The existing 24 train, 9 validation and 14 after-selection labels retain their
roles. The 14 comparison crops were already viewed in the preceding study; replay
is exposed DEVELOPMENT regression, not a new independent test. They do not select
new rules. Final qualification needs future unused physical matches.

A zero-additional-review development comparison is possible with these labels.
Do not request them again. If an active-learning batch is later prepared, keep
hard-case selection separate from a probability-sampled audit. Proposed queue
reduction is not the number of reviews actually saved, and preparing a UI is not
completed human review.

Torch-free tests cover source/split/pseudo-origin violations, teacher drift,
UNKNOWN, replay binding, duplicate weighting and a negative-regression rollback.
Real local fits and private data comparisons remain separate from platform CI.
This API builds on #91 and does not change its human-only fitter or Production
contracts. Related: #21, #62, #84.

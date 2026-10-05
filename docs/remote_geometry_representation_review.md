# Remote geometric-interface representation review

## Reproducibility

Starting shared commit: `e9240ad3a37f85cd74970b92021ed7457353a25c`. Production analyzer remains `f291ded6140a802aec9098c22ea96ef6d7b29e2a`; no positive UI matcher is activated. Its clean E2E run is `20261004T234911Z-092d7437`, metadata `git_is_dirty=false`, evaluation 22 passed / 56 failed / 4 not evaluated and negative assertions 20/0.

Video SHA256: `71d58558559d6f578433ce9f234bf176f76fd5a86657dbfe3eba1e7d36136b06`. Layout SHA256: `a3678bcd9df35d0932ae0e69495eb5b87a3ab40e9c988560d502a9507d59eef1`. Active sidecar SHA256: `8e764d6eb2b7a6a8ce6a5f144300bdf809f16f9dcf2b689ac659333c2265b615`. Runtime Remote has no learned subtype asset in this profile. Candidate images, descriptors, masks, source mappings and all timestamps remain private.

## Cohorts and exposure limits

A frozen appearance-based retrieval produced 24 root-reviewed unique images, with six purple angular full-screen map-like/interface appearances and 18 controls. The latter include purchase grids, gray expanded tactical maps, ordinary world/smoke/effects and a death/report mesh. Three opaque purple effects provide insufficient pixel evidence for a geometric interface. Labels describe visible image structure, not GT mode or Agent identity.

The preassigned native-block parity split yields three training UI examples and three development-holdout UI examples, with eight training controls and ten holdout controls. All are the same recording; root saw all review images before representation design, and adjacent blocks can share an occurrence. This is development validation, not untouched independent-video holdout. A further 42 previously reviewed context images provide 31 world/hand/effect cases, ten death/report textures and one world/scoreboard/report case. Prior selection used saved states as strata, not semantic training truth. No GT, expected mode, Agent, native time or runtime score is an input to the descriptor.

## Measurement correction

Version 1 is invalid for representation decisions. It extracted display-composite rows 0:400 instead of the actual source crop at rows 20:420, and black-filled an excluded band before Sobel differentiation. The former mixed a display border with the crop; the latter could create an artificial horizontal mask edge. Its recipe and results remain private and unchanged for audit. Do not combine its numbers with corrected version 2.

Version 2 verified exact equality of the display crop and decoded source JPEG crop for all 66 cases. The actual crop is 400x400 pixels. `scripts/diagnostic_edge_geometry.py` computes unsigned, magnitude-weighted spatial HOG from original grayscale pixels. A 3x3 mask erosion admits only gradients whose entire Sobel footprint is valid, including explicit exclusion of image borders. It never differentiates a black-filled mask. A randomized excluded-pixel ablation produced exactly identical descriptors. The lower band exclusion can still discard useful UI edges and does not prove that every hand/weapon/icon pixel has been removed.

The frozen representation is 8x8 spatial cells with eight unsigned orientation bins, global L2 normalization, and descriptive cosine similarity to the normalized mean of three training UI descriptors. The upper-mask and full-ROI ablation use the same train/holdout/control cohorts. These similarities are not confidence probabilities or production acceptance scores.

## Corrected distributions

| Cohort | Count | Upper-mask min / median / max | Full-ROI min / median / max |
| --- | ---: | --- | --- |
| Training UI appearances | 3 | 0.7202 / 0.8115 / 0.8317 | 0.7131 / 0.7942 / 0.8167 |
| Training controls | 8 | 0.2411 / 0.3918 / 0.4535 | 0.1200 / 0.3844 / 0.4608 |
| Development holdout UI appearances | 3 | 0.5605 / 0.7265 / 0.7533 | 0.5595 / 0.6934 / 0.7198 |
| Development holdout controls | 10 | 0.1617 / 0.3425 / 0.7088 | 0.1581 / 0.3744 / 0.7246 |
| Prior reviewed context controls | 42 | 0.1929 / 0.3400 / 0.7504 | 0.2473 / 0.3787 / 0.7280 |
| Prior death/report texture subset | 10 | 0.4299 / 0.7332 / 0.7504 | 0.4003 / 0.7132 / 0.7280 |

The masked control maximum exceeds the lowest holdout UI score. Death/report textures have a median comparable to the two stronger holdout UI examples. Full-ROI ablation does not remove the overlap. Even training examples do not reach 0.90 against their mean descriptor. A threshold sweep or lowering would not prove view identity, independence, invariance or contradiction rejection. No positive production representation follows from this descriptor.

## Decision and next evidence

`NEED MORE EVIDENCE` for a positive Remote matcher; reject this mean spatial-HOG representation as a sufficient identity source. The existing texture qualification correction stays active and all live gates remain unchanged.

Next experiment is already a separate diagnostic: test whether HOG normalization conflates dense fine character-mesh texture with broad angular interface boundaries. Freeze Gaussian scale-space measurements at sigma 0/2/4, exclude the entire smoothing-and-derivative footprint at masked boundaries, compare absolute gradient support, scale persistence, contour/long-boundary population and spatial spread on the same cohorts. This measures a failure mechanism, not a threshold optimization. Before any adoption, require independent support groups, insufficient-evidence rejection, observable-contradiction rejection and genuine holdout separation; neither a single high normalized score nor low variance establishes a mode.

## Artifact receipts and checks

Corrected recipe SHA256: `645e1d3c51277cf408fb5db78b962867fc9544ee3dca22cc6a3ced0e70feaa43`. Crop provenance SHA256: `b22e21324e731a8920717f5717997cf6b67df92da511e9a80e9f0dc114b925db`. Corrected results SHA256: `f68809e43d2bb452345a73fd37918662b94529db1ef54d81caca45fa903fef92`.

Six focused diagnostic-kernel tests pass: arbitrary excluded-pixel changes cannot change features, constant valid regions do not acquire mask-border edges, insufficient masks yield no gradient support, visible distributed edges remain measurable, and malformed mask geometry/type rejects. Ruff passes for src/tests/scripts; mypy passes for the existing 86-file source contract. Full pytest: 867 passed / 2 existing skips (266.21 seconds). Diff check passes. This diagnostic-only phase does not require a new production Clean E2E.

## Scale-space mechanism result

The next frozen diagnostic reverified source-crop equality for all 66 cases and applied Gaussian sigma 0/2/4. Explicit finite Gaussian radii plus Sobel footprint require mask erosion radii 1/7/13. Randomizing excluded pixels left descriptors and valid-region metrics exactly identical at every scale. The descriptor still receives no time/state/GT/Agent/runtime-score inputs.

| Measurement | UI training median | UI development-holdout median | Death/report texture median |
| --- | ---: | ---: | ---: |
| HOG similarity, sigma 0 | 0.812 | 0.727 | 0.733 |
| HOG similarity, sigma 2 | 0.748 | 0.663 | 0.625 |
| HOG similarity, sigma 4 | 0.745 | 0.635 | 0.379 |
| Gradient magnitude ratio, sigma 4 / sigma 0, common valid support | 0.465 | 0.482 | 0.040 |

Fine mesh texture loses substantially more gradient magnitude under smoothing than the broad interface boundaries. This explains one contributor to the earlier HOG overlap. It does not prove that all world textures separate. At sigma 4 the death/report maximum similarity is 0.425 versus lowest holdout UI 0.477, but other holdout controls still reach 0.611 and overlap the UI examples. Canny edge population differs strongly (UI medians about 3.2--3.3 thousand versus death/report 36.4 thousand), while long-component counts are similar; death/report also has more straight-line support pixels. Long-contour amount or linearity alone therefore fails as an identity witness.

Scale-space recipe SHA256: `c1926543a82e1a6bc7d13b5c0f74463a727f14d0ddc9b3962801ee324e8585b5`; script SHA256: `8571ff171079b098d91e666e06d4df55d04159e54e818bff9cdea7f65cdb47eb`; provenance SHA256: `51a2c56cb6089ac066085365d8b6a69e307f648766c3dc8f6a2df357e0b86d62`; results SHA256: `86b76cd50ee86ac5dccf3bfc9b4a70995d90b5438238bdd433b823f65daf0049`.

No representation is promoted. The remaining bounded diagnostic identifies which appearance controls still overlap and describes their original palette evidence, without fitting a cutoff. A resolved fine-texture mechanism and a failed descriptor are concrete evidence for choosing the next experiment; they do not authorize UNKNOWN-to-positive conversion.
## Conditional overlap checkpoint and next priority

The bounded palette slice recomputed the existing HSV coverage score on exact original crops; all 24 candidate-case palette scores reproduce their saved values exactly. Six of six UI appearances pass the existing palette >=0.90 gate. Shop controls (four) and gray expanded maps (three) do not pass it. Purple smoke/effect controls pass it, as do four of seven ordinary world/hand controls. Thus color is not a mode witness.

At sigma 4, one candidate death/report mesh and one earlier first-person/world/hand-effect context overlap the weakest UI HOG score and both pass the palette gate. Both have scale-persistence ratio about 0.016, unlike the UI cohort's 0.414--0.683 range. This is promising descriptive evidence for the fine-texture mechanism; no joint cutoff, class probability or production positive is fitted. It does not establish independent UI support groups or recording-independent invariance. Conditional artifact SHA256: `828aab3cced4fdeebfaa1c91dae1c8efe8a7296a3e50b1040d235bb89077c18d`; script SHA256: `552b5821491c4e3350b4962337facb02d2bcafdc3a69b1e54171016bb375f732`.

This closes the current exploratory logical phase. Keep the texture qualification correction; do not adopt the examined HOG representation. Following the user's added priority, implement two regression lanes next: deterministic canonical PTS frames and frozen production-coverage frames replayed through actual runtime components, alongside unchanged adaptive production E2E. This infrastructure must precede the next behavior change so paired detector changes and sampling changes are measured separately. UI topology/support validation and independent Buy-menu challenge remain subsequent candidates; completing the replay infrastructure is not a stop condition.
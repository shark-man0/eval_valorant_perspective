# R1 source-world track footprint audit

## Problem

Target: `GT-R1-ROUND-START` and its upstream scene/UI contract. The existing diagnostic compares a central 15-pixel adjacent/seed patch but current-frame world masks remain manually reviewed. Before replacing those reviews, measure the larger 21-pixel flow and 31-pixel original-seed footprints without assigning semantic background labels.

## Evidence

Main: `80d0d460b8e3a76d3c181e035c72cd10026f4252`. Source video, native PNG/pixels, code and all 30 input images were bound before/after measurement. The exposed source is one recording; no independent holdout or qualification claim is made. [Declaration](../e2e_reports/match_001/scene_track_footprint_declaration.json) and [results](../e2e_reports/match_001/scene_track_footprint_development.json) contain hashes, transforms, coordinates and scores without image assets.

## Competing hypotheses

Central matching might hide current occlusion in the larger context. Conversely, projected original-source appearance might remain strong across the R1 transient. Even strong footprint appearance may fail spatial quorum or fail to establish semantic absence of foreground. The camera model and original tracker were frozen; no threshold/model variant is selected from this run.

## Independent image evidence

| PTS | Candidate tracks | 15px support | 21px support | 31px support | All sizes support | Two-row spatial support |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| 4.086003 | 69 | 68 | 69 | 69 | 68 | False |
| 4.102669 | 68 | 66 | 68 | 68 | 66 | False |
| 4.119336 | 65 | 65 | 65 | 65 | 65 | False |
| 4.136003 | 64 | 64 | 64 | 64 | 64 | False |
| 4.152669 | 61 | 61 | 61 | 61 | 61 | False |
| 4.169336 | 61 | 61 | 61 | 61 | 61 | False |

All critical all-size witnesses belong to seed regions 1, 2 and 5, in a single spatial row. Larger footprints strengthen local appearance evidence but do not recover the missing upper-row identities. The 31-pixel original-source patch still matches through phase disappearance, both transient timer images and the first active display. This shadow audit receives no timer, phase, GT, native timestamps or current manual world masks. It samples the full declared square using the unchanged source-camera transform; every interpolation tap must remain in bounds and outside protected clock/phase pixels. No mismatching pixels are excluded from NCC.

## Continuity decision

Visible scene continuity remains supported by the earlier distributed, manually reviewed whole-crop experiment. These point footprints alone cannot authorize scene continuity because they fail the independent spatial quorum. Failed spatial/appearance support is unknown, not evidence of a content cut. Hidden uninterrupted game time remains unproven. No runtime boundary follows.

## Contract change

Only a pure passive audit is added outside production. Output reports matched appearance, explicitly `world_mask_authorized=false` and `runtime_proof_authorized=false`. Mean NCC cannot establish an entire patch as foreground-free: a small synthetic foreground edit still passes NCC 0.90, while a larger surrounding occlusion fails 21/31 pixels despite an exact central 15-pixel match. Therefore neither strong mean NCC nor the projected transform can be converted into a whole-ROI semantic mask. Existing producer acceptance decisions are unchanged.

## Tests

New tests cover large surrounding occlusion, small foreground hidden by mean NCC, excluded timer/phase invariance, matching without semantic/temporal authority, protected projected taps without denominator shrinkage, invalid source scope and nonfinite/degenerate models. Broader suite and lint evidence are stored in the verification artifact. Production source is unchanged from the preceding mypy PASS on all 104 files.

## Previous / Current / Delta

| Metric | Previous | Current | Delta |
| --- | ---: | ---: | ---: |
| Same-input unchanged diagnostic supported links | 22/29 | 22/29 | 0 |
| Critical images with point-only spatial quorum | Not measured for all sizes | 0/6 | Not comparable |
| Production scene/UI qualification | 0 | 0 | 0 |
| Canonical PASS / FAIL / NE | Historical 23/55/4 | Not rerun | Unmeasured |
| Canonical negative / discontinuity failures | Historical 0/0 | Not rerun | Unmeasured |

30 images were processed in 14.171270 seconds. This includes new passive footprint measurement and is not comparable as a speed benchmark to the prior mask-gated projected replay.

## Remaining blocker

Replacing manually reviewed distributed background domains with these track patches is rejected: every critical query lacks a second row. Enlarging their spatial cells or ignoring small occlusion would relax evidence, not fix the missing producer. The next source task is image-derived distributed background-domain correspondence/occlusion evidence, with original source support, complete footprint accounting, explicit ambiguity rejection, and independent negative/holdout qualification. Such appearance evidence must carry its limited scope instead of declaring a full semantic mask. This is not an OCR candidate or geometry-threshold task. R2 start and TEAM ACE remain separate; R1 remains first priority. No full E2E was run because the trusted source/qualification gate remains incomplete. Validation Pack/GT/assertions/full sampler and all 82 stored statuses remain unchanged. Windows execution is still unverified.

# Continuous reviewed projected-world diagnostic

## Problem

Projected appearance on one pair explained fixed-crop coverage loss, but a single pair cannot establish a temporal scene contract. An integrated chain must preserve original world identities, image/current review eligibility and source continuity at every link. The real target remains R1source continuity feeding `GT-R1-ROUND-START` and upstream lifecycle/package work. Main is `03bfcbf945fbf3d7b04c54d80b3c5ff103475db0`. No production behavior changes here.

## Evidence

The same exposed wall cohort has12native frames from2.502669to2.686003seconds,11links,256-tick increments in1/15360. Source video is bound to SHA256 `71d58558559d6f578433ce9f234bf176f76fd5a86657dbfe3eba1e7d36136b06`. Original images1–6were viewed at1920×1080; all12frames were reviewed as640×360domain overlays. First5images support the declared wall domains; image6places the hand inside the lower-middle domain. Later lower regions remain conservatively unapproved. Review/code/native PNG/pixel/source-video bindings are checked before and after replay.

[The initial declaration](../e2e_reports/match_001/scene_projected_chain_declaration.json) and [initial result](../e2e_reports/match_001/scene_projected_chain_development.json) are preserved. A conservative unknown bounding rectangle overlapped2pixels of an approved upper rectangle, so the new contradiction guard correctly rejected that annotation before any tracking. [The consistent-review declaration](../e2e_reports/match_001/scene_projected_chain_consistent_review_declaration.json) omits unapproved lower domains; all unlisted pixels remain unknown. The positive mask does not expand. [The corrected replay](../e2e_reports/match_001/scene_projected_chain_consistent_review_development.json) has exactly the same first5rows/four supported links; only the later rejection reason becomes the intended incomplete/occluded seed footprint. This is annotation-encoding repair on development data, not a new recognition candidate or blind holdout reuse.

## Competing hypotheses

- Projected appearance improves only an isolated pair: not supported by this episode; four adjacent links retain distributed source-world geometry and appearance.
- New current masks can grant arbitrary seed identities or repair model failure: prohibited. Original candidates, reciprocal flow, original consensus, bidirectional final-model errors, seed/adjacent patch NCC and region quorum all remain prerequisites.
- A hand entering the tracked world domain should be ignored if other matching scores look strong: prohibited here. Complete flow-source/current footprints must be reviewed world, so the chain stops before tracking that image and never rejoins.

## Independent image evidence

The opt-in diagnostic mode `projected_world` retains the exact existing camera estimator and original-seed membership policy. The original tracked source identities never gain new members. Dense appearance evaluates the full prior source crops projected into independently reviewed current world pixels. Current interpolation taps must all be approved; padding and unreviewed pixels are excluded without shrinking the full source-population denominator. Coverage>=0.90,NCC>=0.90,texture standard deviation>=1and the original point/region consensus remain unchanged. Supported source and projected-current crop centers must both span at least3cells,2rows and2columns.

Additionally,100%of every fixed crop used by local optical flow must be reviewed world on both prior and current images. Thus unreviewed/foreground data cannot influence the crop-local pyramids or source model. The appearance mask may extend beyond the flow crop only when those extra current pixels have independent world review. Source/image hashes bind bytes, not label truth; offline annotations still require independent qualification before any runtime use.

## Continuity decision

The replay supports four links ending at2.519336,2.536003,2.552669and2.569336. This covers66.667msfrom the initial reviewed source image. The first supported endpoint to the last spans50ms. These are descriptive native-source durations, not boundary triggers or hard-coded production windows.

At2.586003the current world review no longer covers the lower seed footprint because the hand enters it. The wrapper returns `current_seed_footprint_occluded_or_unreviewed`, clears tracks and terminates. All subsequent images return `reviewed_chain_terminated`; no reseeding or temporal bridging occurs. Missing evidence is unknown, not a cut label. No uninterrupted hidden game time, UI-transition semantics, R1boundary or final qualification is inferred.

## Contract change

Only diagnostic code changes. `ReviewedWorldChain` has a separately selected canonical-resolution projected mode requiring explicit seed/current world masks; ordinary modes retain their previous behavior. `ReviewedSceneDiagnostic(projected=True)` binds world reviews to video, canonical input pixels, source epoch and native PTS. It handles missing/stale/gapped/occluded/contradictory review and explicit cuts before tracking. Duplicate pixels remain vetoed. A newly added contradictory world/nonworld-overlap check prevents a larger positive region from hiding an unknown/contaminated subregion.

The output still has `runtime_proof_authorized=false`. This is not a trusted production scene/UI producer. Per-frame annotations cannot be copied into runtime as facts or selected by GT time. Qualified runtime bootstrap/current-world/occlusion evidence must be image-derived, and global scene evidence cannot imply HP/weapon/death/shot ownership. Geometry/NCC/OCR/ownership/discontinuity policies, Validation Pack, assertions and sampler are unchanged.

## Tests

53related tests pass in10.41seconds; Ruff passes on `src tests scripts/e2e scripts/diagnostics`; fresh mypy passes102production files. Integrated tests cover repeated successful translations with immutable seed identities, missing world masks, source gap/epoch/cut/occlusion/missing review, no reacquisition, contradictory annotations and complete-result independence from excluded source/current pixels. Existing model/photometry/review/cohort tests remain included.

A new historical-code comparison confirms exact default dictionaries on203real links at canonical/native resolutions and full-valid default membership. Exposed cut and duplicate controls still reject. They are previously exposed stress tests, not blind negative qualification. [Verification](../e2e_reports/match_001/scene_projected_chain_verification.json) records terminal bindings/static/test evidence. Windows execution is unverified; no platform-specific recognition rule is added.

## Previous / Current / Delta

| Same wall episode metric | Previous fixed-crop chain | Current projected diagnostic | Delta |
| --- | ---: | ---: | ---: |
| Native input frames | 12 | 12 | 0 |
| Adjacent links | 11 | 11 | 0 |
| Supported links | 0 | 4 | +4 |
| New feature identities/reseeds | 0 | 0 | 0 |
| Qualifications created | 0 | 0 | 0 |
| New runtime events | 0 | 0 | 0 |

Runtime is recorded in the corrected replay JSON. The earlier cohort timing included decoding3windows/36frames, while this replay uses12cached images; runtime deltas are not comparable. Supported links measure development source evidence, not canonical accuracy. Historical canonical23PASS/55FAIL/4NEand negative/discontinuity0/0remain the baseline; Current/Delta are unmeasured. All82stored assertion statuses remain unchanged. No new targeted, sampled or full canonical E2E was run.

## Remaining blocker

The method must next be evaluated on the actual R1transient episode with independently reviewed source/current world domains, then frozen before disjoint holdout and negative-control qualification. This wall cohort is exposed development and cannot be reused as blind qualification. Runtime image-derived seed/current semantic eligibility is still missing; manually reviewed per-frame masks do not supply that production feature. No event/package PASS follows merely from geometric/appearance support. R2start and result-banner qualification remain separate. Full E2E is not justified before trusted scene/UI source inputs and the three-boundary acceptance gate. The overall goal remains unfinished.

# Additive Report header contract

Decision: `CHANGE REPRESENTATION` for the Report exclusion witness only. Ability remains unchanged and its current decision remains `NEED MORE EVIDENCE`. This logical phase follows the frozen diagnostic audit, rather than relaxing any self-HUD gate.

## Evidence and scope

The old outer-margin panel proxy misses nine independently reviewed Report overlays in baseline live observations. A static title texture plus a spatially separate column-header texture agree in 22/22 training and 16/16 frozen Report holdout images. Non-Report holdout 0/16, world 0/8 and shopping 0/7 are accepted. Frozen Report controls are 29/30 accepted. A further 26 diverse/boundary native candidates and 12 portrait controls were independently inspected and all contain actual Report UI; the portrait controls are Report positives, not additional negatives.

The excluded left raster region has visible structure, not missing evidence. Low-NCC audited examples still show the same Report header against changing backgrounds. Thus disagreement with that single raster is not a Report-family absence label. It supplies no positive evidence in the new contract. Both selected supports are required; an observable contradiction to either rejects this witness. The witness only adds a Report exclusion and cannot convert an UNKNOWN observation to live.

This is a profile-specific static UI-texture representation, not OCR, an Agent icon matcher, or a separator-only invariant scaffold. It has one-recording/locale validation; no cross-recording accuracy claim is made. Private reference assets contain only selected static support pixels, with values, portraits, illustration, unrelated header content and neighboring HUD excluded.

## Runtime

`HudTemplateProfile.detect_signals -> report_header_evidence` receives only the current configured combat-report ROI and validated model assets. Two separate masks share one pose: horizontal offset ±2 pixels around the learned normalized origin, vertical localization inside that ROI, no scaling/rotation or world-wide search. Each group must have at least 32 informative pixels, spatial extent in both axes and adequate reference/current contrast. Signed masked NCC must be at least 0.90 for both groups. The winning pose is recomputed in float64. No timestamps, expected states, GT or temporal positive persistence enter this path.

The loader accepts only version 1, `independent_static_header_v1`, the `combat_report` role and the exact declared fields. Invalid assets, thresholds below 0.90, missing support, overlapping support bounds or geometry mismatch never activate a witness. All assets participate in the existing profile fingerprint. Existing profiles without this optional block retain their existing behavior.

On a match, the profile emits only `combat_report_visible=True` and its measured confidence. On failure it emits no Report boolean: it never clears an existing positive, proves absence, sets self-HUD loss or supplies death corroboration. The unchanged `live_identity` contract handles the existing Report blocker. Death continues to require an independent second source and the existing buy-phase safeguards.

## Verification and provenance

Actual loaded runtime agrees with the frozen diagnostic on accept/reject for all 4,730 native observations: 1,962 Report witnesses, zero decision mismatches. Accepted scores differ by at most 1.88e-6. Rejected numeric scores can differ (maximum 0.135442) because the explicit current-support contrast floor rejects low-contrast candidate poses; no rejected diagnostic frame becomes accepted. These rejected scores are not Report-absence probabilities.

Full pytest: 749 passed, 2 skipped. Nineteen new tests cover independent-group loss/inversion/different shape, flat and arbitrary texture, partial geometry, excluded-pixel variation, threshold/role/oracle-field rejection, asset fingerprints, legacy-positive preservation and lack of death corroboration. Ruff across source/tests/scripts, mypy across 84 source files and diff checks pass. A clean E2E is required after this implementation commit; its report is committed separately.

Video SHA256: `71d58558559d6f578433ce9f234bf176f76fd5a86657dbfe3eba1e7d36136b06`.

Private profile fingerprint: `2bdae7b5358f79ab8130e8c4a125ff3f5a6b83fe7ffe7b79c67bcf52d41c0383`.

Layout SHA256 remains `a3678bcd9df35d0932ae0e69495eb5b87a3ab40e9c988560d502a9507d59eef1`; sidecar SHA256 is `aa4a32b330e25cfdfba0ac092934c13bbe68ff121c7b574d660bee5a3f174141`.

Report template/mask/support-region asset SHA256 respectively:

- `b69bbe2dc8d987f3dc5063dc3bf0874c6583cc48f7410e694bca76e3ebe49a19`
- `4f9f6b13fb9a80169d7c2b9bb5aa2b838916161bfa0f1ca196aa6923bc989f1b`
- `d9127099d2dfbf4a3fa896c5cbbb0ae88e5bffd2f733d8cfc07e47057953463a`

HP, Ability, Weapon and Spectator references/parameters are inherited unchanged. Raw video, crops, model/reference assets and per-frame diagnostics remain private and are not committed. Future profile regeneration must explicitly retain or regenerate this optional Report block; an ordinary profile without it supplies only legacy Report evidence. Subsequent work must evaluate the clean E2E and temporal consequences before revisiting Spectator observability or Map marker ownership.


## Completed Clean E2E and independent live audit

The separately committed report (`d04eef714f172ec609d10d1bf59b9c6a53043410`) evaluates analyzer `5ed3b3d5f53e24c8cb9e902b30b6d5cfa958a3cf` with git_is_dirty=false: 22 passed / 56 failed / 4 not evaluated, negative assertions 20 passed / 0 failed. There are 4,009 adaptive HUD observations: live 138, Spectator 336, remote 33, buy 1 and unknown 3,501. This population differs from the previous 4,730 observations; these raw counts do not measure controlled recall.

All 138 current-run live observations were privately joined to their actual extracted images and scored with the frozen production Report model: accepts 0/138; all 138 non-accepts emit present=None, not Report absence. Scores range 0.000 to 0.213 (median 0.101). The highest-scoring representative of each of 21 time-contiguous runs was independently pixel-inspected; none shows Report UI. This is a bounded review, not proof about every frame. Both current and previous event traces contain zero player_death events, so this recording does not measure a death-event change. Per-frame paths, timestamps and contact sheets remain private.

# Shared image-only scene acquisition

## Problem / target

The native episode owner and tracking/domain calculations are common code, but reference assets and the image-only initializer still depended on diagnostic modules. That prevented constructing the complete observed-source path using only the production package. Preserve the actual source calculations while removing this dependency. Target remains R1 start/end, R2 start and their count/ordering predicates; no assertion is declared fixed by a code extraction.

HEAD: `e9ecaf8f2f0f0dfa1f9433d40a598ec8909e9ce3`.

## Change / source contract

`scene_reference_matching.py` contains the existing fixed-crop reference support and unique reciprocal patch search. `scene_references.py` contains the validated reference loader and reference-domain initializer. Old diagnostic modules re-export these functions/classes. Shared episode, reference loading, acquisition, tracking and domain calculations have no diagnostic-script imports.

The portable profile still has its explicitly unqualified scopes. Exact allowed fields, profile-relative assets confined to the profile directory, PNG/decoded-pixel hashes, review provenance, unique reference IDs and at least three unique non-UI crops are retained. Unknown or competing reference proposals are withheld; no best-score selection is introduced. These checks do not independently qualify semantic background or UI disappearance.

Reference matching consumes actual current canonical pixels only. Existing flow/patch/model/support/ambiguity/coverage predicates and all optional matcher behavior are unchanged. PTS/timer/score/phase/round IDs/Validation Pack cannot enter the image-matching API. The profile cannot provide previous observed source PTS/pixels. Matching result authorization fields remain false.

The complete common path can now be constructed without diagnostic imports:

```python
from valorant_ai_coach.hud.scene_episode import ObservedSceneEpisode
from valorant_ai_coach.hud.scene_references import WorldDomainBootstrap

episode = ObservedSceneEpisode(
    lambda: WorldDomainBootstrap(profile_path),
    native_step_ticks=native_frame_spacing,
)
measurement = episode.observe(native_bgr_frame, actual_pts_ticks, source_epoch=decoder_epoch)
```

This returns descriptive measurements. It does **not** produce `global_scene_continuity`, `global_ui_transition` or a round boundary. Qualified analyzer integration and current phase-absence evidence remain incomplete. Common HUD code fingerprints change normally; no old qualification is grandfathered.

Frozen native source reservations now require the two new common modules as well as domain/tracker/episode code before decode. Historical manifests are not rewritten. The probe's terminal bindings also cover the actual common calculations.

## Evidence / tests

Compare normalized source AST for `_validate`, reviewed patch extraction, unique match, reciprocal search, fixed-crop reference support and both loader/initializer classes. Bodies remain exact after removing typing casts/annotations and common helper import/name relocation. Seven calculation/validation definitions are checked.

Replay the existing exposed native R1 30-frame cohort through the common package directly, without diagnostic imports. Verify source PNG and pixel hashes, bound profiles/report and reference assets before/after; compare every frame result against the preceding episode replay. Results are saved in `e2e_reports/match_001/shared_scene_acquisition_regression.json`. Source exposure means this replay cannot be independent qualification.

All 30 complete frame outputs and original source bindings match exactly, with 22 descriptive links and the same permanent termination. The direct common-package replay also verifies reference-asset hashes at completion. Runtime is 49.293477 → 48.918016 seconds, delta −0.375462 seconds; this one-run fluctuation is not a claimed speed or recognition gain.

Related tests cover real image calculations, source profile/asset/path/provenance rejection, reference ambiguity, no GT fields, protected UI independence, reciprocal/model/photometric support, native source ownership and termination, frozen dependencies and qualified lifecycle consumers. Ruff and mypy cover the common production modules. Refer to the machine-readable result for final counts/timings.

197 related tests pass in 91.62 seconds. Ruff on `src tests scripts/e2e` and changed diagnostic tools passes; mypy passes all 109 source files.

## Previous / Current / Delta

| Metric | Previous | Current | Delta |
| --- | --- | --- | --- |
| Whole observed-source path constructible without diagnostic imports |No|Yes|Common package path available|
| Exposed R1 descriptive links |22|22|0|
| Qualified analyzer scene/UI entrance |Absent|Absent|0|
| Independently qualified runtime source profile |0|0|0|
| Canonical PASS / FAIL / NE |23 / 55 / 4|Not rerun|Unmeasured|

All 82 historical assertion records remain unchanged. Canonical targeted/sampled/full E2E is not run solely for this extraction. Historical negative/discontinuity 0/0 is not newly measured. No Git commit/push is performed. Windows runtime/packaging verification remains outstanding.

## Remaining blocker

Now address the actual qualified producer entrance: bind source-profile/assets to the HUD/profile/code qualification, enforce native source delivery without changing the full sampler, and require independent source/world/phase-absence qualification before releasing paired lifecycle proofs. The reference/profile validation here is not qualification. Do not convert descriptive links or contrast-unavailable phase nonmatches into trusted events. Current exposed R1 results and the preceding nine known-disjoint failed acquisitions remain development/rejected evidence, not new holdout.

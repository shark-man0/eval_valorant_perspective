# Shared observed native-source episode

## Problem / root cause / target

The original-identity tracker and fixed-camera appearance calculations are now common code, but actual native source ownership still lived in `scripts/diagnostics/observed_scene_chain.py`. Production cannot import that diagnostic tree. Complete the common episode layer without treating descriptive links as qualified continuity. Target assertions remain R1 start/end, R2 start and related event count/ordering; none is declared fixed by this extraction.

HEAD: `e9ecaf8f2f0f0dfa1f9433d40a598ec8909e9ce3`.

## Change / native source contract

`ObservedSceneEpisode` in `src/valorant_ai_coach/hud/scene_episode.py` owns the actual observed native PTS, epoch and pixel hashes. It accepts an image-only source initializer through a typed factory interface. The diagnostic compatibility class uses the existing diagnostic profile loader; that loader is not promoted to qualified production recognition. Reference assets remain assets and never supply previous source PTS or source pixels.

Cadence/options are validated before the factory loads reference assets. The factory is invoked once per episode. Pending acquisition stores only native metadata; it has no gray image, original identities or prior world history. The first image-supported acquisition starts at its own actual PTS. Established source episodes require exact configured native spacing, matching epoch and distinct actual source pixels. Explicit cut, malformed frame, missing support, gap or epoch change terminates the episode; later frames cannot rejoin it.

The canonical image conversion is also common code and used by diagnostic callers: actual 1920×1080 uint8 BGR → INTER_AREA 640×360 grayscale. No decoder, native frame cadence, full sampler or acceptance threshold changes. Tracking and joint appearance remain the shared calculations verified in the preceding extraction.

All seed, pending, successful and terminated results retain `runtime_proof_authorized=false`, `world_mask_authorized=false` and `qualification_created=false`. No analyzer proof, player-owned fact or lifecycle event is emitted. The common source episode is implemented; the qualified scene/UI analyzer entrance is still absent. Code qualification fingerprints change normally.

## Evidence / tests

Use the preceding full 30-native-frame R1 replay as the pre-extraction baseline, including all bindings and complete serialized outputs. Replay after extraction with the same profile/images/epoch and verify native PNG/pixel bindings and terminal input hashes. Compare complete serialized results, not just link counts. The machine-readable final result is `e2e_reports/match_001/shared_scene_episode_regression.json`.

All 30 serialized frame results and complete input bindings match exactly, including the 22 supported links, rejection reason and terminated tail. Normalized AST comparison also verifies the unchanged `_stop`, `_result` and `observe` method bodies, accounting only for typing, the common image-conversion name and an internal chain invariant assertion. Replay time is 48.654446 → 49.293477 seconds, delta +0.639031 seconds; this single-run fluctuation is not a speed or accuracy gain.

Related tests exercise initial source ownership, delayed acquisition without history, actual previous/current pixels and PTS, gap/cut/duplicate/epoch/malformed input termination, no rejoin, reference asset distinction, source identity/footprint/ambiguity gates and qualified lifecycle consumers. Additional common-API tests verify invalid spacing does not load assets and that one initializer supplies one episode without reloading after termination. Frozen native reservations must bind the new episode source file before decode.

160 related tests pass in 71.72 seconds. Ruff on `src tests scripts/e2e` and changed diagnostic tools passes; mypy passes all 107 source files. Windows execution remains unverified.

## Previous / Current / Delta

| Metric | Previous | Current | Delta |
| --- | --- | --- | --- |
| Shared native source episode owner |Absent|Implemented|+1 common owner|
| Exposed R1 descriptive links |22|22|0|
| Analyzer using qualified shared episode |Absent|Absent|0|
| Runtime scene/UI qualification |0|0|0|
| Canonical PASS / FAIL / NE |23 / 55 / 4|Not rerun|Unmeasured|

Historical 82 assertion records are not changed. No canonical targeted/sampled/full E2E follows merely from this common-code extraction. Historical negative/discontinuity counts 0/0 are not claimed freshly measured. No Git commit/push is performed.

## Remaining blocker / next implementation

The image-only source reference loader/acquisition remains diagnostic-specific. Move its validated asset/profile and actual image-correspondence path into the common package next, retaining reference ambiguity, source eligibility and code/asset bindings. Then provide independent source/world/phase-absence qualification and native frame delivery before connecting to `global_scene_continuity` / `global_ui_transition`. A diagnostic matcher nonmatch remains unknown; common source ownership cannot establish phase absence by itself. Windows execution and packaging are unverified.

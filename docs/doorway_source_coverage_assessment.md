# Doorway source coverage development assessment

## Problem

The preceding independent-context cohort has no scene seeds with the close-wall reference. Test whether providing an actually reviewed reference for its different background is sufficient, before attempting more holdout cohorts. This is one fixed development hypothesis, not a profile-bank search or a round detector change. Target remains the source qualification upstream of R1 start.

## Evidence / declared experiment

HEAD `e9ecaf8f2f0f0dfa1f9433d40a598ec8909e9ce3`. [Development measurements](../e2e_reports/match_001/doorway_source_coverage_development.json) bind the 12 now-exposed native cohort frames and a new local diagnostic-only profile. The original R1 profile is unchanged and the new profile is never installed in production.

Before measurement, three source-only static background proposals are fixed at canonical bounds `[160,55,220,117]`, `[425,78,565,117]`, `[470,125,550,170]`. Full native images at ticks 82985, 83497 and 85801 are inspected: the proposed source regions contain blue window/background, right ceiling structure, and right arch/crate, excluding the clock, phase area, minimap, spike indicator, FPS panel, name text, hands and players in the source image. This source review does not authorize current-frame world masks after motion. The native asset/pixel hashes and production code fingerprint are frozen.

The premeasurement minimum is three supported development initializations before considering any independent holdout. No score/timer/phase value, GT time or round ID enters these image calculations. Both `WorldDomainBootstrap` and `ObservedSceneEpisode` are the unchanged common production implementations; all outputs remain descriptive.

## Independent image/calculation evidence

| Frame | Accepted reference tracks | Model inliers | Initialization proposed | Observed episode |
| --- | ---: | ---: | --- | --- |
| 82985, reference itself | 45 | 45 | Yes | Seed only |
| 83241, next native frame | 15 | 15 | No | Stops: insufficient reviewed-world tracks |
| 83497 | 1 | 0 | No | Permanently terminated |
| Remaining nine | 0–1 | 0 | No | Permanently terminated |

At frame 83241, the fixed reference model has scale approximately 1.05167 and maps the upper-left region's upper-right corner to approximately `(225.44,52.39)`. This crosses the phase exclusion beginning at canonical x=224, with y below 120. Its fixed-projection domain score is unavailable and 170 local offsets have invalid support. The other two domains have NCC 0.945711 and 0.943025, but only two joint witnesses survive. Therefore distributed three-region support correctly withholds initialization. The observed tracking branch separately rejects with `insufficient_reviewed_world_tracks`; its detailed rejection is not replaced by the reference-domain explanation.

This isolates a concrete source/current footprint constraint, in addition to merely using the wrong wall reference. It does not prove all later failures share that cause: later reference tracking itself falls to 0–1 accepted correspondences.

## Competing hypotheses / continuity decision

- A matching reference alone repairs source qualification: rejected for this fixed proposal; only its self frame initializes.
- Two high-NCC domains can substitute for distributed support: rejected; keep the existing three-region and spatial-spread requirements.
- The phase area can be included because the phase might have disappeared: rejected; this would mix UI changes into supposedly independent camera evidence.
- A seed can rejoin after a failed next frame: rejected; this episode terminates permanently.

No content-cut classification or continuity accuracy follows from this development failure. The 12 images are exposed development, and this profile must not be qualified using those same frames.

## Contract change

None. Minimum support, NCC 0.90, complete current-pixel eligibility, source correspondence, ambiguity handling and no-rejoin policy are unchanged. No production asset, sampler, Validation Pack, assertion or player-owned fact is changed. The proposed profile fails its predeclared development gate and is retained only as a rejected local diagnostic artifact.

## Tests / verification

The actual common profile loader validates the relative asset, encoded/pixel hashes and reviewed native regions before measurement. Terminal profile, native asset, input report and production fingerprint checks pass. The preceding current-worktree source/cohort unit tests (15 passed), Ruff and 112-file mypy results still apply: no production/test code changes occur in this assessment. No additional canonical E2E is warranted by a rejected development profile.

## Previous / Current / Delta

| Same 12 exposed frames | Old close-wall input | New fixed doorway proposal | Delta |
| --- | ---: | ---: | ---: |
| Development initialization proposals | 0 | 1 (self only) | +1 |
| Observed scene links | 0 | 0 | 0 |
| Independent qualification added | 0 | 0 | 0 |
| Canonical PASS / FAIL / NE | 23 / 55 / 4 historical | Unmeasured | Unmeasured |

Development runtime: 4.189011 seconds for saved-image reference and episode checks. It is a different workload from the preceding 21.808556-second native decoder cohort, so no speed improvement is claimed. Canonical event/package/negative/discontinuity results remain unmeasured.

## Remaining blocker / next task

Source acquisition requires sufficiently textured, distributed source regions whose projected current footprints remain outside excluded UI and dynamic content throughout the intended development motion. More reference images alone do not provide that. Stop this rejected proposal without tightening its crops or adding favorable references to obtain counts. Next establish a source-profile training eligibility gate that exposes per-region correspondence, projected exclusion and minimum multi-frame support before any holdout reservation or runtime installation. Independently qualified phase disappearance and native lifecycle merge remain unfinished. Windows execution is unverified.

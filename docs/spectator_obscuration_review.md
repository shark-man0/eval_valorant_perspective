# Spectator obscuration and Report blocker review

## Reproducibility

Starting HEAD: `4e768580ef60e3b7908760b39ffb213a1fa3df3e`. Native image sequence is the 4,730 observations from the clean E2E analyzer `2650d09b90df50d6a004dbe5d849fc60432af33b` (`git_is_dirty=false`). Diagnostic worktree changes are offline code/tests/docs only; production source and profiles remain unchanged. This is not a new E2E report.

Video SHA256: `71d58558559d6f578433ce9f234bf176f76fd5a86657dbfe3eba1e7d36136b06`. Profile fingerprint: `372bf43ab9c443e3d54bd46b3b5d51626aa1ebf0f8d8a68edeb76e5aff826453`. Layout SHA256: `a3678bcd9df35d0932ae0e69495eb5b87a3ab40e9c988560d502a9507d59eef1`. Private image paths/native extraction times are supplied only to the diagnostic CLI; shared output contains aggregates and hashes. No GT, expected state, OCR or agent knowledge enters detector features.

## Why move beyond Ability

Ability follow-up established extractor failure mechanisms, but its best frozen candidate still loses 10/183 positives and lacks certified intrinsic negative separation/dynamic-state invariance. Its findings are in `ability_identity_followup.md`. The largest current live blocker is unchecked Spectator exclusion (4,387/4,730), compared with 182 structure insufficiencies after checked absence. Continuing the same Ability experiments indefinitely has lower information value than auditing why the icon ROI is not measured.

## Actual obscuration path

`OpenCvHudFeatureReader.observe/observe_sequence` emits center-crosshair detail/luminance hints and a buy-grid texture hint. `HudTemplateProfile.detect_signals` passes them to the dedicated fixed-slot icon detector; an independent short-diagonal-X candidate in the configured menu-close ROI also vetoes measurement. `scene_detail_collapse` measures center-crosshair edge density, not the separate portrait ROI. Current native inputs emit only this detail hint, abrupt luminance spike, and buy-grid presence among the supported context keys. Other supported map/transition/flash keys remain policy vetoes when supplied.

The checked-in offline `scripts/diagnose_spectator_obscuration.py` independently reproduces the entire reason distribution using only native fields actually consumed by the icon obscuration path. It stores small icon crops privately in memory, not shared assets, and does not simulate live identity. A separate source-reader/profile/identity/classifier replay audits possible behavior changes with all remaining signals preserved.

| Icon reason | Current | Diagnostic scene-only refinement |
|---|---:|---:|
| Checked absence |343|449|
| Obscured/unmeasured |2786|1918|
| Unobservable |1050|1689|
| Ambiguous |32|70|
| Presence |519|604|

All existing 343 checked absences and 519 presences are unchanged. Of 1,033 scene-detail hint frames, 868 become measurable and 165 remain vetoed by another hint or X. The 868 split into 106 absence, 85 presence, 639 unobservable and 38 ambiguous. All 32 scene/buy-grid overlaps and 135 scene/X overlaps remain vetoed. Local geometry, clipping, mean/contrast, sharpness, edge acutance and presence/absence structure gates are unchanged; no ambiguity or low observability is converted to absence.

## Image audit and full gate replay

All 21 new absence cases with all three current role scores >=0.90 were reviewed in full-frame and icon crops. The crops show no clear portrait; 20 show first-person hands/weapon/Ability imagery and one a world/HUD view without clear hands/weapon. Three also show a right-side report overlay; none shows a full shopping grid. These are clustered samples, not 21 independent scenes.

A diverse sample of eight new presences and all five new presences with every role passing show clear portrait pixels in the configured slot and retain the presence blocker. They are not shopping-grid images. Broader ablations that remove buy/X hints can mistake shopping-grid detail for portrait structure, so those ablations are not proposed for production. Eight sampled buy-grid hints contain five actual full grids and three gameplay/report views. Eight sampled menu-X candidates contain one clear X and seven texture/interface examples. These small reviewed samples diagnose possible sources; they are not population precision estimates.

The narrow full-signal replay matches the saved unknown baseline in all 21 cases. It would classify 19 as live and reject two as competing-view evidence. Eleven would-be live cases retain trusted-world eligibility and eight remain world-untrustworthy through existing smoke/flash safeguards. Critically, one of the 19 has a visually present report that the current report reader misses. That is an unresolved unsafe acceptance opportunity even though world trust remains false. It prevents adoption of the narrow Spectator change.

## Report blocker actual path

The profile has exactly HP, Ability and Weapon signal references and **no combat-report template**. `combat_report_visible` comes directly from `OpenCvHudFeatureReader.observe -> _panel_score(combat_report ROI) >=0.78`; no profile override occurs. ROI is `[1480,270,1918,770]`, crop 438x500. This source path reproduces both saved report flag and saved value on all 4,730 frames: 849 true, 3,881 false. No currently live frame has the flag.

The score is `0.55 * boundary + 0.45 * content`. Boundary is the larger mean-intensity difference between adjacent left/right bands, each width `ROI width//16`, normalized by 42. Content uses edge density and grayscale std. The three audited report controls have current scores min/median/max 0.5099/0.8285/0.9674. The missed case has content=1 with edge density about .100 and std45.87, but boundary .109; it is visibly structured rather than unobservable. A reviewed shopping-grid example reaches .7974 despite no visible report, showing that this proxy also lacks semantic separation.

## Boundary counterfactuals

Changing only the outer-left 27-pixel band (6.16% of ROI), while leaving every other report-crop pixel exactly unchanged, can raise the missed report score from .5099 to1.0. Substituting a neighboring detected report's band has the same effect; another neighbor's band produces .5472. The classifier therefore depends on margin luminance rather than only on stable report structure. Constant band extremes are interventions, not real gameplay-state claims.

Two cheap alternative proxies are inadmissible without further evidence. Removing the boundary term flags 14/146 existing live controls; using the maximum of four row-band boundaries flags 12/146 and still leaves the known missed report below threshold (.7398). These are new tags on state-derived controls, not proven false positives until pixel review. No threshold change or production use is made.

## Decision and autonomous continuation

**KEEP CURRENT** Spectator production policy for now. The local-ROI refinement has a concrete Report blocker dependency; adopting it alone could enable a visible-overlay frame. Ability/Weapon/HP/Spectator/Visual/Map behavior, all identity gates and thresholds are unchanged. There is no new Clean E2E because no production change is adopted.

Continue with independent Report geometric support diagnostics, training-only masks and holdout/control comparisons, plus pixel review of newly tagged live controls. Any eventual report guard must preserve current-frame evidence, avoid text/value/agent/time dependencies and reject insufficient or contradictory evidence. Only after the known overlay safety miss is safely handled can the narrow Spectator refinement be reconsidered. This phase's rejected candidate is an input to the next experiment, not a reason to stop.

## Verification

Full suite before this one additional diagnostic test: 723 passed /2 skipped under `PYTHONUTF8=1` and the local validation-pack environment. New diagnostic plus existing Spectator tests:30 passed. Independent CLI matches all current reason counts on the real 4,730-frame sequence; output exposes no paths/times/images. Ruff `src tests scripts`, mypy `src` (83 files), and diff check pass. Final full suite: **724 passed /2 skipped**,273.40 seconds, same UTF-8/validation-pack environment.

## Expanded visual controls and Ability replay

The current-live controls are not ground truth. Pixel review of the 16-frame union tagged by the two cheap variants found nine visible report panels and seven non-report wall/door/stair textures. Content-only tags nine reports plus five textures; four-band boundary tags five reports plus seven textures. At least nine current live classifications therefore coexist with a report-style overlay despite the current contract's report blocker. Preserving an existing live count is not sufficient evidence of safety.

The private image-reviewed manifest has 57 unique native-frame controls, deduplicated by native-time/image SHA, with correlated near-frames disclosed. Forty-nine have a report overlay (30), full shopping grid (7), or portrait (12); eight are visually confirmed non-report texture controls. Unknown plain-HUD opportunities are reserved, rather than assigned negative solely from runtime state.

On the same new 49 contextual identity negatives, frozen Ability raw accepts are current fixed template30, original scaffold26, revised R33. Native-feature/profile/full-gate replay matches saved live status in all49. Current live accepts9 and R accepts8; R enables no new live cases and rejects one of the existing report-overlay accepts. This accidental Ability rejection does not establish an overlay detector. The remaining eight are still evidence that a separate report guard is required. The older27 control replay's 0 live result was scope-limited and must not be extrapolated to the expanded cohort.

A sparse report-line candidate learned from only three weak even32 seeds with one weak odd holdout also fails: it matches zero of three audited report controls. Its one match among current-live controls was initially presumed false; pixel review establishes a visible report there, so it is a correct negative match, not a proved texture false positive. Candidate rejection rests on inadequate training representation, report misses and parallel-only support, not on preserving an unsafe baseline count. Further experiments use denser image-only seeds and held-out verified controls without tuning to their labels.

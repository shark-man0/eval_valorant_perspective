# PR #42 integration readiness — convergence audit

Decision: preserve the existing results, keep #42 draft, and integrate only independent bounded units. Formal End is **not qualified**. Source-only preflight is extracted as [PR #55](https://github.com/shark-man0/eval_valorant_perspective/pull/55), three files on current main, with no production reader change. No main merge or Full E2E is performed.

Audit implementation HEAD `5cc8b01b77f656312e5f4885011aafdcd206aba0`, main `7e480c2f2f7f49aea73e1541d065d78881d2f11c`, fetched on2026-10-18 JST. The working tree is clean before audit work. The comparison contains27 commits/67 changed files,14470 insertions/10 deletions; most are reports/metadata. Later convergence-report commits must not be described as having this HEAD's CI automatically.

## Integration units

| Unit | Actual change and user-visible behavior | Tests/private dependency | Adoption |
| --- | --- | --- | --- |
| A1 source/PTS preflight | New readonly CLI; wrong source/order/epoch/hash rejects, real PTS origin/cadence preserved; loader admission never becomes qualification | 15 new preflight cases; related174 PASS on main-based extraction; private source/contract needed only for optional actual use | PR #55; independent of #42/#51/#48/#54 |
| A2 native geometry-only binding | Five production modules add an explicit optional reference, immutable source/code/profile/bundle/first-frame binding and terminal replay checks; default cold path unchanged | `test_qualified_geometry_initialization.py` plus native lifecycle/merge tests; real invocation needs retained private reference and current Start admission | Extract as a cohesive later unit; reference code/tests have no dependency on score/caption extensions. Do not split the proof class from replay/transport guards |
| A3 conservative End regression | Existing source-outlier/unknown-gap regression only; production End tracker unchanged | `test_unedited_ui_end.py`; synthetic, no private source | May be separated as test-only protection; does not repair End |
| A4 portable PTS inventory | Metadata-only exporter, explicit UTF-8 and portable POSIX artifact IDs; user-authorized snapshot | 10 export tests/13 text-I/O tests; private manifests needed only to regenerate | Keep separate tooling/data responsibility; no independent exposure certification |
| B1 caption families | `semantic_text.py`/`templates.py`: explicitly configured complete-caption family, no cross-caption group mixing, guarded support and fingerprinting | `test_semantic_text_family.py`; family-specific source/reference/training/held/negative proof still required | Experimental opt-in; not a default or formal End deployment |
| B2 score modes | Border/separated tiny-component cleanup under explicit foreground modes; all0–9, NCC0.90/margin0.04 retained | Border/separated tests; source-reviewed development recoveries and failed independent End trial are separate | Keep opt-in; no End qualification inferred from availability gain |
| B3 source-backed usage | R1/R2 native reference and partial Package/Trace measurements | Current private Start bundle and actual source images | Bound to measured conditions, not whole-match/whole-sampler qualification |
| C research | Rejected temporal restart, timer transfer/template-bank variants, spatial/color score variants, clock-type reader study, failed End episodes | Preserved reports and exact archived hashes | No production default; no repeating failed hypotheses or treating historical fingerprints as current admission |

Stale qualification rejection is an existing main mechanism, not a new general loader feature introduced by this PR. Current remeasurement/rejection evidence supports it; do not claim a fresh qualification merely by copying hashes.

## Responsibility and dependency boundaries

- **#51** HEAD5347f9a0, base branch #42 atabeb011: four files, shared `analyzers.py` and new sampled `FrameSample`/processor binding. #42 owns the existing native-only reference contract; #51 owns sampled prefix, sampled image attestation and application hookup. #51 is behind #42's current source fingerprints and has failing CI in the audited snapshot. Do not merge/cherry-pick it blindly or modify its branch. After a cohesive native contract extraction/rebase, recheck source fingerprints, tests and actual sampled transport. No new sampled implementation is added to #42.
- **#48** HEAD99d9d4dc, main-based, nine evaluator/test/report files, green audited CI. Its versioned±0.1s evaluation policy is separate from recognition; no file overlap with #42's production changes. Do not import its policy to turn the fixed R1 End FAIL into recognition success.
- **#54** HEADcf4f712c, main-based, three files in native decoder endpoint precision/tests/docs, green audited CI. #42 does not change `video/native.py` or reproduce this fix. Decoder/fingerprint changes require actual new qualification/revalidation; no fingerprint-only transfer. The preflight CLI is an audit consumer of the decoder, not a competing endpoint implementation.

Recommended order: review/CI PR #55 independently; review #54 independently as its own exact-PTS responsibility; prepare a cohesive native geometry-contract unit with its transport tests and fresh code-bound proof; rebase/revalidate #51 on the chosen native contract; keep #48 evaluator policy opt-in and separate. Caption/score adoption and formal End remain conditional research. There are no edits to another owner's branch and no merges into main.

## Start/End scope retained

| Target | Actual measured source time / confirmation / confidence | Status |
| --- | --- | --- |
| R1 Start |4.102669270833333 /4.202669270833334 /0.9117099378029602|Bounded current-code native358 frames, ordinary39-frame Package/Trace and selected canonical R1-start PASS. Start-only admission; no complete round or owned facts|
| R2 Start |111.4193359375 /111.48600260416667 /0.931477963924408|Native48 with geometry-only prefix and ordinary51 frames with three genuine origin observations preserve Package/Trace. Cold ordinary48 fails; full default sampler/continuity/match-wide Round2 membership absent|
| R1 End |74.48600260416667 /75.3693359375 /0.9180924279198346|Diagnostic; fixed GT upper74.483 missed by3.002604ms. No rounding/backdating, policy widening or End qualification|
| R2 End |No new full-coverage result|Only the recorded targeted negatives support bounded no-pattern statements; no claim for unobserved suffix|

The local R2 fragment stays `sample_round_1`; renaming it to `sample_round_2` would fabricate membership. Duration sentinel is missing-coverage/package upper bound, not a detected End. Geometry-only reference carries no phase, score, timer, identity, lifecycle state or epoch continuity. Origin3 ordinary observations are a different condition from the native reference-only path. Current original-source bundle08a261f9… admits timer/purchase_phase/ui_transition only under code414f9d9d…; no score/result/End release or default bundle installation.

## Matched spectator comparison

Main and PR #42 are run in separate fresh Python processes, same local interpreter/libraries, same two test modules/order, no private assets. Main is an exact `git archive` of7e480c2f; no source branch edits. Both yield46 PASS/4 FAIL. Test files are byte-identical and failure messages match:

| Test | Failure on both |
| --- | --- |
| `test_global_scene_detail_cannot_override_current_local_icon_evidence[crop1-True]` | `assert None is True` |
| `test_abstract_icon_is_detected_across_small_rendering_shifts` | `assert False is True` |
| `test_profile_uses_only_configured_icon_roi_and_obscuring_context` | `assert None is True` |
| `test_short_menu_close_x_vetoes_icon_without_menu_grid_candidate` | `assert None is True` |

Environment: Python3.12.15, macOS27.0.1 arm64, OpenCV4.14.0, NumPy2.5.4. Fixtures are generated synthetic crops, not private images. This establishes preexisting failures in this matched isolated local scope; it does not prove the cause is the OS or exclude every possible full-suite ordering interaction. Do not dismiss them as harmless or broadly alter spectator recognition here. Linux/Windows exact-HEAD CI is an independent gate.

## CI and remaining acceptance

At5cc8b01, both Linux checks and text-I/O gate pass. Windows PR run39120228954 succeeds, explicitly including UTF-8-disabled tests, PyInstaller and packaged smoke. The additional push-triggered Windows run39120230846 also completed successfully, including PyInstaller and packaged smoke. All five audited checks at5cc8b01 are successful. The previous e9e9e15 failures came from two exporter `.encode()` call sites;5cc8b01 fixes explicit UTF-8 and Windows artifact-ID separators. Exported seven JSON/JSONL files remain byte-identical;23 focused tests/Ruff/audit pass. No production recognizer change is included in that fix.

PR #55 has its own HEAD4f43d74 and CI must be checked separately. No prior #42 green result certifies it automatically. Full local coverage3866 PASS/4 FAIL/9 SKIP is historical implementation evidence; the matched comparison above is the fresh spectator audit, not a new full regression. Canonical baseline stays23 PASS/55 FAIL/4 NE. Full E2E belongs #20 and is not run.

Remaining convergence work: one isolated clock-type temporal study with synthetic/saved-row tests, exact E-1/E-2/E-3 failure audit, final own-HEAD CI checks and data requirements. No further foreground/template experiments are authorized in this goal. If independent temporal positives/negatives are unavailable, stop the experiment as unqualified and retain the safe integration candidate.

## Complete changed-file inventory at audited HEAD

A = contract/tool/test candidate; B = explicit opt-in conditional recognizer; C = unadopted/historical research; evidence = version-bound report; A-record = shared metadata only. Categorization does not make every A file immediately mergeable in isolation.

| File | Category |
| --- | --- |
| `docs/clock_type_chromatic_development.md` | C |
| `docs/clock_type_development_feasibility.md` | C |
| `docs/current_code_independent_End_display.md` | C |
| `docs/current_main_round_application_followup.md` | evidence |
| `docs/current_main_round_boundary_requalification.md` | evidence |
| `docs/end_score_restart_rejected.md` | C |
| `docs/guarded_caption_family_candidate.md` | evidence |
| `docs/guarded_caption_family_followup.md` | evidence |
| `docs/independent_source_001927_evaluation.md` | C |
| `docs/qualified_geometry_initialization.md` | evidence |
| `docs/qualified_r2_application_context.md` | evidence |
| `docs/round_boundary_requalification_preflight.md` | evidence |
| `docs/score_border_source_guards.md` | evidence |
| `docs/score_border_speck_candidate.md` | evidence |
| `docs/score_minchannel_development_study.md` | C |
| `docs/score_separated_speck_development_study.md` | C |
| `docs/score_separated_speck_mode.md` | evidence |
| `docs/score_spatial_background_development_study.md` | C |
| `docs/timer_consistent_bank_development_study.md` | C |
| `docs/timer_foreground_development_study.md` | C |
| `docs/unused_source_round_end_assessment.md` | C |
| `e2e_reports/match_001/clock_type_chromatic_development.json` | C |
| `e2e_reports/match_001/clock_type_development_feasibility.json` | C |
| `e2e_reports/match_001/current_code_independent_End_display.json` | C |
| `e2e_reports/match_001/current_main_round_application_followup.json` | evidence |
| `e2e_reports/match_001/current_main_round_boundary_requalification.json` | evidence |
| `e2e_reports/match_001/end_score_restart_rejected.json` | C |
| `e2e_reports/match_001/exposure_inventory_20261016/README.md` | A-record |
| `e2e_reports/match_001/exposure_inventory_20261016/artifact_index.json` | A-record |
| `e2e_reports/match_001/exposure_inventory_20261016/discovery_requests.json` | A-record |
| `e2e_reports/match_001/exposure_inventory_20261016/frames.jsonl` | A-record |
| `e2e_reports/match_001/exposure_inventory_20261016/historical_split_plans.json` | A-record |
| `e2e_reports/match_001/exposure_inventory_20261016/method_snapshots.json` | A-record |
| `e2e_reports/match_001/exposure_inventory_20261016/sources.json` | A-record |
| `e2e_reports/match_001/exposure_inventory_20261016/summary.json` | A-record |
| `e2e_reports/match_001/guarded_caption_family_candidate.json` | evidence |
| `e2e_reports/match_001/guarded_caption_family_followup.json` | evidence |
| `e2e_reports/match_001/independent_source_001927_evaluation.json` | C |
| `e2e_reports/match_001/qualified_geometry_initialization.json` | evidence |
| `e2e_reports/match_001/qualified_r2_application_context.json` | evidence |
| `e2e_reports/match_001/round_boundary_requalification_preflight.json` | evidence |
| `e2e_reports/match_001/score_border_source_guards.json` | evidence |
| `e2e_reports/match_001/score_border_speck_candidate.json` | evidence |
| `e2e_reports/match_001/score_minchannel_development_study.json` | C |
| `e2e_reports/match_001/score_separated_speck_development_study.json` | C |
| `e2e_reports/match_001/score_separated_speck_mode.json` | evidence |
| `e2e_reports/match_001/score_spatial_background_development_study.json` | C |
| `e2e_reports/match_001/timer_consistent_bank_development_study.json` | C |
| `e2e_reports/match_001/timer_foreground_development_study.json` | C |
| `e2e_reports/match_001/unused_source_round_end_assessment.json` | C |
| `scripts/diagnostics/export_pts_exposure_inventory.py` | A |
| `scripts/e2e/preflight_round_source.py` | A |
| `src/valorant_ai_coach/hud/analyzers.py` | A |
| `src/valorant_ai_coach/hud/native_assured_start.py` | A |
| `src/valorant_ai_coach/hud/native_event_merge.py` | A |
| `src/valorant_ai_coach/hud/native_geometry_initialization.py` | A |
| `src/valorant_ai_coach/hud/native_lifecycle.py` | A |
| `src/valorant_ai_coach/hud/score_glyphs.py` | B |
| `src/valorant_ai_coach/hud/semantic_text.py` | B |
| `src/valorant_ai_coach/hud/templates.py` | B |
| `tests/unit/test_export_pts_exposure_inventory.py` | A |
| `tests/unit/test_qualified_geometry_initialization.py` | A |
| `tests/unit/test_round_source_preflight.py` | A |
| `tests/unit/test_score_border_specks.py` | B |
| `tests/unit/test_score_separated_specks.py` | B |
| `tests/unit/test_semantic_text_family.py` | B |
| `tests/unit/test_unedited_ui_end.py` | A |

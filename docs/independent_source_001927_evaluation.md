# Independent source event evaluation after separated-speck implementation

The frozen separated-speck score mode improves score availability, but neither paired method detects any of the three enrolled End display episodes. Formal End and complete lifecycle qualification remain unproven. Keep Issue #16 open and PR #42 draft; the canonical 23 PASS / 55 FAIL / 4 NOT_EVALUATED baseline is unchanged. No full E2E is rerun.

## Provenance and prospective controls

Source SHA256 `f5a3d2e78f183ffbcdb066ddd21574c2d38846d73b067204145ebaee7cd59c69`, duration 2167.338 seconds, 1920×1080, 60 fps, time base 1/15360. The user supplied it directly in response to a request for an unused, unedited recording. No original labels were supplied. It is distinct from prohibited match_002; no match_002 labels are read.

Before viewing source images, freeze development geometry-only 0–180 seconds, unused buffer 180–540, independent event candidates 540–1440, buffer 1440–1620, scene-control candidates 1620–2100 and unused tail. Scene controls are not presumed negatives. Source-only discovery enrolls all three distinct score-increment brackets; retain the two Spike/decimal episodes as well as the countdown episode. These targeted events do not estimate recording-wide recall or prevalence.

Implementation commit `eaafd6b3545d33039265ccb4f36d70cb52489637`, recognizer fingerprint `414f9d9d3f1841cfe50fdf9732bb78e1bfa35aa4382eb7c0d90d194ed81155fa`. Candidate profile `b217885c5d656221495e7f801c583245123b9ed0fb66546a464a0fc7f7f7b4b0` fixes geometry anchors from actual development source frame 30 seconds, without changing value templates, layouts, thresholds or result/phase configuration. Baseline `d7fabd3ec4f9a9a77021eed733f1d7379004e2e928d1e0f7933bb689e4eda4d0` differs only in the two score foreground modes. Baseline comparison is frozen after discovery extraction begins, before source-content viewing or prediction. Candidate method is frozen before discovery. No post-case tuning occurs.

The inherited profile fails all six development geometry probes. The adapted reference matches four anchors on its own training image, while other sampled development frames fail fresh calibration. Each evaluation uses that actual earlier reference for geometry only. All evaluated frames use retained geometry; fresh in-window geometry succeeds on zero frames. This is conditional geometry-assisted evaluation, not independent calibration success, active Start, player identity or source continuity proof. Source epochs and native 256-tick cadence remain distinct and intact.

Assistant support labels are frozen before prediction. The user independently confirms the first newly visible score frame and LOST caption for all three events before either prediction. The human review is limited to those source displays, not all support labels, an internal game End timestamp or recognizer approval. Historical pre-review labels remain immutable; a separate review receipt binds source pixel/label hashes. Source pixels, input contract, code, profiles and label bindings pass integrity checks before prediction and at all six terminal checks. Raw rows are saved before label scoring.

## Paired results

1,113 physical native frames, six producer calls, 1,931,834,233 PNG bytes. No formal events, owned facts or source breaks are emitted.

| Event | Frames | Complete score pairs, baseline → candidate | First new-score acceptance after human display point, both | Diagnostic End, both |
| --- | ---: | ---: | ---: | ---: |
| E1 | 331 | 183 → 191 | 0 ms | 0 |
| E2 | 391 | 391 → 391 | 0 ms | 0 |
| E3 | 391 | 379 → 380 | 50 ms | 0 |

Across 2,226 score-field calls per method, all 2,065 previously accepted values and confidences are identical; nine previously unknown fields become accepted, and 152 remain unknown. Complete pairs increase from 953 to 962. All timer, phase and result predictions are identical. After-prediction assistant source review covers all nine changed fields and agrees with their readings; that review does not enlarge prospective accuracy counts and is not independent human review.

The frozen 18 support frames give 32 correct / 4 unknown / 0 wrong score fields in both methods. Result presence gives 17 correct / 1 unknown / 0 wrong (nine absence controls and eight positive accepts). Countdown gives 5 correct / 1 unknown / 0 wrong. Twelve noncountdown calls reject correctly, spanning two physical episodes rather than twelve independent events. There is no independent pure End-negative cohort and no formal false-positive-rate claim.

Producer elapsed baseline/candidate seconds: E1 95.893/93.256, E2 129.645/122.607, E3 113.861/109.443. These sequential local observations are not controlled performance benchmarks.

## Why End remains missing

E1 and E2 transition from Spike to retained decimal displays, with no accepted countdown literal in either native window. They are real source-display episodes retained in the evaluation, even though the current clock-gated path cannot seed a countdown End candidate. LOST recognition alone does not establish formal End.

For E3, saved observations show an accepted old countdown and score, then unknown timer/score gaps around the visible transition. The first accepted new countdown arrives while the enemy score is still unknown; the first accepted new enemy score arrives 50 ms after the human display point. The prior stable-score context is already broken, so no pending clock candidate is created. First accepted LOST arrives later. This is an optical gap/order failure, not a successful boundary with merely late confirmation. Diagnosis replays saved rows only; no reader rerun or label change.

No horizon extension, unknown bridging, manual values, inferred earlier timestamps, GT changes or state/epoch splice is introduced. These three cases are exposed now and can serve as regression cases, not fresh independent tests for a future changed method. The event already partially visible at the final discovery point is also exposed. Any later evaluation must freeze a changed method before opening a distinct unviewed physical event.

## Validation and remaining work

This checkpoint adds reports only. The implementation checkpoint retains 33 new / 163 related passing tests, full local 3866 PASS / 4 existing spectator FAIL / 9 SKIP, and passing dataset, Ruff, mypy and UTF-8 audits. This report does not claim a new full test run or current Linux/Windows success. Exact private evidence hashes and six run hashes are recorded in the aggregate; raw images, labels, profiles, qualification bundles and exposure ledgers remain private.

Formal End, independent temporal and negative evidence, complete Start→End continuity, full ordinary R2 sampling and round membership remain outstanding. Network approval is unavailable following an automatic approval review usage-limit rejection of the prior CI query. This checkpoint has not been pushed and no new remote CI result is claimed.

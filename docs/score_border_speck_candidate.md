# Opt-in score border-speck reader: bounded qualification checkpoint

The strict score reader can reject a complete digit because a small, separate bright component touches the edge of its configured ROI. Add `white200_rowcontrast_border_specks_v1` as an explicit profile option. It removes only small, vertically separated border components beside one or two complete, centered and aligned core glyphs. Clipped core glyphs, clipped neighbours, off-center surviving digits, connected fragments and in-band noise remain subject to the existing structural rejection.

This checkpoint integrates main `7e480c2f2f7f49aea73e1541d065d78881d2f11c` through merge `56c42b7`. It remains **B: bounded partial qualification**. Formal Round End and the complete Round lifecycle are unqualified; keep Issue #16 open and PR #42 Draft. The aggregate and private-artifact hashes are in `e2e_reports/match_001/score_border_speck_candidate.json`.

## Reader contract and development

The mode uses the existing white200/rowcontrast mask and Gaussian3x3 comparison. Cleanup operates before classification, without expected digit, score, clock, round ID, retry or temporal history. Core height must be at least half the maximum component height; require one or two cores, none touching an edge. Their heights/top alignment must satisfy the existing 0.8/0.15 consistency rules, and their union center must be within glyph-height/10 of the ROI center. A removable component must touch an edge, be vertically separated from the core by glyph-height/8, have width and height at most glyph-height/3 and area at most one sixth of the smallest core. Remaining components still pass the original score grammar, NCC >=0.90 and competitor margin >=0.04. All ten inherited digit classes remain competitors.

The existing default and previous foreground modes are unchanged. No profile or qualification is installed as a default. No digit asset, confidence threshold, End deadline, ownership, source continuity, GT or timestamp policy changes. The rejected score-restart prototype remains rejected; unknown score gaps do not attest an earlier proposal.

Source-bound diagnostics reproduced 3,428 historical field calls without mismatches. In the exposed WON failure, the complete `7` has NCC 0.955925 versus competitor `2` at 0.6550; a separate 2x8 border component of area9 caused rejection. This exposed case explains the failure but supplies no new independent qualification. Fixed cleanup rules were developed on the original 300–600s development pool. Of 2,886 development field calls, 2,777 accepted values and confidences are unchanged, 106 remain unknown, and three become readable. Assistant source-image review reads `2`, `4`, `4`, all correct; these are development evidence. No parameter sweep or post-held tuning is performed. The inherited timer-digit assets are not claimed as newly trained score-class assets.

An initial private synthetic expansion had seven failures from incorrect fixture expectations (including assuming every rendered font glyph was accepted by the clean baseline). Correcting those fixture assumptions did not change the algorithm. The final public tests compare against the unchanged clean baseline and preserve invalid/clipped structures; they do not claim every synthetic glyph is readable.

## Frozen identities and original-source regression

| Identity | SHA256 / fingerprint |
| --- | --- |
| match_001 source | `71d58558559d6f578433ce9f234bf176f76fd5a86657dbfe3eba1e7d36136b06` |
| additional unused/unedited source | `06919642d69f68895ac123b505bfd7d3643dd28d903585008fcdc2b7f1b7e3fd` |
| recognizer code | `ddc5e6c2d012d3b1219f567a532ea193219578e14c18f3954ce51c98bf473264` |
| original-source candidate profile | `fc3b8dfc4c4e9c72e6bbbaf7c5a90762ad879ea695dff8784997123e1f56f51c` |
| additional-source candidate profile | `6411f7d326f71076efa54bb431a8efc501d01678fccd19a1f3a07a62c2146c80` |
| freshly reviewed Start-only bundle | `85caed7d2b4044b910bfa98f573907a0eaa087c488d840090ee40ab288d75ca7` |

Both legacy and opt-in profiles were measured on the current code; historical results on other code fingerprints remain separate. Static counts are unchanged: phase3 training /8 held correct,12 negative reject; timer25 correct/7 unknown/0 wrong; score36 correct/18 unknown/0 wrong fields; result3 correct/8 unknown/0 wrong and3 negative reject. Timer type controls8 and score negative fields54 have zero false accepts. Seventy-six original timer parents and ten glyph assets remain verified.

Fresh native analysis covers eight fixed windows, 369 frames per profile. In the 108-frame original End window (216 labelled score fields), legacy115 correct/101 unknown/0 wrong becomes candidate119 correct/97 unknown/0 wrong. Start/End diagnostic times remain unchanged. R1 End is still74.48600260416667s, confirmed75.3693359375s, confidence0.9180924279198346: approximately3.003ms beyond the unchanged GT upper bound74.483s. It is not a qualified timing success. Five fixed negative windows produce no diagnostic End. Runtime was188.049s legacy /188.391s candidate; concurrent test activity prevents treating this as a controlled performance benchmark.

Old qualification bundles are actually rejected. Fresh static/native measurements and original physical split/exposure review support a new private **Start-only** bundle for timer, purchase_phase and ui_transition; it is not a fingerprint-only rewrite or an End admission. Actual qualified native analysis processes358 frames, emits R1 Start at4.102669270833333s (confirmation4.202669270833334s, confidence0.9117099378029602), and preserves attributes through one partial Package and one Trace event. End, snapshots and owned player facts remain zero. Production112.205s, total148.795s, PNG607,990,858 bytes, process peak RSS133,169,152 bytes. The actual39-frame application integration preserves the same native→Package→Trace result: application10.409s, total15.709s, peak RSS148,799,488 bytes. Both post-production canonical R1-start assertions pass. These bounded checks do not exercise the full application sampler or full E2E.

## Additional-source regression and independent event-image assessment

The candidate is frozen before negative replay and new event discovery. The original negative candidates (four windows,76 native frames) still produce zero result matches, diagnostic Ends and owned facts. They lack independently certified full temporal negative GT, so this is a bounded regression rather than a measured false-positive rate.

Actual current producer replay on the **previously exposed** WON788–792.5s event now produces one diagnostic End at788.6333333333333s, confirmed789.2166666666667s, confidence0.9150651693344116, with the original strict tracker and unchanged one-second deadline. The real fourth consecutive `7` read is recovered; no unknown gap is bridged. Its271 frames contain171 caption matches. This is an exposed regression, not independent End timing qualification; no formal event is admitted.

For new event-image evaluation, reserve615–715s after the mask freeze. The previously observed600s and720s endpoint contexts and their boundary episodes are excluded. Source-only discovery identifies the distinct5–2→6–2 episode, separated from development by a purchase/active phase. Earlier1530–1800s discovery was already exposed to the rejected temporal experiment and is not recycled as wholly unseen data. This is a same-recording physical-event evaluation, not an entirely unseen-video claim.

Acquire694–701s as421 consecutive decoder-owned frames (784,418,882 PNG bytes, below1GiB). Freeze assistant source-only labels on six exact crops **before** either reader call. The first three show5–2 with a Spike icon; the latter three show retained decimal22.37, with score5–2,5–2,6–2. Animated caption supports are marked ambiguous rather than promoted to complete positives. No exact internal-game End GT or independent human temporal annotation is supplied. Both legacy and candidate use the identical cached native manifest and labels, with an earlier300s frame for geometry only. No active Start or source-epoch continuity is inferred from that prefix.

Both runs produce9 correct/3 unknown/0 wrong selected score fields, and four correctly rejected non-complete caption supports. All six selected Spike/retained-decimal controls remain unknown as countdowns. There are no changed score values across the entire421-frame baseline/candidate comparison, and both diagnostic End counts are zero: this held event shows no improvement. The aggregate records both completed producer runs, source/label hashes, field comparisons and non-countdown controls. These source conditions do not supply the numeric countdown transition required by the existing End path. No End candidate can turn this event into formal timing qualification, and a zero diagnostic End is not evidence of a false-negative-free detector. No held outcome is used for tuning.

## Verification and remaining gates

New synthetic safety tests37 PASS; related score/End tests131 PASS; dataset38 PASS. Ruff, mypy (133 source files) and UTF-8 audit (zero unresolved sites) pass. Full local run: **3801 PASS /4 FAIL /9 SKIP**,476.53s,coverage86.6206%,exit1. The same existing spectator failures are recorded by full test name in the aggregate; no Qt shutdown abort is observed. Exact-commit CI must be reported separately from predecessor CI.

Remaining gates: independent exact temporal End and negative annotations; delayed caption and Spike/decimal-clock development with independent evaluation; a continuous same-epoch active Start→End path; complete R1/R2 Package membership/Trace and R2-to-EOF no-false-End evidence. R2 formal native geometry admission is still unproven. Full E2E is not rerun; adopted canonical baseline23 PASS/55 FAIL/4 NOT_EVALUATED remains unchanged. Source images, profiles, contracts, original labels, exposure ledger and bundles stay private and Git-ignored. No main merge or issue closure is performed.

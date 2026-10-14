# Fixed sampled HUD/visual integration and OCR environment recovery

## Problem and method

Verify current candidate behavior on the existing fixed30point manifest before
another standard full E2E. The production replay receives only PTS and genuine
calibration-prefix acquisition settings; expected states/values remain solely
in the unchanged frame evaluator. No random selection or fabricated continuity.

Run baseline profile13 and the guarded global-numeric candidate under the same
code, frames and preprocessing. Separately exercise real HudVideoProcessor and
RealVisualAnalyzer once per point with a fresh prefix context and the exact
unchanged current qualified whole-source native output. Verify source/code/
profile/qualification/input hashes before reuse and at completion. Native
boundaries originate from10259source frames, never from sparse point jumps.
They are revalidated in each case, not counted as90independent detections.

## First comparison and environment gap

Without a system Tesseract executable, current baseline produces5PASS/14FAIL/11NE;
candidate13PASS/6FAIL/11NE. State counts match the historical baseline:
20unknown,3live,5spectator,2buy menu. The actual per-point HUD/visual/native merge
also gives13/6/11, retains the three source-native boundaries without modifying
them and leaves player facts/state with the main recognizer.

Investigate baseline's two missing historical HP passes instead of attributing
the difference to candidate improvement. Profile13 configures its existing HP
reader with `executable: tesseract`; no executable/package was installed in the
current environment. Missing OCR yields unavailable HP with confidence0. This
is a dependency gap, not permission to infer80or relax ownership.

## Controlled private dependency recovery

Administrative installation is unavailable. Download packages from the machine's
official Ubuntu repository and extract with `dpkg-deb -x` into private
`outputs/toolchains/tesseract-20261014/`. Record package/binary/English-model/wrapper
SHA256 values. Include tesseract5.3.4, libtesseract, leptonica, libgif, English and
orientation models. A private wrapper selects its libraries/data and limits
OpenMP to one thread; no system package, PATH, profile or `.env.local` is changed.

Launch only fresh isolated sampled reader processes with that private PATH.
**Do not reuse the prior native recognition output under this changed OCR
environment.** Decoded images remain reusable; recognitions are executed anew.
Existing reader configuration and acceptance conditions stay unchanged.

## Previous / Current / Delta with matched OCR availability

| Fixed sampled metric | Baseline13 | Candidate | Delta |
| --- | ---: | ---: | ---: |
| PASS | 7 | 15 | +8 |
| FAIL | 12 | 4 | -8 |
| NE | 11 | 11 | 0 |
| Unknown | 20 | 20 | 0 |
| Live | 3 | 3 | 0 |
| Spectator | 5 | 5 | 0 |
| Buy menu | 2 | 2 | 0 |
| Labelled wrong values | 0 | 0 | 0 |
| Point-stage wall seconds | 205.808 | 207.457 | +1.649 |

Player validity and primary state remain identical at every point. This improves
labelled numeric coverage, not identity classification or full-match accuracy.
The remaining four failed points are42.969336,124.536003,147.502669 and170.002669:
timer remains unavailable at each;147.502669also lacks ally score and170.002669
lacks enemy score. Values are not guessed. Eleven points have no independent
expected labels and remain NE; no new ground truth is created.

Without OCR, baseline/candidate isolated stages take161.749/163.044seconds;
the separate per-point HUD/visual/native integration takes1072.505seconds.
Those timings describe different processing scopes. The private OCR comparison
is the matching205.808/207.457second pair; no speed gain is claimed.

## Diagnostics and remaining gates

The restored-OCR diagnostic process exited1 because its last console print
referenced a removed merge summary. Both recognitions, saved reports and terminal
integrity checks completed before that exception. Preserve the failing script/
log; a separate finalizer rechecks every input/report hash and exits0 without
re-recognition. This is a diagnostic summary error, not a ignored test failure.

No production behavior changed in this phase. Standard full E2E remains unrun;
the adopted baseline is23PASS/55FAIL/4NE. Full regression and current Windows CI
for the dirty Strict storage feature remain pending. Before a full application
run with private Tesseract, verify native qualification/collection under that
same OCR environment: code/profile equality alone must not justify recognition
reuse after changing an external reader dependency. Independent temporal
qualification also remains incomplete; do not install the one-exposed-end audit
as a default.

Machine-readable comparison and dependency hashes:
`e2e_reports/match_001/strict_replay_sampled_merge.json`.
Local original integration:
`outputs/recognition-investigation/strict-replay-sampled-merge-20261014/`.
Local controlled OCR comparison/finalizer:
`outputs/recognition-investigation/strict-replay-sampled-tesseract-20261014/`.

## Full regression in restored OCR environment

Full suite with the same privateTesseract path: **3646PASS/5SKIP in2361.57s**;
RuffPASS, mypy131sourcefilesPASS. The actual isolated-English-language-data TSV
integration now passes instead of skipping for missing Tesseract. Remaining skips
are the separately configured real-video anchor fixture and host/PowerShell
Windows checks. No new test failure or assertion relaxation occurs. Current
branch WindowsCI and exact-runtime native verification before full main use
remain pending; adopted23/55/4 remains unchanged.

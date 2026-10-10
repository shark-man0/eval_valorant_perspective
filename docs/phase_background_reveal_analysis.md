# Current-image phase background reveal assessment

## Problem

Multiple purchase-panel structures disappear together, but low contrast alone does not distinguish removal from obscuration. Test whether current surrounding wall appearance independently supports the pixels revealed in those structures. Target remains `GT-R1-ROUND-START`; no acceptance window or expected timer is used.

## Evidence

HEAD `e9ecaf8f2f0f0dfa1f9433d40a598ec8909e9ce3`. Source and all 30 exposed native frames are bound to the existing source report and encoded/decoded pixel hashes. [Machine-readable measurements](../e2e_reports/match_001/phase_background_reveal.json) contain exact context/target bounds, code hash, integer PTS and terminal input verification.

Five reviewed current-image regions outside the panel fit an affine BGR color plane. Each context region is also evaluated with a model fitted to the other four regions. Panel target pixels never participate in fitting. Targets are the same upper/lower edges and purchase button used in the previous structure diagnostic. This is descriptive extrapolation, not a camera model, semantic classifier, NCC replacement or qualification.

## Independent image evidence

Mean maximum-channel residuals, in 0–255 color units:

| Target | Before, 4.086003 s | After, 4.102669 s | Delta |
| --- | ---: | ---: | ---: |
| Upper panel edge | 25.725 | 1.945 | -23.780 |
| Lower panel edge | 24.688 | 1.167 | -23.521 |
| Purchase button | 58.985 | 0.871 | -58.114 |

Leave-one-region-out context residuals at the after frame are 1.815 / 1.159 / 1.511 / 1.463 / 1.355. Thus the revealed pixels are consistent with this simple current surrounding-background appearance. No numeric acceptance threshold is defined.

## Competing hypotheses and sensitivity controls

Four artificial controls modify only the first exposed source frame. They are explicitly synthetic sensitivity checks, not native frames, actual reviewed errors, independent holdout or new ground truth. Parent and modified pixel hashes are recorded; the source video and saved PNGs are unchanged.

| Artificial modification | Upper edge residual | Lower edge residual | Button residual |
| --- | ---: | ---: | ---: |
| Black panel cover | 149.906 | 97.022 | 185.911 |
| White panel cover | 110.690 | 72.554 | 137.009 |
| Surrounding median-color panel cover | 1.939 | 4.342 | 0.315 |
| Surrounding median-color text-only cover | 24.806 | 26.004 | 59.987 |

Color consistency separates conspicuous full-panel covers; measuring separate structures also exposes text-only hiding. However, background-colored full-panel replacement can have residuals comparable to the genuine after-frame, especially upper edge and button. This is a limitation of the measurement, not evidence that the real video was edited. It does not justify requiring an additional video or asserting a production false positive.

## Continuity decision

Current-image color extrapolation alone cannot authorize phase disappearance, establish source continuity or exclude a background-preserving content jump. Reject it as a sufficient absence contract. Do not repeatedly tune its residual threshold against these now-exposed controls. It remains a descriptive corroborator of full-image review.

## Contract change

None. Every actual/control output has `phase_absent=null`, `runtime_authorized=false`, `scene_continuity_proven=false` and `qualification_created=false`. No evidence dictionary is adapted into a trusted proof. GT, OCR/NCC/geometry/ownership thresholds, source video and sampler are unchanged.

## Tests

Five background-reveal tests check target exclusion from model fitting, independent context model error, explicit withholding even for perfectly matching uniform backgrounds, and rejection of overlapping regions. With the six structure tests: 11 passed in 0.58 seconds. Ruff's new diagnostic line-length issue was fixed before the real measurements. Final Ruff passed for `src tests scripts/e2e` and the new diagnostic; mypy passed for all 112 source files. `git diff --check` passed.

## Previous / Current / Delta

| Metric | Previous | Current | Delta |
| --- | ---: | ---: | ---: |
| Current-background target measurements | 0 | 90 (3 × 30 frames) | +90 |
| Artificial sensitivity controls | 0 | 4 | +4 |
| Qualified phase-absence producer | 0 | 0 | 0 |
| Canonical PASS / FAIL / NE | 23 / 55 / 4 | Unmeasured | Unmeasured |

Saved-image runtime: 5.377793 seconds; there is no comparable previous run. No targeted/sampled/full E2E candidate was created. All 82 archived assertion entries remain unchanged. No new production event/package or canonical negative/discontinuity result is claimed.

## Remaining blocker

Current background appearance and absent UI structure must be joined to independently qualified temporal source evidence. A source-owned model should distinguish camera/world continuity from view-model presentation and retain every clock observation, rather than claiming continuity from a flat ROI. The existing paired producer is still unqualified. Next assess temporal background structure spanning panel disappearance with the already available native source chain; do not create another favorable color-fit variant or promote these synthetic controls to qualification. Windows execution remains unverified.

# Scene source training support screen

## Problem

A source reference can initialize against itself while providing no useful next-frame coverage. The rejected doorway development profile demonstrated that a new reference alone cannot establish qualification. Screen measured multi-frame appearance support before reserving another independent cohort; do not count self comparison as evidence of generalization. Target remains the scene/UI source path upstream of `GT-R1-ROUND-START` and lifecycle/package assertions.

## Change and contract

`scripts/diagnostics/check_scene_training_support.py` is a standalone diagnostic inspection command. It consumes the saved source cohort, profile and common implementation's development measurements. It is **not yet integrated into a reference generator or production** and cannot create a qualification report.

The CLI validates source-report/profile hashes and current production fingerprint, loads/validates profile-relative assets with the common source binding, checks complete measurement/source correspondence and a single native epoch/time base, and verifies encoded native image hashes. Distinct native pixel hashes/ticks and consecutive 256-tick progression prevent duplicate/skipped frames from inflating support. Once a saved episode stops, a subsequent claimed scene link is rejected.

The appearance screen requires at least three distinct non-reference initialization matches and three observed scene links. Reference-self matches are reported separately. This additional development screen does not alter production acceptance thresholds or the existing global qualification loader. A passed screen still has no qualified current world semantics, scene/UI proof, holdout correctness or runtime authority. Independently reviewed qualification remains a separate requirement.

For each saved affine model, the tool additionally measures projected source pixels touching the protected clock/phase mask or image boundary, using the same canonical exclusion geometry and bilinear remapping as the common domain audit. It does not refit the model, trim regions, change NCC, infer world labels or repair rejected decisions. Input profile/native/code bindings are checked at completion.

## Evidence and result

HEAD `e9ecaf8f2f0f0dfa1f9433d40a598ec8909e9ce3`.
[Verified screen](../e2e_reports/match_001/scene_training_support_gate_verified.json) inspects the unchanged 12-frame doorway development report. It returns exit code **2**, meaning completed development rejection, rather than an execution failure. Exit 0 means only that appearance training minimums passed; malformed/stale inputs raise an error.

Results: one reference-self match, zero distinct non-reference matches, zero observed links, and first episode stop at native tick 83241 with `insufficient_reviewed_world_tracks`. The upper-left region has 124/3720 projected pixels touching exclusion/boundary at that frame; the other two regions each have zero. This numerical footprint evidence corroborates the previous projection diagnosis without attributing every tracking failure to it. Saved inputs are not decoded or recognized again.

## Tests

Eight new tests cover successful descriptive-only screening, rejection of self-only support and missing temporal links, duplicate/gapped input, prohibited rejoining, projected phase exclusion and nonfinite geometry. Including the two file-binding tests: 10 passed in 1.31 seconds. Ruff passed for `src tests scripts/e2e` and the new script. Production source is unchanged; the preceding 112-file mypy pass remains applicable. The final addition checks terminal diagnostic code bindings as well as source assets. No canonical E2E is warranted by this rejected profile.

## Command

Use a fresh output path; existing reports are never overwritten:

```text
python -m scripts.diagnostics.check_scene_training_support --training-report e2e_reports/match_001/doorway_source_coverage_development.json --source-cohort e2e_reports/match_001/native_scene_entrance_cohort.json --profile outputs/recognition-investigation/doorway-source-coverage-development-20261010/profile.json --output outputs/scene-training-screen.json
```

This command currently accepts the bound development report shape used by the doorway experiment. It is not a general report-schema migration or a tiered E2E runner.

## Previous / Current / Delta

| Same rejected development case | Previous manual assessment | Current screen | Delta |
| --- | ---: | ---: | ---: |
| Non-reference initialization matches | 0 | 0 | 0 |
| Observed links | 0 | 0 | 0 |
| Reference-self matches | 1 | 1 | 0 |
| Projected invalid source pixels in region 0 at next frame | Not counted | 124/3720 | New diagnostic |
| Qualified source/UI producers | 0 | 0 | 0 |
| Canonical PASS / FAIL / NE | 23 / 55 / 4 historical | Unmeasured | Unmeasured |

The initial inspection took 0.675510 seconds; the verified report records its own wall-clock time for the same saved inputs. These are inspection runtimes, not recognition/E2E speed improvements. All 82 archived assertion entries remain unchanged.

## Remaining blocker / next implementation

The screen prevents a self-only development result from being mistaken for useful source coverage, but does not solve source acquisition. The next actual source-profile design must establish textured, distributed background correspondence whose projected footprints remain eligible over its training motion, then pass independent controls. Do not retune the rejected doorway crops to reach counts or reserve more arbitrary uninitialized cohorts. Native qualified producer installation, phase-absence qualification, lifecycle merge and canonical improvement remain unfinished. Windows execution is unverified.

# Start components share one current profile and physical split audit

## Problem, root cause and fixed targets

`GT-R1-ROUND-START`, `GT-R2-ROUND-START` and related count/ordering assertions
need jointly qualified phase/timer/UI inputs. Prior static phase and timer
reports have different profile fingerprints. A native phase negative at
69.002669seconds is also timer training. Combining those reports unchanged
would misstate one runtime profile and cross-component split independence.

## Frozen change and evidence

Re-evaluate existing reviewed native images with the actual native start profile:
`score-rowcontrast-late-result-diagnostic.templates.json`. Its phase binding
matches the earlier phase profile; their differences are score readers and the
result binding. No reference assets, preprocessing, thresholds or source labels
change. Hash-bind current code/profile and the selected source files before
predictions. Exclude only the already identified phase control at source
PTS1059881before replay, retaining its earlier diagnostic record.

Current shared static phase detection supports3/3training,8/8reviewed positives
and12/12eligible negative rejections. Current timer replay preserves25correct,
7unknown,0wrong on32existing holdout images. Runtime22.055seconds for55reader/
detector input cases on saved native images, excluding video decode.

## Physical split audit

Compare source video plus integer PTS, not PNG/JPEG encoded hashes alone.
The joint physical sets contain79training inputs (76timer +3phase),40holdout
inputs (32timer +8phase),12eligible phase negatives. All three pairwise split
intersections are empty. Hash/terminal checks pass. Shared-code fingerprint and
phase profile fingerprint now match the current native transport replay.

The initial audit used the split name `holdout`, but the older phase report
names positives `holdout_positive`. It therefore initially reported32rather
than40holdout inputs. Correct this audit using all55saved prediction rows and
recognized split names, retaining the initial audit and its hash. Recheck all
intersections; no additional reader predictions or selection changes are used
to repair the count. The corrected final audit is authoritative.

## Previous / Current / Delta

| Same eligible source cases | Previous | Current | Delta |
| --- | ---: | ---: | ---: |
| Phase training correct | 3 | 3 | 0 |
| Phase holdout correct | 8 | 8 | 0 |
| Phase holdout wrong | 0 | 0 | 0 |
| Eligible phase negative rejections | 12 | 12 | 0 |
| Phase negative false positives | 0 | 0 | 0 |
| Timer correct | 25 | 25 | 0 |
| Timer unknown | 7 | 7 | 0 |
| Timer wrong | 0 | 0 | 0 |
| Created qualification sidecars | 0 | 0 | 0 |

Previously13phase diagnostic negatives included one cross-component training
conflict. The12eligible control comparison above uses the same12cases on both
sides; it does not hide or improve a recognizer outcome by removing a failure.

The current phase component support is retained as a partial diagnostic proof
under one common profile/code fingerprint. It is not installed as a complete
qualification sidecar. Previous phase+timer static reader runtime17.035+8.415
seconds involved another profile and64timer calls with JPEG comparisons; the
new55case22.055secondrun has a different call population. Do not call that a
pipeline performance improvement.

## Tests, limits and remaining blockers

No production or tests changed in this replay. The preceding303relatedtests,
Ruff and mypy results remain applicable. Static nominal crops do not establish
current accepted geometry, temporal phase disappearance or whole-source
continuity. These reviewed images are already exposed source cases, not a new
blind cohort. The geometry-only shared reference does not itself prove temporal
continuity across the excluded prefix gap.

Timer control scope/current common-profile replay and independently reviewed
continuous UI support/provenance remain to be completed. Source-field negatives
and synthetic controls must describe their actual tested scope; unknown timer
predictions must not be labelled as absence. This adds no natural-negative-only
requirement or extra video prerequisite.

No formal events, package promotion, qualification installation or full E2E.
All82canonical entries retain historical23PASS/55FAIL/4NE; Current full/Delta
unavailable. Windows runtime remains unverified. Next, replay existing reviewed
timer type controls through the exact configured reader input transformation,
and audit their parent source identities before any joint qualification.

Machine-readable source hashes, PTS, outcomes, common-profile component support
and corrected audit:
[joint_start_component_replay.json](../e2e_reports/match_001/joint_start_component_replay.json).

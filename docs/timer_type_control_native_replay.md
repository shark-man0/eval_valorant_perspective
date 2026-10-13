# Current configured timer wrapper rejects eight native type controls

## Problem and targets

`GT-R1-ROUND-START` and `GT-R2-ROUND-START` require qualified timer/phase/UI
inputs. Existing eight timer negatives are actual score-/HP-adjacent source
fields, tested previously as isolated75×40crops. That did not verify the current
configured reader's125×85outer ROI and subregion transformation, or native
parent PTS/split provenance. Keep them as type-discrimination controls, not
natural timer-absent observations at the genuine timer ROI.

## Frozen selection and native evidence

Reuse all eight existing control cases and reviewed spatial bounds without
choosing new cases from predictions. Native target centers are fixed from
existing review times before decode. The decoder returns and verifies each
actual integer PTS, time base, source epoch, source/pixel/encoded hash and image
geometry. Retain only the preselected center for static field evaluation;
acquisition itself verifies all40frames in the eight short continuous windows.
These are exposed source cases, not a new blind holdout or temporal stream.

Native contact-sheet review precedes current predictions. Four fields contain
one score-adjacent zero; the other four contain scene/plain colour/non-timer
text. No displayed clock is present in these selected fields. This says nothing
about the genuine timer elsewhere in the full source image.

For each75×40field, choose its actual125×85outer source rectangle such that the
existing configured subregion[25,27,100,67]yields exactly that field. No pixel
editing, resizing, fake calibration or production geometry translation. Verify
pixel equality between the wrapper's inner input and the declared source crop
for both original JPEG and native raster. Original cached negative PNGs also
match the original source crops and their pixel hashes. Encoded PNG hashes
are deliberately not confused with decoded pixel hashes.

## Acquisition failure and guard preservation

The first request contained only one frame and was rejected by the existing
native decoder's minimum-two-frame contract, before any reader predictions.
A repaired five-frame interval with endpoints exactly on native ticks then
failed at the sixth source case: probe expected
[1685289,1685545,1685801,1686057,1686313],while decode omitted1685289.
A transparent diagnostic wrapper records the original subprocess/parser returns,
without altering them, and preserves the complete-coverage rejection.

Declare acquisition endpoints halfway between source frame ticks, encompassing
the same five target native frames. The wider interval verifies all expected
frames and includes the previously missing1685289. Thus this rejected request
is not evidence that the recording lacks that source frame. The exact FFmpeg
endpoint/seek exclusion mechanism is not determined. No decoder guard, PTS
policy, recognition condition or full sampler is relaxed. All failed selections,
inspection results and corrected acquisition parameters remain hash-recorded.

## Current / Previous / Delta

| Same eight type controls | Previous raw JPEG field | Current configured JPEG wrapper | Current native wrapper | Delta vs previous |
| --- | ---: | ---: | ---: | ---: |
| Rejected | 8 | 8 | 8 | 0 |
| False positive | 0 | 0 | 0 | 0 |

Current16reader calls take1.560seconds, excluding native acquisition118.147seconds.
The previous0.356secondcontrol result also included four known-positive error
witnesses and used isolated fields, so it is not a comparable pipeline benchmark.
Acquisition/runtime numbers describe successful final runs; failed attempts are
recorded separately, not included as successful input processing.

Eight exact native parent PTS are disjoint from the previously audited joint
training79,holdout40and phase-negative12sets. Adding the type controls yields
20physical negative source inputs. This audit does not imply all20test the
same component or that eight controls represent a whole-video false-positive
rate. Native controls use full source pixel identity, not crop hashes alone.

## Change, tests and conclusion

No production/profile/threshold/GT/assertion change. Current common-profile
fingerprint and code fingerprint match the previous55casejoint static replay.
Terminal input/source/profile/code checks pass. The preceding303relatedtests,
Ruff/mypyverification remains applicable; no unnecessary full regression/E2E.
Windows runtime unverified. No formal event, qualification sidecar or canonical
status promotion: historical23PASS/55FAIL/4NEis retained.

The configured type-control transformation and native physical parent audit
now exist. Complete the timer training/holdout/control provenance aggregation
and independent continuous UI review before global start release. Do not impose
a new natural-negative-only requirement, mislabel readable-positive unknowns
as absence, or treat static type rejection as geometry/temporal qualification.

Machine-readable PTS, bounds, pixel equivalence, guard diagnosis and comparison:
[timer_type_control_native_replay.json](../e2e_reports/match_001/timer_type_control_native_replay.json).

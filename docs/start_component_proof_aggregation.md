# Source-audited timer/phase aggregation remains incomplete for release

## Problem and fixed targets

The global start route for `GT-R1-ROUND-START` and `GT-R2-ROUND-START` needs one
qualified timer/phase/UI bundle. Static phase and timer validation and current
native type controls now share the actual native profile fingerprint. Aggregate
their original source provenance, not predicted confidence or GT values, and
verify that an incomplete bundle cannot authorize formal lifecycle events.

## Training/reference audit

All76timer training source images exist and hash-verify:64frozen JPEG images
match their recorded decoded pixel hashes, and12native PNGs match their encoded
training-selection hashes. Native source ticks for12come from original decoder
metadata; the64legacy rounded annotations map uniquely to the known15360/256
source grid and match the existing declared training ticks. This is not a new
native decode of those64images. Keep that provenance distinction explicit.

All ten current digit reference PNG hashes equal the frozen alphabet report's
references. Current configured thresholds remainNCC0.90,class margin0.04.
Historical per-class minimum support checks remain recorded; this audit proves
asset/source equality and does not claim new current training reader predictions.
No reference selection or numeric label changes.

The timer partial component contains76distinct training source pixel hashes,
32current native holdout hashes and8current native type-control parent hashes.
Physical and pixel splits are disjoint. The joint phase/timer physical sets
remain79training/40holdout/20negative source inputs. Component scopes differ:
eight timer negatives test actual alternate fields through the configured ROI
wrapper, not natural absence at the genuine timer location or geometry accuracy.

## Current component evidence and loader admission

Timer holdout is25correct/7unknown/0wrong; its eight current native controls all
reject. Purchase phase retains3training/8correctholdout/12negative rejections.
The aggregation records review provenance and source/asset hashes under the
current common profile and code fingerprints. It contains no expected timestamps,
round IDs, acceptance windows or Validation Pack runtime input.

Write only a clearly named local `partial-components.json`, outside runtime
profile configuration. It contains timer and purchase_phase;ui_transitionis
not fabricated. Actual `GlobalLifecycleQualification.load` with the matching
source assurance rejects it with `Missing or unknown global lifecycle component`.
No qualification is installed and no formal event is authorized. This rejection
verifies the incomplete-bundle gate, not approval of an overall release proof.

## Previous / Current / Delta

| Same reviewed input metric | Previous | Current | Delta |
| --- | ---: | ---: | ---: |
| Timer correct | 25 | 25 | 0 |
| Timer unknown | 7 | 7 | 0 |
| Timer wrong | 0 | 0 | 0 |
| Timer type-control false positives | 0 | 0 | 0 |
| Assembled current timer partial proof | 0 | 1 | +1 |
| Installed release qualifications | 0 | 0 | 0 |

Aggregation/terminal hash audit takes7.219seconds; this is not frame recognition
or a comparable E2E runtime. Canonical82statuses remain historical23PASS/55FAIL/
4NE, not a current full run or zero-delta full measurement.

## Tests and remaining blocker

No shared production/profile/GT/assertion code changes in this aggregation.
Existing303relatedtests,Ruff/mypyremain applicable. Real source/reference hashes,
physical/pixel split checks and actual production loader rejection pass. No
unnecessary full regression or full E2E. Windows runtime remains unverified.

The remaining required component isui_transition. Existing source replay has
two known development start episodes and three negative windows.133accepted
clock observations are not133manually proven correct values. Replaying or
truncating one boundary into multiple cases must not manufacture independent
positive events. Likewise, the loader's minimum three distinct source-image
hashes must not be reinterpreted as an invented three-video/three-episode rule.

Audit continuous UI support at the actual physical-frame/context level, retain
original selection/development exposure, review the source rather than deriving
labels from tracker predictions, and clearly distinguish correlated support
images from independently evaluated event cases. Existing exposed development
images cannot be relabelled as a new blind holdout. Do not install the partial
bundle, remove UI qualification, or use GT to create missing support.

Machine-readable component proof, training provenance, source/asset hashes and
actual loader rejection:
[start_component_proof_aggregation.json](../e2e_reports/match_001/start_component_proof_aggregation.json).

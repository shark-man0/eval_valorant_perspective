# DEVELOPMENT full-recording comparison

This is a Draft progress report for #121, using three previously exposed,
registered, distinct physical matches. It does not establish unseen or
all-match generalization. Private media, Profiles, exact native samples,
review answers, and weights remain outside Git. No Production route is adopted.

## Fixed automatic baseline

One shared pixel observer configuration processed all three files without a
recorder roster, human initial state, Source ID, map, agent or timestamp as
recognition inputs. Match identity is used only for intake, provenance and
physical-match partitions. Original observations and source bytes are preserved.

| Match | Recorded seconds | Observed second bins | Native points | Round UNKNOWN bins | Inferred-only known Round bins | Wall seconds | Python peak MiB |
|---|---:|---:|---:|---:|---:|---:|---:|
| A | 2053.40 | 2054 | 3163 | 604 | 324 | 992.12 | 281.44 |
| B | 2541.47 | 2542 | 3648 | 1039 | 459 | 1109.60 | 315.47 |
| C | 1609.08 | 1610 | 2717 | 648 | 322 | 875.92 | 256.38 |

Partial final seconds are bins, not extra recording duration. Each bin contains
at least one selected video point; this is not continuous semantic observation.
Life/camera are UNKNOWN throughout this automatic baseline. Map is UNCONFIGURED.
The three processes ran concurrently. Wall time includes source hashing, native
decode, observation and state/output work. Python peak excludes child processes.
The adaptive budget deferred 115/156/93 windows, respectively, and is not
exhaustive boundary coverage. Selected PTS/pixels were checked, not all frames.

## Clock component correction on the same native points

The known wrong Round point was carried BUY because one seconds glyph failed
the unchanged 0.90 full-clock threshold. The minute glyph independently passed.
The opt-in `clock_prefix` observer preserves all ten competing glyph classes,
0.90 acceptance, 0.04 margin, colon and clipping checks. Accepted minute >= 1
supports the existing ACTIVE range rule only with current Round geometry and
without a current BUY/Result conflict. Numeric clock seconds stay unknown.
There is no Source/time-specific correction or chosen internal event time.

For a fixed-input comparison, all 9,528 original observations were retained
unchanged. Only automatically eligible unread-clock points were redecoded:
757/980/734 points, with exact Source/native PTS/timebase/size/pixel checks.
Clock evidence was added as a separately fingerprinted stream to the same state
engine. This is a fixed-observation add-on comparison, not another full execution
of every observer. The full-recording CLI separately exposes the same optional
pixel component rule. The option remains off by default.

| Match | Reviewed Round points | Baseline correct / wrong / abstained | Clock add-on correct / wrong / abstained | Previously correct lost |
|---|---:|---|---|---:|
| A | 2 | 2 / 0 / 0 | 2 / 0 / 0 | 0 |
| B | 7 | 6 / 1 / 0 | 7 / 0 / 0 | 0 |
| C | 2 | 2 / 0 / 0 | 2 / 0 / 0 | 0 |

Micro reviewed-point correctness: 10/11 -> 11/11. Mean of per-match reviewed
fractions: 95.24% -> 100%. These are boundary-selected development points,
not random full-match accuracy. Match B was the worst labeled baseline match;
its incomplete-clock evidence explains the measured error. Round UNKNOWN bins
become 604/1039/645; the three-bin reduction is unreviewed and is not scored as
accuracy improvement. Inferred-only known Round bins become 318/455/319.
All life/camera values at all 9,528 native points are unchanged by this add-on.

## Forward, offline and learning controls

On the same 11 reviewed Round points, forward and the previous offline rule
both score 10 correct/1 wrong. Offline transition brackets score 10 correct,
0 wrong/1 abstained; this represents uncertainty, not a recovered correct state.
Future information has not added a correct reviewed label in that control.
The forward-only control now also excludes future DOWNED evidence; its real-data
predictions were reproduced byte-for-byte, alongside a regression test of the
previously leaking branch. Default engine behavior is retained.

Weak-label temporal reranking C and self-supervised-feature-plus-reranking D
were fitted with the held-out physical match excluded. Both score 9/11, against
the rule's 10/11, losing one previously correct point on Match B. Neither is
adopted. Weights and all three fold outputs are private and reproducible. Existing
visual calibration exposure is not an untouched model holdout. Human review
labels were not fitted into these temporal models.

A separate image-only camera candidate experiment compares broad spectator UI
features with two shared tighter portrait/name/control regions. Broad features
score 3/7 on the original reviewed points. Tight features score 7/7 there and
4/4 on additional predictions sealed before the human answers: A 2/2, B 3/3,
C 6/6. Held-out match samples are excluded from fitting; original comparison-only
labels and the four new comparison replies are not training labels. Training-side
human controls are used only in other physical-match folds. UI feature design
is development-exposed. Models/predictions reproduce byte-for-byte; the report
has identical JSON values with key-order-only differences. At that image-only
stage it was not integrated into timeline inference. A later reviewed SPECTATOR
negative increases the denominator to 12: the centroid gives 11 correct/1
abstained. Three prototypes alone give 8 correct/4 abstained and are rejected.
The bounded shared-engine follow-up is below. REMOTE and full negative episodes
remain unmeasured. Classifier point counts do not establish safe attribution.

## Bounded view and persistent-report follow-up

Replay a fixed first 150 seconds per match, including the already fixed native
review controls: 2,109 native points / 450 second bins. This cohort includes
older exact controls absent from the full cadence and a newly reviewed frame;
its 12 life/camera points must not be compared with the full run's seven-point
denominator. Per-fold learned weights exclude the held-out physical match.
The inference procedure is shared; these are not identical weights in all folds.
New comparison replies are not fitted or used for initialization. Existing
Profile/UI design exposure still prevents untouched whole-model claims.

The private pixel observer proposes view claims, HP displays and an exact
Japanese owned-victim verb phrase. It receives no Source, timestamp, previous
state or roster. The existing shared engine alone infers life and transitions.
The raw phrase is an unqualified observation, not an imputed complete header,
normal-death certificate or event time. Existing competing-view exclusions
veto learned owner claims. SELF retains REMOTE/UNKNOWN alternatives; weak
view claims cannot sponsor current Map evidence or recorder correspondence.

| Match | Reviewed life | Baseline correct / abstained | Constrained candidate correct / abstained | Reviewed camera / candidate correct | Round correct retained |
|---|---:|---|---|---|---|
| A | 2 | 0 / 2 | 2 / 0 | 2 / 2 | 2 / 2 |
| B | 3 | 0 / 3 | 3 / 0 | 3 / 3 | 7 / 7 |
| C | 7 | 0 / 7 | 7 / 0 | 7 / 7 | 2 / 2 |

An initial integration scored 11 correct/1 abstained on life, with one known
return left unresolved. Reusing a persistent report as fresh evidence created
another elimination hypothesis. The common engine now remembers bound display
signatures across Round changes, occlusion/unread gaps and reappearance. A weak
elimination claim without a readable signature cannot establish freshness. A
signature still needs prior owned-alive/round/spectator context. It identifies
display attributes, not physical events; genuinely different identical cards
can remain ambiguous. This retains the original candidate rather than inferring
a new death solely from its old display.

With the view exclusions and display-identity rule, reviewed life and camera
both score 12 correct/0 wrong/0 abstained; Round stays 11/11. Both per-match mean
and pooled reviewed-point fractions are 100%, with no baseline-correct point
lost. The six older correct Match B life/camera values are retained in this
bounded experiment. No wrong SELF is observed at the two reviewed SPECTATOR
points; this is not a population false-attribution estimate. Unlabeled candidate
events, including later candidates, are unscored. No internal event-time error
or independent full-episode accuracy is inferred from these point labels.
These counts compare the selected estimate with the human label; DEAD still
retains DOWNED/UNKNOWN alternatives and SELF retains REMOTE/UNKNOWN. They do not
establish reliable normal-death/down/remote separation.

This bounded experiment remains unadopted. The following full-recording stage
connects the same inference procedure through bound native suppliers. The older
runs are retained unchanged. Full-match REMOTE/negative coverage, unseen
generalization and Round numbers remain open. No formal Fact/Event or current
Map-owner evidence is issued by the weak model.

## Completed automatic composite runs

Three new full-recording runs completed with source bytes checked before/after,
selected native PTS/pixels checked, output hashes verified and 19 predeclared
native review references matched. Five references required additional native
points; all 19 retained their original/new epoch aliases. The frozen audit plan
contains no labels or initialization and is not given to the pixel observer.
There are 9,536 native points and 6,206 second bins across 6,203.949 recorded
seconds. All bins have a selected video observation; semantic support is sparse.

One primary recognizer uses identical frozen weights and rules on all three
matches. It is role-weight-held-out on A and training-side regression on B/C;
it is **not** a three-match independent model test. The separate LOMO role
weight comparison excludes the evaluated physical match from fit and uses only
the fixed coarse grid plus predeclared controls, excluding primary-selected
dense frames. Whole-model UI/Profile design exposure remains known DEVELOPMENT.

| Match | Native points | Round reviewed / correct | Life reviewed / correct | Camera reviewed / correct | Old source-bound correct lost |
|---|---:|---|---|---|---:|
| A | 3164 | 2 / 2 | 2 / 2 | 2 / 2 | 0 |
| B | 3650 | 7 / 7 | 3 / 3 | 3 / 3 | 0 |
| C | 2722 | 2 / 2 | 7 / 7 | 7 / 7 | 0 |

The baseline uses the same new native points, clock-prefix option and shared
state engine, with only the original HUD supplier: Round 11 correct/0 wrong/0
abstained, life 0/0/12, camera 0/0/12. Adding the unqualified view supplier gives
Round 11/0/0, life 12/0/0 and camera 12/0/0. Pooled and per-match-mean selected
label agreement are 100% in each domain, with zero baseline-correct losses.
The LOMO fixed-grid control has the same reviewed counts, against life/camera
abstentions in its own same-grid baseline. These are selected known-development
point agreements, not full-match accuracy, untouched evaluation or qualification.
The five additional life/camera review frames absent from the original cadence
are present in both new methods; the original seven-point full cohort must not
be used as the denominator for a 12-point improvement claim.

The six older correct life/camera values on B are recovered in this full route.
Across the enlarged reviewed cohort all seven source-bound correct domain
values are retained. No wrong SELF occurs at the two reviewed SPECTATOR points;
population false attribution and unreviewed death/return events remain unscored.
Forward, legacy offline and transition-bracket controls all agree at the same
11/12/12 reviewed domain points: no extra correct label from future context was
measured. The corrected comparison CLI reproduces every primary domain estimate
at all 9,536 native points from the original separate supplier archives.

| Match | Round UNKNOWN bins | Life UNKNOWN bins | Camera UNKNOWN bins | Inferred-only known Round / life / camera bins | Wall seconds | Python peak MiB | Deferred refinement windows |
|---|---:|---:|---:|---|---:|---:|---:|
| A | 613 | 913 | 804 | 322 / 415 / 325 | 1437.03 | 512.19 | 107 |
| B | 1035 | 885 | 765 | 458 / 1051 / 323 | 1729.76 | 578.59 | 121 |
| C | 649 | 592 | 491 | 318 / 527 / 228 | 1448.55 | 467.66 | 69 |

The original HUD-only same-native baseline has the same Round UNKNOWN counts
and UNKNOWN life/camera in all bins. Unlabeled UNKNOWN reductions are not scored
as accuracy gains. Native UNKNOWN Round reasons are unsupported observations;
life additionally lacks owned-death context or current return confirmation.
These domain-support gaps differ from absent video frames. Match B has the most
Round-UNKNOWN bins, but reviewed recognition is tied; there is no justified
worst full-match accuracy ranking. The known old B clock error was addressed
without a Source/time exception.

The three jobs ran concurrently, with a local test run overlapping part of the
measurement. Receipts include hashing, native acquisition, primary/sidecar image
inspection and shared primary/baseline state/output work, but exclude the later
fixed-grid LOMO replay. Python peaks exclude children and later replay; no total
system-memory or isolated speed comparison is claimed. The refinement budget
still leaves uninspected candidate windows. Learned role weights and report
signatures remain unadopted research; DEAD/DOWNED and SELF/REMOTE alternatives
and qualified-output suppression remain intact.

An additional replay joins 22/140 archived Map packets at exact full-run pixels
without altering their original epochs. All joined pools are retained in the
original full acquisition, with zero Round/life/camera selected-value changes.
The other 118 packets have no exact current full-run counterpart and are not
interpolated. Parallel epoch estimates remain separate: the first diagnostic
mistakenly collapsed four such comparisons by physical-key dictionary order;
the corrected comparison keys the original acquisition sample. This is archived
supplier reuse, not a generic full-video Map recognizer. Known self-role outputs
remain 0 correct/4 abstained; raw candidate retention is not role recovery.

Final local regression for this stage: 4,327 passed/9 skipped; Ruff, mypy (151
source modules) and Text I/O audit pass. Exact new-head Linux/Windows/package
CI is unverified and is not inferred from these local results. The Goal remains
open: independent Round-number validation, full Map/Zone processing, event/REMOTE/negative
coverage and unseen generalization are incomplete.

## Additive Round-number and UNKNOWN diagnosis

The shared engine now exposes current-score/phase Round-number candidates in
native frames, acquisition seconds and common seconds. The full CLI appends
numeric/candidate/uncertainty CSV columns. It does not count start candidates,
reuse unread previous scores, choose an ENDED score-update side, or resolve a
carried phase. Invalid/conflicting scores and parallel acquisition uncertainty
remain explicit. This is development inference, with no qualified number Fact.

Before editing the engine, code and input/output hashes from the completed
stage were frozen. Replaying the same cached observations for all four methods
on each match plus the exact archived Map replay produces 13 timelines. Removing
only the additive `round_number` fields gives the complete original outputs
unchanged, including observations, native samples, all previous state fields,
transitions, Map pools, second views and qualification suppression. This is a
state/output replay, not new full-length pixel recognition or improved accuracy.

| Match | Second bins | Selected unqualified number | Ambiguous number | No number candidates |
|---|---:|---:|---:|---:|
| A | 2054 | 825 | 667 | 562 |
| B | 2542 | 684 | 905 | 953 |
| C | 1610 | 408 | 508 | 694 |

No independent Round-number accuracy is inferred from those coverage counts.
Three frozen exact review points currently abstain on number selection: two
lack a complete accepted score, and the third has a score but no current phase.
Those display score/phase answers were pending at that stage; their later
exact-frame comparison is recorded below.
Three new 60-second native CLI pilots verify the new JSON/CSV path with the
same new primary fingerprint; they are explicitly partial and do not replace
the earlier full-run receipts. Focused shared/codec/Text I/O regression: 284
passed; Ruff and mypy (151 source modules) passed. The 4,327-test full-suite result
above belongs to the preceding head, not this new field's exact-head CI.

For UNKNOWN diagnosis, a source-blind top-HUD pixel probe acquired the same
fixed first 180 seconds on all three sources: 180/180/185 exact native points,
each matched to prior full-run pixels, with one probe fingerprint. It records
HSV/contours and content-addressed native crops without a state claim. Centered
wide/tall red geometry gives 28/9/21 proposals, including 5/7/0 points with an
already readable timer. Visual diagnosis of the first proposals shows red world
backgrounds as well as a possible timer-replacement icon. Color/geometry alone
therefore is not adopted as ACTIVE or a spike event. The icon's semantic label
was pending at that stage; the later reply and separate weak-prototype
comparison are recorded below.
Candidate counts and UNKNOWN reduction are not recognition improvements.

## Exact display reply and bounded weak-shape follow-up

The human confirmed three exact display score/phase frames, including one
post-plant ACTIVE display. This adds two Round labels; the third re-confirms an
existing point and is not counted twice. The enlarged fixed cohort is Round
12 correct/0 wrong/1 abstained out of 13, life 12/12 and camera 12/12. Display
scores give 1 correct/2 abstained out of 3. All three score/phase-derived number
references remain abstentions; these references are not internal-counter GT.
No interval, precise event time, training, life/camera or Zone labels are added.

Three literal-header OCR variants on the same 180 native images each accepted
zero numbers at the fixed word threshold. They are not connected to the current
recognizer. A weak centered-shape centroid also fails to recover the reviewed
abstention and is rejected. The private three-prototype comparison retains
fixed 0.90 similarity / 0.04 competitor-gap gates and fits only automatic pixel
teachers. All 19 exact comparison references are excluded from fit. Source IDs
partition physical matches; they never enter the classifier.

Three fresh native prefixes of 180 seconds each, using one frozen primary
recognizer, completed at 180/180/185 points. Source before/after hashes, selected
native samples, output hashes and audit references were checked. Each run also
saves a same-native baseline and a fixed-grid comparison whose learned view and
shape parameters exclude the evaluated physical match. Main weights exclude A
and train on B/C. UI/feature design and method selection are known-DEVELOPMENT
exposed, so these parameter splits do not establish untouched generalization.

| Match | Reviewed Round | Baseline correct / wrong / abstained | Weak current-shape candidate | Life/camera correct retained |
|---|---:|---|---|---|
| A | 2 | 2 / 0 / 0 | 2 / 0 / 0 | 2 / 2 each |
| B | 8 | 8 / 0 / 0 | 8 / 0 / 0 | 3 / 3 each |
| C | 3 | 2 / 0 / 1 | 3 / 0 / 0 | 7 / 7 each |

The current-frame selected Round estimate recovers one reviewed abstention:
12/13 -> 13/13. The parameter-held-out comparison gives the same result; no
previously correct reviewed point is lost. This is one positive post-plant
display control, not a full-match false-ACTIVE or event-accuracy estimate.
The recovered estimate retains ACTIVE/UNKNOWN alternatives. In its one-second
bin other samples remain unresolved, so that bin still reports UNKNOWN. The
point label is not extended to a whole-second label. Number selection remains
unresolved and strict Fact/Event qualification remains absent.

Weak Round rows are isolated from all Rule calculations before a bounded
current-pixel projection. Native before/after life, camera, Map, continuity,
Round/self-view tokens and rule-generated transition/boundary evidence match
exactly in all three runs and their parameter-held-out controls. An initial
prototype leaked weak observation IDs into future-result evidence; its failed
executions are retained. The corrected separation and fresh native runs verify
that fix. All 13 untagged cached full-observation outputs also remain identical.
No weak cue creates a Round/spike/death/return event or authorizes current Map
ownership. This remains an optional, unadopted research supplier.

Final related shared/native/Text I/O regression at this stage: 303 passed;
Ruff and mypy (151 source modules) passed. New-head Linux/Windows/package-smoke
CI and new full-recording runs of this optional supplier are unverified. The
earlier complete full runs remain separate evidence rather than being relabeled
as this version's E2E result. The Goal remains open.

## Remaining failures and unavailable metrics

The original automatic baseline abstains on all seven available reviewed life points
and all seven available reviewed camera points across the three matches. Eight
older life/camera domain points lack exact native counterparts in its cadence
and are excluded, not counted as incorrect or negative. Compared with the older
source-bound route, six previously correct life/camera values on Match B are
lost in that archived baseline. The clock add-on alone does not recover them;
the completed composite stage above reports recovery on its enlarged fixed
cohort. HP is readable in a reviewed
spectator view, so positive view HP cannot independently establish recorder life.

The four known legacy Map-role selections remain lost in the shared path.
Raw marker pools are retained. Missing recorder/view/slot correspondence blocks
attribution; an observed candidate must not disappear merely because recorder
life is uncertain. The full-video route has not connected its Map reader, so it
has no full-match Map/Zone accuracy denominator. This limitation is not a
measurement of no markers or no movement.

An exact archived audit revalidates the original review packet/response hashes,
candidate IDs and previous predictions. All 140 Map observations and candidate
pools are unchanged. Each of the four reviewed self-marker objects remains in
its pool, and its initial selection index still agrees with the reviewed marker.
All four common consumers abstain at `external_self_or_round_support_incomplete`:
the old common Round, life, camera, recorder correspondence and semantic
continuity were UNKNOWN. Candidate preservation is not recovery of the four
correct role selections: correct 4 -> 0, abstained 0 -> 4. The separately reviewed
spike UI is blocked by a SPECTATOR context. The old initial selector requires a
Source/agent-supported appearance reference, so restoring that selector alone
would not establish source-independent recorder identity. No coordinate, Zone,
path or population Map-role accuracy is inferred from these exact-image roles.

There is no complete independent event inventory or internal boundary-time GT.
Correct/false/missed Round starts/ends, event precision/recall, boundary-time
error, population false death/SELF attribution and full-match Map-role accuracy
are therefore **unavailable**, not zero. Candidate starts/ends remain unqualified.
Independent Round-number validation, generic death/down/remote/revival handling,
Map routing and major-regression acceptance remain open. No formal Fact/Event
is produced.

## Validation and reproduction

The full composite stage's local suite passed 4,327 tests with 9 skipped. The
subsequent Round-number change passed 284 focused shared/codec/Text I/O tests,
Ruff src/tests and mypy on 151 source files. These supersede the earlier UTF-8
fixture inventory failure; historical results remain retained. Exact new-head
Linux/Windows/package-smoke CI is unverified.

The original 11,402 native-frame Round/life/camera/Map/continuity/token fields,
transitions and second rows are unchanged under the new optional view contract.
All three full-recording temporal-control prediction files reproduce byte-for-byte.

The API/CLI, intake and temporal-control commands are in
[development_full_match_timeline.md](development_full_match_timeline.md).
Private receipts bind the original full runs, frozen comparison plan, physical
splits, exact review equivalence, clock add-on, model reproduction and exposure
journal. Repeating experiments requires those admitted private assets and new
output directories. Adding a recording requires predeclared use/physical split,
registry acceptance, a pilot, the same observer configuration, then full processing
and per-match comparison. Keep old methods and rejected models for comparison.

The Goal remains open. Draft/main/Production/GT/fixed-window/protected-recording
boundaries and the hold on HUD/Map redistribution remain in effect.

## Verified full weak-Round comparison

The `a8887d8` runtime completed the three full DEVELOPMENT matches with one
primary recognizer: 6,203.949 recorded seconds, 9,537 native points and 6,206
second rows. The two completed acquisitions were retained; the interrupted
third acquisition was preserved and rerun into a new directory. All Source
before/after hashes, native audit references, output hashes and unchanged
runtime bindings were verified before scoring.

| Match | Native points / bins | Fixed Round baseline -> shape | Life / camera, both methods | UNKNOWN R/L/C after shape |
|---|---|---|---|---|
| A | 3164 / 2054 | 2/2 -> 2/2 | each 2/2 | 569 / 913 / 803 |
| B | 3650 / 2542 | 8/8 -> 8/8 | each 3/3 | 994 / 885 / 765 |
| C | 2723 / 1610 | 2 correct + 1 abstained / 3 -> 3/3 | each 7/7 | 620 / 592 / 491 |

Fixed-point Round agreement is 12/13 -> 13/13; per-match macro agreement is
88.9% -> 100%. Life/camera remain 12/12 each and reviewed correct losses are
zero in these domains. Map's four previously correct role selections remain
lost and are not included in that zero. Physical-match-excluded role/shape
parameter controls reproduce the fixed-point gain; whole-model independence
remains unestablished because UI/Profile and method selection were exposed.

Same-native Round UNKNOWN bins decrease 2,302 -> 2,183. That is coverage, not
119 new correct seconds. Life/camera/Map/continuity/token fields and transition
and boundary candidates, including evidence, are identical before/after the
new supplier. The reviewed timer-replacement native point gains an unqualified
ACTIVE/UNKNOWN alternative, while its common second remains UNKNOWN.

A separate sparse audit fixed each of two matches' lowest accepted shape-score
proposals before recovering images. Both were human-confirmed post-plant ACTIVE
versus baseline abstentions; one camera was confirmed SPECTATOR and matched.
These selected-candidate audits do not alter the fixed 13-point denominator or
establish population false-positive rates. A viewed player's death is not a new
recorder death. No interval, internal event-time, training or formal labels were
added.

The current forward/offline/bracket replay on identical full evidence scores
Round13/13, life12/12 and camera12/12 in all modes. Extra reviewed correct labels
from future context: zero. Unlabeled state revisions remain unscored. Current
full-run wall seconds are 1380.43/1334.31/1390.82; Python peaks are
607.95/731.95/568.83 MiB, excluding decoder/OCR children. Parallel jobs and the
rerun's partial overlap with tests prevent an isolated speed comparison.

The frozen full-acquisition source completed the local suite: 4,371 passed, 9 skipped,
85.72% coverage against the 75% gate. This supersedes the historical full-suite
count for local source validation; platform CI and packaged smoke remain
unverified. The later opt-in adapter has separate focused validation below.

Five additional already-registered DEVELOPMENT matches were fixed by metadata
before new pixel access. All five completed 60-second, audit-free acquisition
pilots with the same primary recognizer. Their prior training/review exposure
prevents untouched independent-evaluation claims. Protected and
UNKNOWN_EXPOSURE media remain excluded. Pilot coverage is not full-match or
recognition accuracy evidence. Independent event/Map/Zone metrics and the Goal
remain incomplete.

## Additional five-match report-overlay failure

The five acquisition pilots are not recognition success. Replaying nine existing
human-confirmed ALIVE/SELF native frames from those five matches made the HUD,
view and shape routes abstain on all nine in each domain. Every frame had a
visible combat report; eight already had an accepted SELF pixel hypothesis,
readable HP100 and current HUD support. The blanket report blocker discarded
the current view. The old human scope allows SELF_LIVE during purchase, but does
not turn the separate PURCHASE menu label into Round or life GT.

An opt-in shared `project_purchase_self_claim` adapter now retains a weak owner
claim only with current positive BUY evidence, accepted SELF/HP/HUD measurements,
the report as the sole blocker, no read owned-death relation and no conflicting
view/death cue. It preserves the report and parent producer constraints. The
shared engine owns all state and history; the observation remains unqualified
and cannot authorize current Map ownership or formal output.

On the same nine isolated native points, the candidate gives 3 correct/6
abstained versus 9 baseline abstentions in life and camera. A fixed native
+/-2-second context around every center (45 total native points) gives:

| Additional match | Parent life/camera | Current life/camera, each |
|---|---|---|
| D | 0 correct / 2 abstained | 1 correct / 1 abstained |
| E | 0 correct / 2 abstained | 1 correct / 1 abstained |
| F | 0 correct / 2 abstained | 1 correct / 1 abstained |
| G | 0 correct / 1 abstained | 0 correct / 1 abstained |
| H | 0 correct / 2 abstained | 2 correct / 0 abstained |

The current forward and offline methods both give 5 correct/4 abstained per
domain. The two extra correct points relative to isolated observations are not
an effect of future information alone. Only the original nine centers are GT;
neighbor frames are unlabeled. Match G is the worst with 0/1, not omitted from
an average. Sparse same-native replay is not a new full-match recognition run.

The original three-match fixed controls retain Round13/13, life12/12 and
camera12/12 under the new proposal. No previous reviewed correct value is lost.
Unqualified death/return candidate counts are unchanged in those cached full
replays; population event accuracy is still unavailable. The remaining four
additional controls abstain; broader report handling, actor identity, REMOTE,
revival, Map roles and independent generalization remain unresolved. This
known-DEVELOPMENT rule design is an experimental candidate, not Production
adoption. Model weights and existing GT/splits are unchanged.

The frozen `a8887d8` full source passed 4,371 tests/9 skips at 85.72% coverage.
After adding the opt-in adapter, 659 focused shared/native/Text I/O tests,
Ruff src/tests, mypy152 and the classified Text I/O gate pass. Current-head full
platform CI and packaged smoke remain unverified; historical full-suite results
must not be described as new-head CI.

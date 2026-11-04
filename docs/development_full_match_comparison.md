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
open: Round numbers, full Map/Zone processing, independent event/REMOTE/negative
coverage and unseen generalization are incomplete.

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
Round-number candidates, generic death/down/remote/revival handling, Map routing
and major-regression acceptance remain open. No formal Fact/Event is produced.

## Validation and reproduction

Final full local suite: 4,327 passed and 9 skipped. Ruff src/tests, mypy on 151
source files and the Text I/O audit passed. This supersedes the earlier local
suite's UTF-8 fixture inventory failure; that earlier result remains historical.
Exact new-head Linux/Windows/package-smoke CI is unverified.

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

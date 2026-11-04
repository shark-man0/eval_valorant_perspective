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
has identical JSON values with key-order-only differences. This experiment is
not integrated into timeline camera/life inference and is unadopted. Only one
reviewed SPECTATOR point is a negative for SELF; REMOTE and full negative episodes
are unmeasured. Classifier point counts cannot establish safe recorder attribution.

## Remaining failures and unavailable metrics

The full automatic route abstains on all seven available reviewed life points
and all seven available reviewed camera points across the three matches. Eight
older life/camera domain points lack exact native counterparts in its cadence
and are excluded, not counted as incorrect or negative. Compared with the older
source-bound route, six previously correct life/camera values on Match B are
lost. The clock add-on does not recover them. HP is readable in a reviewed
spectator view, so positive view HP cannot independently establish recorder life.

The four known legacy Map-role selections remain lost in the shared path.
Raw marker pools are retained. Missing recorder/view/slot correspondence blocks
attribution; an observed candidate must not disappear merely because recorder
life is uncertain. The full-video route has not connected its Map reader, so it
has no full-match Map/Zone accuracy denominator. This limitation is not a
measurement of no markers or no movement.

There is no complete independent event inventory or internal boundary-time GT.
Correct/false/missed Round starts/ends, event precision/recall, boundary-time
error, population false death/SELF attribution and full-match Map-role accuracy
are therefore **unavailable**, not zero. Candidate starts/ends remain unqualified.
Round-number candidates, generic death/down/remote/revival handling, Map routing
and major-regression acceptance remain open. No formal Fact/Event is produced.

## Validation and reproduction

Related shared/timer/geometry/Text I/O tests: 251 passed. Ruff src/tests and mypy
on 151 source files passed. An earlier full local suite reported 4,274 passed,
9 skipped and one Text I/O inventory failure in new fixtures; explicit UTF-8
fixes passed the related audit. A fresh all-green full suite or new-head
Linux/Windows/package-smoke CI is not claimed.

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

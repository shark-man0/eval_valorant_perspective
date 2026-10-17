# Self Death image recognizer: development and independent-source result

## Scope and integration

Starting main: `7e480c2f2f7f49aea73e1541d065d78881d2f11c`.
Branch foundation: PR #52 (`ffdf41f`) plus PR #50's `d81f238`, merged as
`b45d1308a4ab6182a750ce9f439cffa86bf28f7e`. This separate branch preserves
PRs #44, #46, #47 and #50/#52. It does not change the production HUD, Event,
Snapshot, Package, Trace, evaluator, GT, sampling or qualification contracts.

The new experimental recognizer actually reads current pixels and executes a
temporal state machine. It remains non-releasing: `qualified` is false and
`formal_events` is empty. These predictions cannot establish HUD identity,
HP, weapon, ammo, Alive, ownership of visual facts, or a formal Death event.
The overall S-01 goal is **not complete** and no Strict FAIL reduction is claimed.

## Image evidence

The human source review confirms that the killfeed yellow portrait outline
identifies the recording player. This explains why a Scoreboard-only path
cannot identify the player when the Scoreboard is closed. Human confirmation
of UI semantics does not qualify the automatic image reader.

`experimental/killfeed_subject.py` searches for this outline using three
disjoint, contrasting structural masks, each requiring NCC >= 0.90. It also
requires >= 0.90 yellow support. The feature is the binary yellow outline,
not the portrait, player name, numeric values or world luminance. A mirrored
outline can be searched. An independently matched weapon separator on the
same row determines the highlighted subject's killer/victim side; ambiguous
or absent separators retain unknown. Names are OCRed from the measured gap;
partial or low-confidence names remain unknown without deleting the separate
structural observation. Names and diagnostic times are never runtime constants.

`experimental/self_death_image.py` separately reads the self-referential report
prefix at NCC >= 0.90. It requires observed fresh report and self-victim edges
in the same source segment, followed by distinct native frames spanning at
least 0.05 seconds. A victim reader dropout restarts the entire corroboration
run within the original one-second onset expiry. It does not erase the earlier
independent report edge or lower a threshold. A report dropout,
invalid binding, PTS gap/reordering, repeated pixel raster or changed
source context prevents confirmation. Only a genuine producer-qualified new
round may rearm a completed episode. Report toggling cannot rearm it.

The prediction retains report onset separately from confirmation time and the
supporting source bindings. It does not claim that report onset is already a
qualified Death timestamp. Source SHA, rational PTS, pixel hash, source segment,
code/profile/dependency fingerprints and conservative measured support survive.

## Measured development regression

All `match_001` positives below are previously exposed development episodes,
not blind holdout. Ninety-six lossless native input frames were verified by
encoded and pixel hashes. Reusing decoded images does not reuse recognition:
every variant recomputed its image readings and temporal state with its own
code/profile fingerprint. Source and dependency terminal hashes passed.

| Variant | R1 prediction | R2 prediction | Persistent-report control | Spectator/report control |
| --- | ---: | ---: | ---: | ---: |
| Grayscale outline context | 0 | 1 | 0 | 0 |
| Binary outline, original candidate consumption | 0 | 1 | 0 | 0 |
| Binary outline, complete corroboration restart | 1 | 1 | 0 | 0 |

Input counts are respectively 24, 48, 12 and 12 native frames. The final image
recognition run took **88.56 seconds**. Final conservative supports were
0.94080 and 0.93921. These are two episode predictions, not hundreds of
independent successes, formal events or canonical assertion passes. Only the
stated short control intervals were tested; full-match false-positive rate
and delayed duplicate suppression are not established by those controls.

Two concrete defects were reproduced. Grayscale exterior context made outline
matching depend on world luminance. Binary outline geometry removes that
dependency without lowering NCC. Separately, a single early victim witness
consumed the upstream candidate latch before sustained corroboration, so later
valid witnesses could never confirm R1. Retaining the original report candidate
while restarting the full confirmation run resolves that development failure.

## Frozen independent-source test

The existing local `match_002` video was located and verified against registered
SHA `55d909c2d6a5f38575d1cb6c249ddfa7e2a48b96535841317adcae704c6f63b6`:
2214.272 seconds, 1920x1080, 60 fps and three audio streams. No GT, assertion,
expected name or timestamp was used for recognition or interval selection.
Code and training references were frozen before decoding this source.

A **discovery-only** keyframe scan found the trained report prefix in 561 of
2245 keyframes. It took 267.72 seconds, peak Python RSS 61,644 KiB and decoder
RSS 80,396 KiB. This scan cannot certify absence, event counts, native onset,
recall or continuity. It does not change any E2E sampler.

The first header-positive run selected one bounded native window by a frozen
source-order rule. All 91 native frames were decoded and hash verified, with
150,636,777 encoded bytes and a measured cache-generation time of 361.62
seconds. Source images were reviewed before reading classifier predictions:
the sequence contains a self-killer predecessor, then one self-victim/collapse
episode with a fresh self-referential report. Persistent report is not a new
episode. Exact Death onset is not yet independently annotated.

| Independent first episode | Result |
| --- | ---: |
| Manually observed self-death episodes | 1 |
| Frozen recognizer predictions | 0 |
| Formal Death events | 0 |
| Frames with report NCC >= 0.90 | 78 / 91 |
| Frames with outline proposals | 91 / 91 |
| Outline proposals with unknown separator/role | 314 |
| Recognizer wall time, excluding outer source checks | 141.00 s |

**This is a false negative at episode level, not qualification success.** The
single trained weapon glyph does not establish the separator for the different
weapon in this episode. Multiple outline proposals also require independent
specificity review; 314 proposals are not 314 correct subject identifications.
No threshold, reference or recognizer was tuned to make this test pass. Future
development using these images must mark this first episode as exposed; it
cannot be reused as fresh blind holdout. Other untouched episodes require a
new frozen partition before further development.

### Follow-up development and reserved native episode

The results above belong to commit `a587560` and its frozen private inputs.
They are not re-signed for subsequent source changes. That commit's Linux CI
run 38851424124 and Windows CI run 38851423766 passed, including coverage >=75%,
Ruff, mypy and the Windows packaged application smoke test. Text I/O checks also
passed. Those CI results do not certify the later changes or real-image accuracy.

The experimental profile now optionally accepts additional weapon references;
default callers retain their previous configuration. Multiple templates matching
the same physical glyph are deduplicated and contribute one measured support,
never an increased confidence or extra independent witness. Distinct competing
separators still produce unknown. Existing public Schemas are unchanged.

A second temporal fix prevents an older self-killer row from vetoing a fresh
self-victim row elsewhere in the feed. A recording player can eliminate an
opponent and then die while that earlier row persists. Killer-only input still
cannot generate a Death prediction; a separate fresh victim edge and report
onset with complete corroboration remain necessary. A synthetic two-row
regression exercises that distinction.

The first match_002 episode is now explicitly development data. A private
source-bound outline profile and extra weapon reference constructed there
produce one development prediction, measured support 0.91930, in 157.57 seconds.
No source labels, names, GT or expected timestamps enter runtime. This is not
an independent success and does not erase the earlier false negative.

Before using any later full frames, the code/reference inputs and a native
second-half interval were frozen. Header crops from that interval had already
been used for discovery, which is documented exposure; this is a held-out
native episode test, not a blind full-match recall benchmark. Source image
review before reading classifier predictions established one self-death,
followed by persistent report/map overlay and a teammate spectator transition.
No exact Death time label was injected.

| Reserved native episode | Result |
| --- | ---: |
| All native frames decoded and evaluated | 241 |
| Manually observed self-death episodes | 1 |
| Predictions / formal events | 0 / 0 |
| Frames with report support >=0.90 | 199 |
| Accepted subject outline proposals | 0 |
| Encoded input bytes | 399,669,910 |
| Cache generation time | 468.16 s |
| Recognizer time excluding outer source checks | 259.95 s |

This test fails **before weapon/role corroboration**: the frozen outline profile
does not transfer to that episode. The first independent test also exhibited
unqualified, potentially spurious outline proposals; specificity and sensitivity
both need qualification. No threshold was lowered and no reference was adjusted
to pass this reserved result. Both frozen failures remain local, with verified
terminal hashes. Formal subject qualification and Strict E2E improvement are
still unachieved. Another profile variant cannot inherit the earlier CI or
recognition results without rerunning the applicable checks.

Follow-up local regression: **162 passed in 8.62 seconds** (36 image/temporal
controls); full configured Ruff scope passed and mypy passed all 141 source
files. Follow-up remote results must be checked at the corresponding PR head.

Two discovery attempts terminated with OOM at final source hashing: the private
script incorrectly read the 3.4 GB video into one bytes object. Kernel logs
confirmed approximately 3 GB Python RSS. Streaming hash verification corrected
the diagnostic; the successful run retained terminal integrity checks. This
was not a recognizer or production decoder change.

## Tests and release gates

Initial local unit regression: **159 passed**, including **33** new image and
temporal controls. Controls exercise own-killer rejection, no separator,
partial names and invalid confidence, world luminance independence, initial
persistent report, interrupted corroboration, report reappearance, source
changes, PTS gaps and duplicate suppression. They are synthetic safety tests,
not real-video precision measurements. Ruff passed for new files; mypy passed
the eight experimental modules. Remote CI results are recorded separately once
available; no Linux/Windows or packaged-smoke result is inferred from local tests.

Adopted canonical Full remains **23 PASS / 55 FAIL / 4 NE**. The archived
unadopted candidate remains **28 / 50 / 4**; the different timing-policy comparison
remains **30 / 49 / 3**. Current targeted/sampled/full canonical results for this
new recognizer are **not measured**. No canonical PASS delta or whole-suite
negative/discontinuity delta is claimed. No new Full was run because independent
positive subject/role qualification has not passed.

## Next implementation

Complete current-image separator/role recognition across weapons and audit
outline specificity, using an explicitly exposed development partition.
Freeze the resulting reader before evaluating untouched episodes and genuine
own-killer, nonself-victim, partial-text, report-reopen, spectator and respawn
controls. Then qualify temporal Death onset and duplicate suppression across
longer continuous source windows. Only after independent qualification should
the separate subject producer connect to formal Event/Package/Trace. Public
event identity/schema adoption must retain the approved compatibility and
review process. Snapshot transport improvements alone do not satisfy these gates.

Private pixels, player text, timestamps, GT, profiles and qualification assets
remain outside Git. Detailed source-bound JSON and failure records are retained
locally under the ignored investigation directory.

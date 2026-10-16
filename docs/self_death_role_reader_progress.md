# Self Death role reader: first unused-native episode success

This continues PR #53. Starting main is
`7e480c2f2f7f49aea73e1541d065d78881d2f11c`; the previous branch head is
`cc3fa0453f00aa1a733ad0011ea3d3e378803892`. The previous turn made concrete
implementation and source-measurement progress. This is another partial
milestone, **not completed qualification, production adoption or Strict E2E
improvement**. Production HUD ownership and formal Event release stay unchanged.

## Causes reproduced

The full-outline reference does not transfer reliably. A source diagnostic on
a failed episode measured top/middle/bottom NCC 0.664/0.975/0.726. The exterior
chevron was recognizable while thin horizontal strokes were affected by
antialiasing and background. A three-pixel filtered feature was implemented,
tested and independently rejected: a new 181-frame interval produced no subject
proposals, even though the report appeared on 94 frames. That feature was
removed; its exact source bytes were retained privately and checked against the
failed run's recorded hash. No failed run was overwritten or re-signed.

Three nonoverlapping exterior-tag supports, excluding portrait/name/numeric
pixels and fragile horizontal strokes, then detected the source-player tag on
32 frames of a different unused episode. The single trained weapon glyph still
could not establish killer/victim roles. Merely extending the template bank
does not solve weapon coverage.

An experimental connected-white-pictogram path identified victim roles on 17
frames and accepted names on all 17, but still produced no episode prediction.
Diagnosis found two distinct causes: the killer's white portrait/hat could also
pass isolated shape checks, and warm scenery contaminated the permissive yellow
shape feature. Victim witnesses became available only after the original onset
expired. The one-second expiry and full native corroboration were not relaxed.

## Opt-in experimental changes

The default `template_ncc` path retains its previous configuration and gates.
The new `white_glyph_geometry` option measures a connected white pictogram with
explicit size, aspect, density and scanline constraints, plus a consistent red
or green team plate immediately above and below it. A portrait's white hat or
hair does not qualify just because it is a wide white component. Multiple
distinct separators remain ambiguous. Geometry retains its ROI, pixel counts,
area, scanline support and plate measurements; **it is not assigned a fabricated
NCC or confidence of one**. Its classification is still unqualified.

A separate explicit `hsv_strong_yellow_outline_v1` shape option uses the stronger
S>=90/V>=200 criterion already frozen for training color-core construction.
The original feature uses S>=60/V>=150. This is a new, stricter, fingerprinted
feature, not transferred qualification or a lowered acceptance gate. Hue bounds,
NCC >=0.90 on each of three disjoint supports, measured color support >=0.90,
OCR >=0.90, source guards, onset expiry and native corroboration remain intact.
Training rejected a support with zero contrast rather than forcing a profile
through validation. The valid profile's supports contain 96/94/94 pixels; its
color witness contains 50 consistently observed pixels.

Names are cropped from the measured separator-to-portrait gap. A fingerprinted
source-calibrated inset prevents the portrait border from contaminating OCR.
One training-source diagnostic changed raw OCR support from 0.55309 with edge
ink to 0.92281 without it, without changing OCR code or its acceptance gate.
No expected name, GT, timestamp or Round number is supplied to the reader.

These features belong to the separate experimental subject route. They do not
change live HUD identity, view ownership, HP, weapon, ammo, Alive/dead snapshots,
legacy Death guards, qualification packs, public Schemas or assertion semantics.
Image predictions still report `qualified=False` and `formal_events=[]`.

## Source partition and measurements

All reference pixels for the new profile come from the same 51 frames in the
first, explicitly exposed `match_002` development episode. Failed later episodes
remain failed records, never become fresh holdout, and are not copied into the
reference. Their diagnostics inform the documented failure analysis. Code and
profile inputs are frozen before each new native source interval is decoded.

Previously performed report-only keyframe discovery is disclosed exposure. It
selects intervals independently of GT, but a discovery-selected source test is
not a blind full-match recall benchmark. Full native frames and semantic roles
in each selected test were previously unused; source roles were reviewed before
reading predictions. Native replays evaluate every frame without changing Full
E2E sampling. Exact native PTS, encoded/pixel hashes, source segment and actual
code/profile/dependency fingerprints are retained. Terminal hashes passed.

| Configuration / scope | Frames | Episode predictions | Additional evidence |
| --- | ---: | ---: | --- |
| Exterior tag + template separator, unused episode | 181 | 0 | 32 tag observations, role unknown |
| Exterior tag + shape-only glyph, next unused episode | 181 | 0 | 17 victim readings, portrait ambiguity and late witnesses |
| Plate-bound glyph + strong tag, exposed development | 91 | 1 | 74 victim readings, 51 accepted names |
| Same frozen plate-bound/strong reader, next unused episode | 181 | **1** | 47 victim readings, 12 accepted names |

The last test's source review identifies one self-death and a preceding nonself
victim entry. The recording-player tag is on the victim; the other Omen is the
killer without that tag. The report, collapse and later persistent report are
consistent with one episode. The prediction retains the original report onset;
confirmation follows 0.100 seconds later. Minimum measured visual support is
0.93612. A **post-run**, source-backed exact text audit found 12/12 accepted name
readings match the visible source text, zero other accepted strings. This is not
claimed as blind text-label qualification. No actual name is published here.

The last native replay took **234.44 seconds**, excluding outer source checks.
Its immutable decoded input cache contains 363,791,854 bytes; generation took
402.29 seconds. Acquisition used bounded RAM temporary storage, with a
550,000,000-byte PNG budget, then copied hash-verified immutable inputs to disk.
All source hashes use streaming reads; no multi-gigabyte bytes allocation is
used. Actual reader peak RSS is not yet measured. Earlier discovery resource
measurements are not substituted for reader memory measurements.

The unused-episode success is meaningful positive recognition progress. It does
not establish long-duration duplicate suppression, report reopening/respawn,
spectator safety, all weapons, all agents, whole-match false-positive rate or
formal event timing. Earlier failures are part of the record, not hidden by the
one successful episode. Synthetic controls and this one real episode cannot
stand in for the remaining independent negative suite.

## Tests and remaining release gates

Current local regression: **174 passed in 9.57 seconds**, including 48 image and
temporal controls. Configured Ruff passed; mypy passed all 141 source files.
Controls include both marker sides, text/line/block/color/portrait-context
rejection, multiple glyph ambiguity, source changes, defaults/fingerprints,
warm background exclusion, partial/invalid name confidence, temporal restart,
initial persistent report and duplicate suppression. Source profile/feature
changes require their own qualification despite green tests.

Remote CI for `cc3fa04` passed on Linux and Windows, including packaged smoke;
that result does not automatically cover the new source changes. New PR-head
results must be checked separately.

Next: frozen source-negative windows for persistent/reopened report and spectator
or respawn context, plus current-code regression on `match_001`. Complete the
subject/role/temporal qualification evidence before constructing formal events.
The typed subject contract requires separate subject, victim and transition
witnesses; a diagnostic prediction alone does not fulfill it. Public event
identity/schema adoption still follows the approved compatibility review.

The unchanged canonical assertion inspection also confirms that the two point
Death predicates require victim name, killer agent and received damage. Even a
qualified Death without these attributes cannot pass those predicates. The two
per-Round Death count predicates are separate, conditional improvement targets;
correct native Round association is also required. Missing killer/damage fields
will remain missing rather than borrowing values from GT.

Adopted Full remains **23/55/4**, archived unadopted Strict candidate **28/50/4**,
and the distinct timing-policy comparison **30/49/3**. Current canonical targeted,
sampled and Full results for this reader are **not measured**; no Strict delta
is claimed. No new Full was run because qualification and formal producer wiring
are incomplete. Detailed private pixels, names, timestamp labels, profiles,
failure records and manifests remain outside Git.

## Shared replay and exposure audit follow-up

The common `scripts/diagnostics/replay_self_death_images.py` runner recomputes
image recognition from verified lossless decoded inputs. It separates the
runtime fingerprint from dataset hashes, rejects unexpected profile keys
(including expected labels), verifies every encoded/pixel binding, resets at
each independent window and checks terminal source/dependency/input hashes.
Positive and negative windows use the same executable fingerprint. Cached
recognition outputs are not accepted as decoded inputs. Peak RSS covers the
Python process, not child decoder/OCR processes.

The original source-2 frozen profile produced one diagnostic prediction in its
positive window and zero in two report-persistence/spectator/preparation
controls: 315 frames, 274.51 seconds of recognition, 430.65 seconds wall time,
about 95 MiB Python peak RSS. No frame was blocked by source validation. These
are bounded diagnostic results, not whole-match precision or qualification.

That profile initially found no marker on source 1. A shared exterior mask was
then derived from the existing source-2 development images and eight previously
exposed source-1 images. Those images are training inputs. Reference values,
NCC 0.90 and the independent color/geometry requirements remain unchanged.
The shared profile found one source-1 R2 prediction in the 96-frame regression
set; the shorter R1 window did not provide sufficient continuous corroboration.
An extended 75-frame R1 replay produced one prediction, preserving the observed
onset despite confirmation 0.400 seconds later. The extended replay took 76.14
seconds recognition / 83.10 seconds wall time, about 95 MiB Python peak RSS.
Both source-1 report/spectator controls retained zero predictions. These exposed
development/regression results do not independently qualify the changed mask.
Formal events remain zero; canonical targeted/sampled/Full deltas are unmeasured.

The one-second candidate horizon now compares rational source PTS directly.
Converting an onset through a decimal float could incorrectly expire the exact
one-second endpoint. Tests accept that endpoint and reject the next native
frame; neither the horizon nor the confirmation-duration threshold is widened.

The user supplied `codex/round-boundary-requalification` as the exposure-ledger
reference. Read-only inspection at `e9e9e15aa54b0d4792a27869d8c8447a4e0e4bfc`
verified all six recorded file hashes in
`e2e_reports/match_001/exposure_inventory_20261016/summary.json`. Its 4,518 records
cover two supplemental sources, **not match_002**. The README and summary
explicitly state that match_002 image exposure was not assessed and unlisted
frames are not certified unviewed. Consequently no prospective match_002 window
is declared a new blind holdout from absence in this ledger. PR #42 was not
modified. Complete event-level exposure verification remains a release gate.

Local follow-up: 152 relevant unit/integration tests passed in 17.75 seconds;
Ruff passed for the CI scope (`src tests scripts/e2e`) plus the new runner;
mypy passed 142 files including the runner. A broader `ruff check .` also scans
legacy/private validation and configuration scripts and reports existing
out-of-scope errors; those files were not changed. Remote checks for `14894b8`
passed Linux and Windows push CI. Its Windows PR job failed before testing
because the Chocolatey FFmpeg download returned HTTP 503; this is not a Windows
PR-test pass. These remote results do not certify subsequent local changes.

Remaining work is independent subject/role/transition qualification, followed
by the approved formal producer connection and same-contract canonical
evaluation. Positive diagnostic predictions are not substituted for these
steps. No new Full E2E was run.

## Prospective shared-mask episode: positive not detected

After freezing the shared mask and runtime, another source-2 episode was decoded
without changing any recognizer input. Before inspecting predictions, six native
source images were reviewed: a live first-person view takes damage, collapses,
acquires a new red killfeed row with the highlighted recording player on the
victim side and opens the self-referential report. The scoreboard appears later.
This establishes one positive episode, independently of the reader output. It
does not certify global historical exposure or an exact event timestamp.

The same-code run processed that 151-frame window and the two existing negative
windows (134 frames). Result: **0/1 positive episodes predicted**, zero predictions
in both controls, zero source-blocked frames and zero formal events. In the
positive window the report matched on 97 frames and 94 highlighted-marker
candidates were retained, but every role remained unknown with
`weapon_separator_unavailable`. The actual pistol silhouette measures 28 by 20
pixels (aspect 1.4); the frozen wide-glyph detector requires width at least 32
and aspect at least 2. The failure is therefore a supported-icon coverage gap,
not evidence that the yellow-marker or report reader never sees the scene.
The victim-name area also has a performance overlay, so successful name OCR
must not be assumed from marker presence.

The 285-frame recognition took 230.36 seconds, 381.37 seconds including all
outer checks, with 99,803,136 bytes Python peak RSS. Terminal source, input and
dependency hashes passed. The newly decoded cache used 259,905,413 bytes and
took 376.62 seconds to acquire; acquisition is separate from reader execution.
No recognition output was reused as a new-code result.

The failed validation episode remains excluded from fitting. Broadening the
existing glyph bounds until this image passes is not the chosen remedy. The
next role-reader implementation needs separately trained compact-icon evidence
or an independently validated row-structure witness, plus event-level tests
that include recorder-as-killer and nonself victims. The two bounded controls
are useful regressions, not complete long-duration false-positive qualification.
Current canonical targeted/sampled/Full results remain unmeasured; no PASS gain
or formal adoption is claimed. Linux PR and push CI for `e1907aa` passed;
Windows PR run `38896852236` also finished successfully, including its
test-and-build job. These remote results cover the source changes at `e1907aa`.
The source owner subsequently reported that no additional match_002 exposure
ledger is likely available. Historical exposure therefore remains unknown;
prospective validation may establish separation from this implementation's
fitting inputs, but cannot certify globally unseen images.

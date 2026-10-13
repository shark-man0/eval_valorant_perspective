# Source-preserved combat report numeric observations

## Problem and target assertions

`GT-R1-DEATH`, `GT-R2-DEATH` and their player-death count assertions need a
qualified semantic producer as well as ownership and lifecycle association.
The existing numeric-fields reader converts source text to integers and loses
its original display/per-field evidence. R2's actual report visibly supplies a
damage value, but cannot yet authorize a self-death event.

## Change and contract

Reuse the existing profile `kind: fields` on ROI `combat_report`. An explicit
configuration can now retain `damage_received` / `damage_given` source readings
through the common `RealHudAnalyzer`. No default profile or OCR executable was
changed. Existing `NumericFieldsReader.read` behavior stays unchanged; its
new source-preserving method returns each reliable field independently.

The additive optional HUD Observation v2 field is `combat_report_readings`:

```json
{
  "status": "candidate",
  "reader": "combat_report",
  "source_pts_sec": 147.68600260416667,
  "source_pixel_sha256": "<decoded full-frame SHA256>",
  "profile_fingerprint": "<profile and layout fingerprint>",
  "fields": {
    "damage_received": {
      "display": "194",
      "value": 194,
      "confidence": 0.95,
      "sources": ["tesseract_digits"],
      "cross_checked": false,
      "roi_bounds_norm": [0.80, 0.51, 0.95, 0.58]
    }
  }
}
```

The example confidence and ROI are illustrative; actual measurements are in the
linked report. The original display is retained, including leading zeros;
integers are parsed from that display rather than used to reconstruct text.
Confidence must be finite and at least 0.90, sources must be present and numeric
text must contain ASCII digits. A weak/absent field is independently omitted.
The observation's geometry must be accepted and its current frame must carry
report presence. Nothing is carried to later frames without a new observation.

`candidate` is the only supported status. This is neither qualified damage nor
player-owned damage. It cannot create death events, self-dead ownership,
confirmed snapshots, deterministic player facts or AI scores. The canonical
trace adapter does not export it as `combat_report_damage_received`. JSON
schema, native model and persisted-observation validation reject a promoted
status, stale PTS, display/value disagreement, invalid bounds, missing source
proof or an added ownership claim. A missing profile fingerprint remains null,
so injected-reader diagnostics do not pretend to be profile-qualified.

## Existing OCR feasibility

An isolated, explicitly invoked local Tesseract 5.3.4 runtime exercised the
existing common OCR adapters. It was extracted under `outputs`, not installed
system-wide or added to PATH. The initial eight source-reviewed development
frames and three ROIs were fixed before predictions. Models were not fitted or
selected using Validation Pack expected values. This is a feasibility cohort,
not independent holdout or reader qualification.

| Field | Exact source-text matches | Unknown | Exact display mismatches | Negative rejected |
| --- | ---: | ---: | ---: | ---: |
| Received damage | 6 | 0 | 0 | 2 |
| Killer-agent raw Japanese text | 0 | 0 | 6 | 2 |
| Complete victim-name text | 0 | 3 | 0 | 2 |

Three animated, incomplete victim-name inputs remain unscored. The Japanese
reader returned `フェ イド`, including an OCR word separator, rather than the
source label `フェイド`. The six mismatches measure exact display agreement;
they do not prove six wrong semantic-agent classifications. No semantic-agent
classifier or alias normalization was adopted. The victim name has extra
punctuation and confidence below 0.90 and is rejected. No threshold was lowered.

## Actual shared-producer verification

The opt-in diagnostic profile reuses existing score/timer/identity settings and
adds only a received-damage field within the configured combat-report ROI.
The analyzer processes the same eight unmodified source PNGs, preceded by the
exact-source initial calibration frame. All source images were previously
SHA-bound; current encoded/pixel hashes and terminal video SHA were verified.
Reader executable and English/Japanese model hashes match the frozen runtime
snapshot. This isolated input is not continuous temporal validation.

| Metric | Previous | Current | Delta |
| --- | ---: | ---: | ---: |
| Source-preserved numeric candidates in the eight inputs | 0 | 6 | +6 |
| Correct damage displays in the six reviewed positive inputs | Not measured | 6 | — |
| Wrong damage displays / negative accepts | Not measured | 0 / 0 | — |
| Owned-player readings | 0 | 0 | 0 |
| Formal death events | 0 | 0 | 0 |
| Canonical PASS / FAIL / NE | 23 / 55 / 4 | Not re-evaluated | — |

Runtime was 14.371 seconds for nine inputs. All eight target states stay
unknown; candidate provenance binds current PTS, decoded pixels and the actual
profile/layout fingerprint. HUD/ownership confidence is not increased. These
selected correct displays cannot establish general recognition accuracy.

## Tests and cache safety

- New meaningful tests: 23; source displays, independent missing fields,
  confidence/source rejection, native/persisted validation, current-frame-only
  analyzer behavior, unknown identity and absence of fake trace death fields.
- Related tests: 59 PASS.
- Full regression: 2626 PASS, 7 SKIP, 1838.23 seconds. One skip resulted from an
  incorrect validation-pack environment-variable name in that invocation.
  `VALORANT_E2E_VALIDATION_PACK` was then set correctly and the affected trace
  test module passed all 9 tests without a skip. The other six remain optional
  source/Tesseract/Windows/PowerShell prerequisites.
- Ruff (`src tests scripts/e2e`) and mypy (128 source files): PASS.
- Old whole-native recognition archive: rejected by the existing code-binding
  guard after the HUD changes. Physical image reuse does not authorize stale
  recognition-result reuse. Previous whole-video Practical results remain
  historical evidence for their recorded code fingerprint.

No full canonical E2E was justified: the candidate is not a qualified death
producer, victim identity is unreadable, ownership is unknown and Strict round
qualification remains absent. No assertion, threshold, sampler or safety policy
was changed. Windows CI covers the common contracts; actual Windows OCR/media
runtime remains unverified until a source-backed run is performed there.

## Remaining implementation

Next acquire source-qualified victim-name and agent-name evidence while
preserving raw OCR text, then design their safe relationship to ownership and
current report presence. Qualification requires disjoint held-out/negative
inputs; these development frames are ineligible for later independent holdout.
Do not set `death_source_confidence` or copy candidate numeric fields into event
attributes until those requirements hold. R1/R2 round association remains a
separate blocker. No canonical PASS gain is claimed.

Artifacts: `e2e_reports/match_001/death_existing_ocr_feasibility.json` and
`e2e_reports/match_001/death_report_candidate_source_verification.json`.
The diagnostic-only profile, runtime and PNGs remain Pi-local under `outputs`.


## Windows CI probe follow-up

At `4a4a909`, both Linux checks and one Windows check passed, but the other
Windows check failed two pre-existing native-source tests. Its generic probe
coverage error did not include the probed timestamps, so its precise root cause
is unproven. Decoder auto-thread behavior is a hypothesis, not a confirmed
explanation. The report-reading tests were not the failing tests.

Both native PNG and raw replay paths now pass `-threads 1` to ffprobe, matching
their already single-threaded FFmpeg decode. Native failures additionally retain
probe count, first/last ticks, time base, requested window and first non-monotonic
pair. All original coverage, strict ordering, source SHA and pixel checks remain;
no timestamp sorting, dropping, repair or retry-to-accept was introduced.

The final related native tests pass 46 cases in 30.62s, including normal/budgeted
complete coverage, probe option checks for PNG/replay and duplicate-PTS rejection.
Ruff/mypy pass. Source verification decodes 31 real native frames across the
initial 0–0.1s and R2 147.60–148.04s windows; every PTS and pixel hash matches the
previous physical archive. This verification takes 34.786s and does not reuse
old recognizer predictions. The initial explicit 40MiB PNG disk budget was too
small; the diagnostic was rerun with 256MiB without changing inputs or acceptance.

The earlier full regression (2626 PASS) predates this probe-only follow-up;
the 46 native tests validate the final follow-up locally. Final common full
regression/Windows packaging evidence is the latest PR CI result. Actual Windows
match_001 accuracy and the original intermittent probe root remain unverified.
Source evidence: `e2e_reports/match_001/native_probe_decoder_alignment.json`.


## Qt media-test teardown follow-up

The `01ce952` Windows checks both passed. One Linux check also passed; the
other passed all 2630 tests and then exited 134 during finalization. Its stderr
contains `QObject: shared QObject was deleted directly` followed by an allocator
corruption diagnostic. This is an unsuccessful CI process despite passing test
assertions, and is not reported as a green check.

The real multitrack media test previously left its unparented video sink bound
to the player and relied on Python GC for both objects. Its teardown now runs
in `finally`: the sink is parented to the player, playback stops, the sink and
source are detached, and deferred deletion is processed while QApplication
is alive. All actual track-selection/playback assertions are preserved. This
corrects an observed lifecycle gap; it does not establish the exclusive cause
of the previous intermittent shutdown abort. Production UI/recognition behavior
is unchanged by this test-only follow-up. Relevant real FFmpeg/Qt/widget tests
passed with normal process exit; latest cross-platform checks remain the final
authoritative CI evidence.


## Physical-origin probe correction

At `c062eba`, Linux checks both passed and one Windows check passed, but the
other Windows check rejected a probe with **zero frames** for window `(0.2, EOF)`
and time base `1/15360`. There was no non-monotonic pair. This rules out treating
single-thread probe configuration alone as a sufficient correction. The new
reason output made the empty-probe failure observable.

The prior interval `0.0%` explicitly asks ffprobe to seek to timestamp zero,
including for a video whose physical first PTS is positive. The origin-covering
probe now leaves the interval start empty; positive interior probe offsets are
retained. This reads from the physical origin without a needless pre-origin
seek. The distinction follows the [official ffprobe interval contract](https://ffmpeg.org/ffprobe.html#Main-options).
No empty result is accepted, no retry substitutes a different timestamp, and
all existing decoded-versus-probed coverage and monotonicity checks still run.

Three new regression cases model the observed empty result when a zero seek
is requested on a nonzero-origin file. Origin/EOF, interior/EOF and bounded
windows now preserve every real fixture PTS using one probe. Related native
PNG/replay tests pass 49 cases; Ruff/mypy pass. A fresh actual match_001 prefix
probe/decode preserves all four native PTS/pixel hashes exactly. See the source
artifact for the recorded final decoder-code fingerprint and timing.

This is a common source-transport correction, with no OS-specific branch,
recognition change, source edit, sampler change or acceptance relaxation. The
previous CI failure's complete causal mechanism remains unproven until stronger
runtime evidence exists; current CI establishes the tested contract rather than
a guarantee that all external demuxer behaviors are now explained.

### Remaining Windows empty-probe diagnosis

Commit `b890ac4` passed both Linux runs and one Windows run; Windows job
`38186147433` failed three native-source tests (2627 passed, 10 skipped).
An empty frame list occurred in the production frame probe; the earlier
negative-origin test traceback was initially misattributed to the fixture.
The subsequent captured fixture diagnostics show its standalone probe succeeded. Neither single-thread decoding nor the no-zero-seek change
is sufficient to explain or eliminate this failure. The cause remains unknown.

The follow-up retains the last 2000 characters of successful ffprobe stderr
in rejected coverage errors. The synthetic fixture captures encoder/probe
stderr and asserts it contains frames before a consumer can use it. Pytest
prints these captured setup diagnostics only on failure. There is no retry,
frame repair, coverage relaxation or source-policy change. Local native-source
tests: 44 passed; Ruff and mypy (128 files): passed.

### EOF interval root-cause evidence and workaround

The failed Windows job uses FFmpeg/ffprobe **9.0.2**. Captured fixture output
shows 35 encoded frames and a successful standalone frame probe; the subsequent
`-read_intervals %` probe returned no frames and empty stderr.
[FFmpeg 9.0.2 source](https://github.com/FFmpeg/FFmpeg/blob/n9.0.2/fftools/ffprobe.c)
allocates ReadInterval with `av_malloc_array`. `parse_read_interval` sets
`has_end=0` for an omitted end but does not initialize `end_is_offset`,
`duration_frames` or `end`. `read_interval_packets` still reads `end_is_offset`
when `has_end` is false. This uninitialized-data path explains intermittent
early EOF without a decoder error; a debugger capture of the specific CI process
is unavailable, so the attribution is source-supported rather than a memory trace.

Native EOF windows now omit `read_intervals` entirely and probe all source PTS
from the physical origin, including when the requested start is positive.
FFprobe's default ReadInterval is explicitly zero-initialized. Bounded windows
continue to specify an explicit absolute end. No PTS, image or integrity checks
are changed, and truncated/duplicate/negative probes remain rejected.
Local native source/replay tests: **50 passed**; Ruff and mypy: passed.

Linux job `38188766402` passed all tests but aborted during Qt finalization
(shared QObject deletion/allocator error). The prior explicit media cleanup
was insufficient; that separate regression remains open.

### Agent versus player-name semantics: source correction

The later cross-context check shows the R1 header identifies agent `レイズ`,
while the red band shows player name `シャバーニ`. The original feasibility
diagnostic labeled a red-band crop `killer_agent_text`; its six R2 strings
remain the original raw measurement, but that label does not prove agent
semantics. R2's red-band player name happens to be `フェイド`, matching its agent.
Do not use whitespace normalization of this field to create killer_agent.
The actual source header/portrait and player-name fields need separate
qualification. The numeric-only profile remains available; an explicit optional
unqualified portrait-class candidate now preserves a separate label without
creating killer-agent or ownership semantics. See
[portrait source contract and qualification limits](report_portrait_candidates.md).
See [source geometry and semantic evidence](death_report_crop_comparison.md).

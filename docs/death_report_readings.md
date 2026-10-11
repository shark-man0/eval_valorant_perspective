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

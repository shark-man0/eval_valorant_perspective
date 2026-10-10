# Current-frame phase evidence and temporal flag contract

## Problem

Round starts must follow qualified preparation evidence, phase disappearance and
stable timer support. A missing debounced `buy_phase_banner` flag alone cannot
prove that current-frame preparation text disappeared. Qualification also cannot
equate a reader's isolated-image result with a continuous temporal state flag.
Targets remain `GT-R1-ROUND-START`, `GT-R1-ROUND-END`, `GT-R2-ROUND-START` and
their original count/ordering assertions. No GT or acceptance-window changes.

## Evidence

Fixed existing reviewed holdouts were passed through the actual production
analyzer, with four native origin frames for geometry in the same call. Prefix
gaps are diagnostic context, never temporal boundary corroboration. The53JPEG
holdout images retain their saved timestamp precision; they are not claimed as
an exact-cadence native sequence. Original selections, labels and image hashes
are checked before and after processing. Labels never enter the recognizer.

| Comparable reader metric | Previous | Current | Delta |
| --- | ---: | ---: | ---: |
| Timer correct | 25 | 25 | 0 |
| Timer unknown | 7 | 7 | 0 |
| Timer wrong | 0 | 0 | 0 |
| Raw phase positive correct | 8 | 8 | 0 |
| Raw phase positive unknown | 0 | 0 | 0 |
| Raw phase negative false accepts | 0 | 0 | 0 |

All13reviewed phase negatives are rejected; all21phase scans are valid.
The phase flags are present on only4of8positive images. That is NOT a raw-reader
regression: the old8metric counts text matches and the4metric counts classified
flags. `current_analyzer_component_holdout.json` initially exposes this difference;
`current_analyzer_phase_holdout_diagnostics.json` explicitly separates the metrics.

## Competing hypotheses and independent evidence

Geometry failure, reference mismatch, low NCC and downstream temporal suppression
were investigated. All8positive crops have effective calibration and a raw
semantic match at NCC0.90or higher. On the4without flags (98.002669,
102.719336,104.086003,111.269336), `semantic_buy_phase_confirmed` is absent.
`SemanticPhaseContext.advance` resets on gaps over1sec; isolated images do not
provide consecutive0.05sec support. Some other positive frames receive a flag
through the legacy classifier, which still does not supply qualified semantic
phase confidence. Reader match, classified flag and qualified preparation are
therefore kept separate.

These are source image/producer facts, not an attempt to re-prove the user's
no-edit guarantee. The exact video-specific assurance remains explicit. Loss,
PTS gaps, repeated adjacent pixels and recording discontinuities remain guarded.

## Contract change

Actual analyzer `native_ui_measurements` now preserves `phase_present` and
`phase_confidence` from the source semantic matcher before temporal classification.
The assured producer carries them as `assured_phase_present` and
`assured_phase_confidence`, separately from `assured_phase_scan_valid`.
The pair requires boolean presence and finite numeric confidence in[0,1]; a
positive also needs valid scan and confidence at least0.90. Partial or weak
positive proof is rejected. Legacy replay fixtures without the pair retain
compatibility; the current actual producer supplies it. Code-bound qualification
must be renewed after the production code fingerprint changes.

Positive source phase text with an unconfirmed flag cannot propose disappearance
or count as preparation: the start tracker discards pending preparation. It also
vetoes qualified same-frame ends and discards pending delayed ends. This only
removes unsupported candidates; it never promotes a raw text match into a start,
an end, a player identity or owned HP/weapon/death/shot fact. A false marker means
no accepted positive text match, not independently proven physical absence.
Timer corroboration and separate temporal qualification remain required.

No threshold, debounce duration, ownership policy, geometry policy, profile
reference, Validation Pack, assertion or full sampler changes. Default classified
flags are unchanged; only the assured global lifecycle guard uses the new facts.

## Tests and current actual-image replay

168related unit tests PASS (104.96seconds), RuffPASS, mypy121source filesPASS.
Tests include unconfirmed phase veto, current/previous phase veto on same-frame
end, delayed-end veto, malformed/partial/weak proof, source discontinuity and
existing native event/package/trace regressions. They remain synthetic contracts,
not real qualification.

Post-change actual analyzer on the same21phase images keeps8raw matches and
13negative rejections. All21source presence markers match raw reader output;
the4unconfirmed positives now retain their source marker. No classification is
forced to improve the flag count.

Unchanged30native R1 development frames from3.902669to4.386003sec are replayed
with the current actual analyzer and raw phase guard. Every native frame is
processed, native tick step256at1/15360verified; four origin prefix frames are
only geometry context. The candidate remains4.102669270833333sec, confirmation
4.202669270833334sec. All observed timer strings, including `0:00 → 2:25 →
2:25 → 1:39`, remain intact. Previous1candidate / Current1 / Delta0. No event
is released without qualification; no independent holdout is claimed for this
already exposed development window.

## Runtime and canonical comparison

The53-image analyzer run takes100.395378sec, diagnostic21-image phase replay
45.053673sec, final21-image transport replay44.957575sec and30-native-frame
R1analyzer58.193154sec. Offline tracker time is recorded separately. Earlier
direct-reader and longer native runs are different workloads; comparable runtime
Previous/Delta remain unavailable. No speedup is inferred from these values.

Canonical Previous23PASS/55FAIL/4NE; Current/Delta unavailable. All82original
assertion states/digest are preserved. Diagnostic released events0→0, delta0.
No targeted/sampled/full canonical run, new global qualification or profile
adoption. Canonical negative/discontinuity outcomes are not newly verified.
Windows hardware remains unverified; code and profile format remain shared.

## Artifacts and remaining blocker

`e2e_reports/match_001/current_phase_presence_guard_summary.json` binds the final
phase transport report and R1source report. Original reports retain historical
fingerprints; none is re-signed into qualification. Images remain local.

Next complete justified independent temporal qualification with disjoint reviewed
support and continuous source context. Isolated image correct counts cannot
qualify complete start-to-end lifecycle semantics. No artificial requirement for
three independent round episodes or an extra video is introduced. The existing
separate R1end timestamp/result delay blocker remains; it must not be solved by
backdating an event into GT. Then proceed through targeted/sampled and gated full
acceptance with unchanged negative assertions.

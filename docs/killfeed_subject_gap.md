# Killfeed victim reader and ownership contract gap

## Problem and target assertions

`GT-R2-DEATH`, `OWN-R2-SELF-DEAD` and `event_count_constraints-005` still require
qualified current evidence of who died, death semantics and Strict round
association. A report portrait class and damage value cannot attest self death.
Previous report diagnostics did not obtain reliable victim-name text.

## Evidence, root cause and hypothesis

On existing source development images, the original crop `[1752,98,1844,128]`
includes a border next to the victim name. Existing English TesseractTextReader
returns `sharkman |` or another punctuation token. It correctly retains minimum
word confidence, so the extra low-confidence token rejects the entire field.
Dropping tokens or lowering confidence is not an acceptable repair.

A frozen crop `[1754,103,1842,125]` excludes that border while retaining this
observed complete name. Existing processing, English language and psm7 remain
unchanged; diagnostic acceptance is0.90. Five development images yield two
correct accepted full names, one readable but subthreshold name0.897593 and two
absent-row rejects. This is not three accepted training supports or a general
victim reader. It is a crop-contamination hypothesis tested without production
changes, templates or name hard-coding.

## Prospective source check

Three previously reserved images at148.202669,148.702669,149.202669 visibly contain
the complete victim name. They were exposed to earlier numeric testing, but not
this victim reader. Selection and manual source labels were written before its
predictions, and their physical hashes are disjoint from the five development
inputs. Only one video, one death episode and one Latin player name are covered.

Controls130.002669 and140.002669 contain other/Japanese victim names with a
different field extent or row position; the fixed crop does not isolate their
complete names. Control146.002669 has no row. These are invalid-field/absent-row
controls, not proof that Japanese names should always be rejected. All are
rejected at0.90; no accepted garbled text occurs on this small set. A production
reader must locate and validate the complete current field independently;
these absolute coordinates cannot be adopted as a universal victim field.

| Metric | Previous original crop | Current frozen crop | Delta |
| --- | ---: | ---: | ---: |
| Correct victim text on positive holdout | 0 | 3 | +3 |
| Unknown on positive holdout | 3 | 0 | -3 |
| Wrong accepted victim text | 0 | 0 | 0 |
| Invalid-field/absent-row controls rejected | 3 | 3 | 0 |
| False accepted control text | 0 | 0 | 0 |

The three accepted confidences are0.904658,0.921208,0.919809. Combined original/
current OCR verification takes5.652s; development probe and production-binding
check are separate runs, not comparable speed benchmarks.

## Shared producer and ownership evidence

An existing SubregionReader/TesseractTextReader diagnostic injection processes
these six images plus calibration prefix through RealHudAnalyzer/profile13.
OCR fallbacks are explicitly disabled to isolate this reader. No qualification
is inherited by injected readers. The actual diagnostic sink records the three
correct raw accepted names, but native `kill_feed_rows` remains empty.

This is a necessary contract guard: the kill_feed binding expects structured
rows, while bare text contains no independently validated victim-role or row
association. `_normalize_reader_value(..., 'list', ...)` rejects the string.
Wrapping a string into a victim row or aliasing the observed name to self would
invent missing semantics. The profile loader currently has no dedicated
structured killfeed row reader; configuration of `kind: text` cannot bridge it.

All six observations remainunknown, HUD confidence0 and player-owned evidence
false. Three report-bearing positives have zero accepted live identity supports;
the current frame cannot borrow ownership from the report, its portrait, camera
view, player name or teammate-dead communication notification. The source
username is only a reviewed string, not an authorized runtime self identity.
The code/config has no subject-name matching contract to supply that binding.

The existing `_player_death_event` separately requires report presence plus
spectator-transition/self-HUD-loss/roster-self-dead evidence and
`death_source_confidence`; event confidence is capped by current HUD confidence.
The source producer supplies neither qualified self-dead proof nor that death
confidence. Thus solving OCR alone leaves several direct blockers, in addition
to Strict round qualification. These existing safety gates remain unchanged.

| Producer metric on these six images | Previous report-only | Text diagnostic | Delta |
| --- | ---: | ---: | ---: |
| Raw accepted victim strings | 0 | 3 | +3 |
| Structured killfeed rows from this text reader | 0 | 0 | 0 |
| Qualified self-dead ownership | 0 | 0 | 0 |
| Formal death events | 0 | 0 | 0 |

This diagnostic run takes13.339s for7frames. It is not continuous temporal
validation, and does not establish event timing, duplicate suppression or
source continuity. Control140 also has report presence; it is only a victim
field control, not an absent-report negative.

## Change, tests and conclusion

Only local diagnostic scripts and Markdown/JSON evidence are added in this
investigation; no production/schema/threshold changes. The preceding completed
current-code regression remains2690PASS/6SKIP, RuffPASS, mypy128filesPASS.
Actual source OCR and shared producer checks terminate successfully; native
observations pass SchemaValidator. Full E2E is unnecessary because complete
reader, ownership and temporal qualification have not been established.
All82canonical statuses remain23PASS/55FAIL/4NE; no new current full result or
negative/discontinuity remeasurement is claimed.

Bindings, exact PTS, pixel/input/code hashes and predictions:
[killfeed_subject_gap.json](../e2e_reports/match_001/killfeed_subject_gap.json).
No source pixels are shared. Windows execution remains unverified.

## Remaining blocker and next implementation

Build an independently localized structured killfeed reader that distinguishes
killer and victim and keeps original text/ROI/current PTS provenance. Test other
names, row positions, insertion animation and contradictory controls before
qualification. It must not know the reviewed name or Validation Pack expected
attributes. Self-dead attribution then needs a separately justified subject
binding and second death source; the system-only global lifecycle route cannot
be reused for player-owned facts. No fixed name crop, bare string wrapping or
confidence relaxation is adopted from this diagnostic.

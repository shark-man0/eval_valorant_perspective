# Unqualified report portrait candidates

## Problem

`GT-R2-DEATH`, `OWN-R2-SELF-DEAD` and `event_count_constraints-005` need a
source-backed semantic death producer, current ownership and Strict round
association. Reading report damage alone cannot establish them. The agent in
the report and the player name in its red band are different fields.

## Evidence and rejected hypothesis

Existing Japanese text OCR on six development frames accepts no complete
header line at confidence0.90. A narrower suffix sometimes accepts but loses
header context; red-band OCR is ambiguous and unreliable. Neither whitespace
normalization nor a player-name alias is evidence for killer-agent semantics.
The unmodified raw strings/confidences are retained locally in
`outputs/recognition-investigation/report-text-contract-20261012`.

The source report portrait offers a different measurable signal. Three
physically distinct development frames per class generate frozen median
portrait references, with source-reviewed class labels `レイズ` and `フェイド`.
The current header translates the fixed reference crop `[29,100,104,180]`
inside the438×500report. All three training inputs per class match their
frozen class. Existing TemplateValueReader uses NCC0.90 and ambiguity margin
0.035 unchanged; this is a class template comparison, not text OCR.

## Change and contract

An explicit optional `portrait_fields.report_portrait_label` entry in the
existing combat_report fields reader requires current independent header
localization. It cannot be configured for another ROI or without the locator.
Missing/ambiguous header, outside crop, weak/nonfinite match, unavailable asset
or missing template provenance fail closed. No retained label or pose is used.

The additional candidate field stores `label`, confidence, template/header
sources, actual normalized crop and `cross_checked=false`. Its parent retains
current PTS, source pixel hash and profile fingerprint. The optional observation
schema accepts it without changing existing required fields or schema version.
It is not original OCR display text and cannot attest killer_agent, player name,
identity, self ownership or death. The legacy numeric API and default profiles
are unchanged. Model/schema reject promoted, stale or malformed candidates;
the trace adapter exports no new semantic alias or event.

## Source verification and Previous / Current / Delta

The shared RealHudAnalyzer reprocesses nine hash-verified native source images
and a calibration prefix with the frozen diagnostic profile. Six source-reviewed
positives are physically disjoint from portrait training; labels and selection
were recorded before portrait prediction. These images were used previously for
numeric validation, so this is target-specific portrait holdout, not globally
fresh HUD/lifecycle holdout. There are two report contexts in one video.

| Metric | Previous | Current | Delta |
| --- | ---: | ---: | ---: |
| Correct portrait class candidates | 0 | 6 | +6 |
| Portrait unknown on positive images | 6 | 0 | -6 |
| Wrong portrait candidates | 0 | 0 | 0 |
| Natural absent-report controls rejected | 3 | 3 | 0 |
| Negative false accepts | 0 | 0 | 0 |
| Correct damage readings | 6 | 6 | 0 |
| Owned observations | 0 | 0 | 0 |
| Formal HUD/trace events | 0 | 0 | 0 |

Previous means the localized numeric-only reader on the same source set;
no candidate label was produced. All six values survive model/schema roundtrip.
Source run processes10frames in23.991s. Prior numeric-only run22.558s overlapped
unit tests and uses a different fingerprint; runtime difference is descriptive,
not a performance conclusion. No canonical full rerun: historical adopted
23PASS/55FAIL/4NE remains the reference, not a new current result.

Machine-readable source/provenance, exact PTS, confidence, physical splits and
artifact hashes: [report_portrait_candidates.json](../e2e_reports/match_001/report_portrait_candidates.json).
The diagnostic profile and portrait images remain local; no default adoption.

## Tests

169 related testsPASS, RuffPASS, mypy128source filesPASS. New tests cover current
header requirements, confidence/provenance rejection, independent numeric
abstention, outside-frame rejection, legacy API, invalid explicit configuration,
model/schema persistence and no promotion in trace. Full regression completes
2690PASS/6SKIP in1865.89s (previous2661PASS/6SKIP in1841.35s,
+29PASS/0SKIP and+24.54s/+1.33%; differing test count, not a speed benchmark).
Skipped checks include real-HUD fixture, system Tesseract and Windows/PowerShell;
the separately bound isolated-runtime source probe above is not a Windows check.

## Remaining blockers and next implementation

Natural absent-report negatives do not qualify rejection of another agent,
contradictory report subject, altered portrait or other layouts. A high matching
score on these correlated images cannot prove universal agent classification.
Reader qualification, report role and self-dead ownership remain separate gates;
formal death still needs an independent second source and temporal suppression.
Strict round qualification remains upstream. No extra full E2E is justified by
these unqualified candidates alone. Windows execution and CI for the current
uncommitted changes are unverified. The next contract to investigate is current
report subject/victim ownership, using independent killfeed evidence rather than
camera ownership or red-band name equivalence.

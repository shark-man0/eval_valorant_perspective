# Current-frame report field localization

## Problem and acceptance target

P2 report attributes are prerequisites of `GT-R1-DEATH`, `GT-R2-DEATH`,
self-dead ownership and death count assertions. The previously fixed damage
crop truncated seven R1 glyph rows. Static widening fixed R1 but changed one
correct R2 reading to unknown and was rejected. This implementation fixes local
field placement without changing global HUD geometry or any numeric threshold.
It does not complete the actor, semantic or Strict round prerequisites.

Start/analysis HEAD: `3f88b1a6120114643e71f72b247eb860e9b8416d`.
Changes remain uncommitted. Source SHA-256:
`71d58558559d6f578433ce9f234bf176f76fd5a86657dbfe3eba1e7d36136b06`.
Measured recognizer fingerprint:
`74bbda51d0ed3e0ecd9c9d0a74ca79c16f5a685a9bba4d88fb5042d590f7c695`.

## Existing structure reused

`ReportHeader` already matches two spatially independent static header supports,
using NCC >= 0.90 at one shared pose. Its masks exclude damage values, player
names and agent-specific portraits. The existing reference/mask/support assets
are reused unchanged; no new reference, OCR model or value-conditioned crop
is introduced. Presence remains exclusion-only evidence.

`report_header_evidence(..., include_pose=True)` optionally exposes the accepted
local position. The default return/presence contract is unchanged. Two qualifying header positions outside a two-pixel vertical neighbourhood
cannot choose a number, even if their template extents overlap;
they can still add report exclusion evidence. Partial geometry or missing or
contradictory support also cannot place a field. Adjacent matching positions of
one header do not represent two separate report panels.

`ReportFieldLocator` applies the current translation relative to a training
reference origin. No pose is retained between frames. The existing report model
search, geometry, support counts, mask validation and NCC threshold are retained.
It does not establish report absence, self identity or numeric corroboration.

## Opt-in profile and native observation

Only the `fields` reader on `combat_report` accepts this additional setting:

```json
"localization": {
  "method": "report_header_pose_v1",
  "reference_origin_norm": [0.0639269406392694, 0.436]
}
```

The reference origin is a local report position measured on three development
R2 images, not a timestamp or GT field. Existing field bounds remain unchanged.
R1's accepted header is 16 pixels lower, so the field moves down 16 pixels;
R2 retains its old field bounds. No special case recognizes 190, 194 or a round ID.
The profile must already have a valid independent report_header_detector.
Malformed or unsupported explicit localization keeps an unavailable reader,
including non-report roles, rather than silently substituting OCR.

The optional source observations remain status=candidate, with the original
OCR display, source PTS/pixel hash, profile fingerprint, actual translated
roi_bounds_norm and report_header_pose source marker. Numeric confidence is
bounded by header confidence. Numeric cross_checked is not raised by matching
a header. Out-of-image translated fields are rejected without clipping.
Model/schema format and the legacy numeric read API are unchanged. Default
profiles have no localization setting and preserve previous behavior.

The global code fingerprint changes, so prior recognition archives or
qualifications cannot be rebound to this code. Source pixels remain reusable
only under their existing source/asset verification contracts.

## Source splits, tests and comparison

Six development images (three physical R1 and three physical R2 images) define
reference geometry; existing header assets are not refitted. The previously
exposed nine-frame regression cohort now yields six correct values and three
natural absence rejections, including the R2 frame lost by static widening.
That cohort is explicitly development/regression evidence, not fresh holdout.

Before any prediction, a new fixed cohort selects first native frames at/after
0.35/0.5/0.65, 151.5/154.5/158 and 1.6/126/144 seconds. Manual pre-prediction
labels show three 190s, three 194s and three absent reports. All nine are retained.
Training, positive holdout and negative physical pixel hashes are mutually
disjoint. Both common analyzers process the same ten inputs (including a source
calibration prefix), with real geometry/feature/OCR readers and no injected
outputs. Terminal input/source/profile/code hashes and native observation schema
roundtrips pass. This remains a same-video, two-report, two-value component check,
not independent global lifecycle qualification or temporal death acceptance.

| Metric | Static baseline | Header-localized | Delta |
| --- | ---: | ---: | ---: |
| New holdout correct | 3 | 6 | +3 |
| New holdout unknown | 3 | 0 | -3 |
| New holdout wrong | 0 | 0 | 0 |
| Natural negative rejects | 3 | 3 | 0 |
| Negative false accepts | 0 | 0 | 0 |
| unknown → correct | — | 3 | R1 fields |
| correct → unknown / wrong | — | 0 / 0 | No loss of prior correct value |
| Formal HUD events | 0 | 0 | 0 |
| Report-owned observations | 0 | 0 | 0 |
| Processed inputs | 10 | 10 | 0 |
| Analyzer seconds | 17.024 | 17.598 | +0.573 (+3.37%) |
| Canonical full PASS / FAIL / NE | 23 / 55 / 4 | not rerun | unavailable |

Related tests: **244 PASS in 104.73 sec**. Full pytest with both external Pack
variables explicitly set: **2661 PASS / 6 SKIP in 1841.35 sec**, exit0.
Ruff on src/tests/scripts/e2e and mypy128 source files PASS. Tests cover the
legacy presence contract, vertical translation, original strings, no stale
pose, conflicting headers, independent supports, out-of-bounds fields, low
numeric confidence, confidence cap, malformed profile/role and no fallback.
Skipped tests remain unverified optional/platform tests, not PASS.

## Standard targeted regression and runtime discrepancy

The first adopted-profile13 standard37-point run used the normal environment,
where shutil.which(tesseract) is None. It finished9PASS/16FAIL/12NE, versus the
old12/13/12. The three additional failures are missing HP at141.936003,
145.852669 and147.019336. State counts and trace SHA-256 remain identical.
This discrepancy was investigated rather than labeled a successful regression.

Two isolated Python source trees compare HEAD and modified code on identical
pixels/profile for those three points and calibration prefix. Both yield
unknown HP without OCR; both yield80 with identical confidence using the
existing isolated Tesseract5.3.4 binary/language assets. No default PATH or
system installation changes. This establishes the missing dependency as the
cause of these three differences, not report localization. The old run did
not bind OCR runtime availability in its comparison fingerprint, so identical
settings fingerprints alone do not prove identical execution dependencies.

The standard runner is then executed once with the isolated OCR environment
explicitly enabled for that process only. It finishes12PASS/13FAIL/12NE with
identical failure records, state counts (live6/spectator6/menu3/unknown22) and
trace hash `f0799f3b83ec16557111a59265143414ddf0356f2abb1f38b46d08f09926c00a`.
Terminal artifact hashes verify. Its exit1 denotes the13 existing field FAILs.
Wall time262.472sec versus550.047sec is descriptive: cache/runtime conditions
differ, and no speedup is attributed to the new optional reader. These isolated
points do not evaluate continuous lifecycle or full negative/discontinuity
assertions. No new canonical assertion PASS is claimed.

## Remaining blockers and next task

The localized source field remains unqualified and unowned. Source header/portrait
agent semantics must stay separate from red-band player-name semantics; name
normalization alone cannot create killer_agent. Current self-dead ownership,
independent broader controls/temporal qualification and P1 Strict round
association remain required. No death event or evaluator alias is manufactured.

No sampled/full adoption E2E is justified before those qualification gates.
Windows verification of these new uncommitted code changes is outstanding;
previous HEAD CI successes do not validate this diff. No main merge or push
is performed in this ordinary Goal continuation.

Machine report: `e2e_reports/match_001/report_field_localization.json`.
Private runs: `outputs/recognition-investigation/death-report-localized-holdout-20261012`
and `outputs/recognition-investigation/report-localization-targeted-ocr-20261012`.
The next production contract is separate source-preserving agent-header versus
player-name observations, with explicit qualification and safe owner binding.

## Final safety revalidation

A synthetic second header whose template overlaps the first revealed that
separating candidates only by the full template height was insufficient.
The opt-in locator now rejects a second qualifying vertical position outside
the two-pixel neighbourhood of the winner, including both near and far duplicate
headers. The default presence/exclusion decision is unchanged. All fixed source
readings and their metadata revalidate identically; six correct, three negative
rejections, zero wrong/false accepts, zero owned report readings or events.
The final source revalidation runtime22.558sec overlapped related tests and
is not compared as a speed measurement. Final244related and2661full tests
pass after this last production safety change. The recorded standard targeted
run predates it and does not activate opt-in field localization; it is reported
as that measured version rather than relabeled as an exact final-code run.

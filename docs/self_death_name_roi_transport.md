# Self Death: padded separator witness and own-name layout

Status: **B, real candidate fields improved; independent qualification and
canonical FAIL reduction remain incomplete**. Main at this work began at
`7e480c2f2f7f49aea73e1541d065d78881d2f11c`, branch at
`9c0a16b5aeb3c46be9253043ef1d88e0f2eb8ea3`. The preceding source-assurance fix,
`4e1fbe3de124adc1c2f7c849924dbe537aa6c88c`, passed Linux/Windows PR and push CI,
text-I/O audit and Windows packaged smoke. Those checks are not assigned to the
new reader bytes. PR #53 remains a Draft stacked on #52; no main merge.

## Problem and source evidence

A new frozen local source window showed an actual recording-player death.
The fixed reader detected its yellow victim marker and fresh Report but the
weapon had geometry only, no numeric NCC. A second fixed window showed a living
player leaving the purchase menu, with an old Report reappearing. Both were
selected before role output, reviewed from native pixels before replay and
retained regardless of outcome. No source video was copied. Original caption
localization and unknown historical global geometry exposure remain explicit;
these are not blind or whole-match recall cohorts.

A single weapon-class reference was then extracted from an **already exposed
development** episode, using the previous fixed three-pixel plate-padding rule.
The private prototype only appends that array to the existing bank; all old
arrays, thresholds, ROIs, horizons and code were initially unchanged. The
reference contains the pictogram/plate, not names, values or GT. It is not a
new qualified or default profile. The development episode is explicitly
excluded from independent holdout.

The new reference supplied actual NCC on 74 frames of the other death window,
but exposed a concrete implementation bug: the template canvas includes plate
padding, while `_weapon_glyphs()` returns actual connected ink bounds. The name
crop incorrectly used the padded canvas edge. In the native frame at 1881.250 s:

| Measurement | Original geometry | Padded numeric template |
| --- | --- | --- |
| Weapon witness ROI | `[1614,102,1709,124]` | `[1611,99,1712,127]` |
| Name ROI | `[1752,103,1834,125]` | `[1716,103,1834,125]` |
| Headshot glyph excluded | Yes | No |

Moving the name search three pixels clipped the headshot-template search. OCR
then saw that symbol as name input. Correct accepted names fell from 54 to 2,
with four additional incorrect symbol-prefixed readings. This intermediate
prototype was **not adopted, qualified or enabled**; its failure artifacts are
preserved. Symbols were not stripped from OCR output to disguise the failure.

## Minimal reader correction

For the existing mixed geometry/template method, name layout may use a unique
current-image pictogram wholly contained in the accepted NCC canvas, with the
existing physical-overlap condition. The original template ROI and its numeric
support remain the role witness. Geometry supplies neither a synthetic NCC nor
extra confidence. If that unique correspondence is absent, the previous layout
path remains. Pure template, pure geometry and ability paths retain their
contracts.

The name crop uses the measured ink boundary before the unchanged headshot
matcher and edge-clipping/OCR acceptance checks. This works for both killer and
victim layout. Nothing copies a name from the other row, an adjacent time, a
review, GT or a scoreboard. Source SHA/PTS/pixels and own-row name ROI remain
attached. HUD identity, ownership, confidence meanings, schemas, event policies
and all numeric thresholds are unchanged. Existing exact code/profile
qualification bindings still reject old qualifications after this code change.

Synthetic regressions exercise the padded NCC and ink ROI separately on both
sides. They require the same name crop as the geometry-only source, preserve
original numeric ROI/score and plate support, and emit no formal Event. The
focused reader suite passed 55 tests; the related regression passed 345 tests
in 94.11 s. Repository Ruff, mypy (148 source files) and zero-unclassified-text-I/O
checks passed. Current-code remote CI is recorded separately.

## Actual continuous replay

All selected native frames were re-recognized after the code change. Source 2
used the explicit private prototype above; source 1 retained its existing v4
profile. No saved recognition row was called a new result. Each window has its
own native observation context; none bridges a source gap. No labels, expected
names, GT values or timestamps were provided to the runtime.

Counts below are correlated field observations, not independent deaths.

| Source-2 context | Metric | Previous | Current | Delta |
| --- | --- | ---: | ---: | ---: |
| New death, case 005 | Numeric victim readings | 0 | 74 | +74 |
| New death, case 005 | Correct own-name readings | 54 | 54 | 0 |
| Concurrent old Self Killer/new Self Victim, case 002 | Correct victim-name readings | 0 | 74 | +74 |
| Same case 002 | Numeric victim readings | 119 | 119 | 0 |
| Existing case 003 | Correct victim-name readings | 29 | 29 | 0 |
| Living/old-Report reappearance, case 006 | Death predictions | 0 | 0 | 0 |
| Three death episodes | Diagnostic predictions | 3 | 3 | 0 |
| These fixed source-2 contexts | Incorrect accepted victim names | 0 | 0 | 0 |
| These contexts | Formal Death Events | 0 | 0 | 0 |

The intermediate name regression above is separate from the original-profile
Previous column. Against that failed prototype, the fix restores 54 correct
names from two and removes all four symbol-prefixed readings. Across the final
source-2 windows, 157 accepted victim-name readings match the independent visual
source labels. This is a fixed exposed-cohort check, not general OCR accuracy.

Case 002's recovered victim name comes from its **own second row** at y=142–164;
the concurrent Self Killer name is y=103–125. The old absence was a crop defect,
not a missing source string or permission to borrow the killer's name.

Original onset/confirmation pairs are unchanged: case 002
69.216667/69.333333, case 003 512.616667/512.716667, case 005
1880.950000/1881.250000. Case 005's source review only brackets the transition;
it does not prove exact timing accuracy or qualify an Event. The Report onset
precedes accepted victim-row evidence, which still requires temporal review.

Source 1 processed 171 frames across five fixed windows, including overlapping
R1 regressions. Victim-name/NCC counts, candidate onset/confirmation, source
blocks and negative-window predictions are identical to the original output.
Overlapping R1 windows are one episode, not independent positive successes.
No formal Event was emitted on either source.

| Run | Frames | Replay wall sec | Recognition sec | Peak Python RSS bytes |
| --- | ---: | ---: | ---: | ---: |
| Source 2, four windows | 544 | 827.473 | 662.678 | 96,768,000 |
| Source 1, five windows | 171 | 227.978 | 199.700 | 97,226,752 |

The new two-window acquisition retained 405,015,964 lossless PNG bytes and took
618.805 seconds. It used the already local video and disk-backed hard links,
with an explicit storage budget. All runs passed terminal source, encoded/pixel,
code/profile/asset and dependency checks. This is not a performance-optimization
claim. Private plans/frozen inputs/failure records/results stay in ignored
outputs; the public aggregate contains hashes/counts, not private images,
profiles, names or GT.

## Qualification and canonical limits

The source pixels used to diagnose/fix name layout are now **development or
regression for that layout**. They cannot be relabeled new blind holdout.
Known earlier native replay exposure of cases 001–003 is also retained; their
new recognition measurements do not make those source windows unseen.
Component-specific exposure still needs independent review before any numeric
Subject, role, temporal or semantic-attribute qualification is issued. The
private prototype is not installed as a default and no real certificate was
created.

Adopted Full remains 23/55/4; archived unadopted Strict remains 28/50/4. No new
canonical targeted/sampled/Full run, current PASS/FAIL/NE, new PASS assertion or
current canonical negative/discontinuity count is claimed. Those values are
**unmeasured**; the historic 20 negative PASS are not current-reader evidence.
Full remains unjustified before independent qualification and an enabled
qualified-provider real positive.

Next, qualify the existing marker/role/Report/temporal components using an
explicit component-specific exposure inventory, then test the qualified provider
and canonical count path. Own-name attribute qualification is separate from
count eligibility. Missing killer-agent/damage semantics cannot be filled from
the source labels merely because this crop defect is fixed.

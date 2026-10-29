# Shared development timeline comparison

The common engine and supplier APIs reconstruct a development Round sequence,
but recorder life/reentry and self-position recovery remain **UNMET**. Keep this
Draft and retain the existing default recognizers. No Production/main merge or
evaluation-specification change is authorized.

| Fixed evidence / metric | Result | Interpretation |
| --- | --- | --- |
| Previously exposed DEVELOPMENT physical matches | 3 | No protected recording used |
| Observation records / acquisition frames / physical native points | 11609 / 11402 / 11308 | Different acquisition IDs do not create independent events |
| Shared Source-clock second rows | 1170 | 297 have observations; 873 are explicit missing bins |
| UNKNOWN Round / life / camera second rows | 963 / 1170 / 1152 | Includes unexposed bins; not negative duration |
| Legacy display-boundary proposals found / bracket overlap | 8/8 / 8/8 | Proposal agreement, not independently correct events |
| Maximum display upper-endpoint difference | 0.166667s | Not an internal event timing error |
| Same-input shared HUD state-value changes | 0 / 11342 | Output parity, not an accuracy claim |
| Same native Map observations / changed observations or pools | 140 / 0 | Source pixels and original candidates preserved |
| Legacy selected Map candidates → shared-context consumer | 81 → 0 | Complete abstention; **not an improvement** |
| Previously reviewed self-role selections lost | 4 / 4 | Exact-image role controls; not world-coordinate GT |
| New bounded cycle | 7561 native PTS checked; 127 retained points; 2 starts / 1 end | One acquisition supports start→end→next-start candidates |
| New-cycle recorder life | UNKNOWN 127/127 | No restored full recorder life episode |
| Formal Facts / Events | 0 / 0 | Qualification not established |

Across all acquisitions there are 6 start and 5 end candidate records. Overlapping
brackets produce 5 start and 4 end evidence groups; neither count is verified
physical-event identity or a count of correct recognition. The new targeted cycle
is exposed DEVELOPMENT evidence, not a blind qualification sample. Original GT,
fixed windows and strict evaluation contracts are unchanged. Correct/false Round
boundaries, internal timing error, general ownership accuracy and correct world
position/Zone remain unmeasured without independent matching GT.

## Phase results

A: additional bounded real decoding yielded one complete candidate Round cycle
in one acquisition, with retained native times. Native acquisition integrity is
not semantic continuity proof. B: spectator displays and later first-person
presentation exist, but the common model does not restore recorder death/return.
Existing Source-wide roster binding and current ability glyphs do not establish
current ownership when the spectator absence slot is unobservable. The gate was
not relaxed. C: multiple Round intervals share one Source clock with explicit
unobserved gaps and parallel acquisition lanes. D: fixed-input comparisons show
state/pool preservation but total self-position abstention and four known role
selection losses. The shared engine is a research basis, not an adopted baseline.

## Learning and performance

Physical-match split: two train matches and one comparison match; no split by
frame/epoch. Next-feature MSE: persistence 0.033478, ridge
0.020465. Weak Round teacher agreement: centroid
0.6200, temporal reranker
0.8121. These measure automatic feature/teacher
agreement, not recognition accuracy. The known camera teacher class is spectator;
a perfect agreement there does not establish self recognition. All learners are
**unadopted** and old methods remain available.

Frozen observation normalization/replay reference measurements:
HUD-only 6.720s / 552.8MiB;
Map-only 3.042s / 276.4MiB;
combined 10.047s / 701.7MiB.
They exclude new video decoding, image recognition, output writing and learning;
no end-to-end speedup or full-match memory qualification is claimed. New bounded
Round image recognition took16.4s in its recorded run. Source capture total wall
time was not recorded, and that missing timing is not inferred from file dates.

## Validation and restart boundary

Local full repository run before the final small comparison/Map contract changes:
4155 passed, 9 skipped, coverage86.16%. Final affected tests:63 passed. Full-source
mypy141 modules, Ruff, classified text-I/O and38 dataset contract cases pass.
The codec test checks all native PTS versus sparse retained PNGs. These tests are
not real-video recognition qualification. Exact Draft-head CI/Windows/package
status is recorded separately; historical supplier CI is not reused.

Supervisor review precedes restarting separate recognition improvements:

- HUD: make current spectator-slot observability/absence evidence reliable;
  export Source-bound self/death/downed/revival/remote observations. Preserve
  UNKNOWN and current shared state definitions; do not reinterpret Report as death.
- Map: consume the approved shared context and preserve the four existing
  reviewed selections without increasing wrong attribution. Keep unassigned
  candidates/geometry and observed endpoints; add no private life/Round FSM.
- Common owner: own state definitions, candidate revisions, conditional continuity,
  duplicate-epoch grouping and physical-match learning evaluation. Obtain a fully
  reviewed recorder episode before claiming life recovery or learner superiority.
  Measure whole-match performance separately before practical adoption.

See [API/specification](development_shared_timeline.md) and
[dependency ledger](development_shared_timeline_dependencies.md). The development
`temporal.replay`, `temporal.acquire`, supplier observation adapters and
`temporal.compare` CLIs retain private inputs/evidence outside Git. Reproduction
uses new private output directories. Full Tesseract/decoder executable and
traineddata fingerprints were not frozen by the old image-reader supplier;
byte-identical raw recognition or strict qualification is not claimed. The fixed
observation replay is bound to exact input and implementation hashes.

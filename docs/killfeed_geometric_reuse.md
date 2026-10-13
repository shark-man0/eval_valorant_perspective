# Existing portrait geometry cannot directly localize killfeed victims

## Problem

The previous fixed outer-frame reference fails minimum training support and
transfer to other victims. Before designing a new reader, test reuse of the
existing portrait proposal mechanism. Dependencies remain`GT-R2-DEATH`,
`OWN-R2-SELF-DEAD` and`event_count_constraints-005`; no actor or ownership proof
is supplied by this investigation.

## Evidence and method

The existing`hud.spectator.portrait_frames`runs unchanged on current killfeed
ROI478×143with the same Canny60/150and signed orientation measurement. Its
contour/Hough proposals, normalized geometry and directed side-occupancy gates
remain intact. Frozen separatorNCC0.90supplies only one independent row support.
A subsequent diagnostic pair would require a same-row portrait to the right
plus at least three aligned glyph-like components between them. No name value,
GT time or expected identity is used.

Inputs are three reference-development images, three same-victim source
witnesses, two other-victim rows and one absent-row image. All nine images are
already exposed development data; this is not a fresh holdout. Their pixel and
encoded hashes match the prior diagnostics. The word detector is not run or
reinterpreted as complete victim text.

## Results and competing hypotheses

| Metric | Expected supporting images | Observed | Difference |
| --- | ---: | ---: | ---: |
| Existing killfeed-row images with portrait proposal | 8 | 0 | -8 |
| Absent-row false proposals | 0 | 0 | 0 |
| Existing-row images with final geometry/text pair | 8 | 0 | -8 |

Zero proposals do not mean there are no actual portraits. Directed rectangular
side occupancy or normalized geometry rejects every candidate. At148.202669,
for example, the best candidate has top/bottom occupancy1.0/1.0but left/right
occupancy0.0833/0.1667. At149.202669the best mean score0.69697remains below the
existing0.70gate. No near-threshold exception is introduced. Some images produce
no rectangle meeting geometry at all, so this is not exclusively an occupancy
problem.

Source review shows the killfeed portrait frame is not the same rectangular
panel family used for spectating. The rejected fixed-edge experiment already
shows frame appearance differs across existing victims. These observations do
not prove a particular tint or alpha cause. The existing frameless alternative
also requires two adjacent text rows; a killfeed name row does not meet that
contract. Loosening its requirements would change spectator safety and is
outside this task.

Decision: **reject direct reuse**. Thresholds and the spectator detector stay
unchanged. The probe takes1.462s; no speed comparison or accuracy claim follows
from a rejected proposal-only run.

## Previous / Current / Delta

| Production metric | Previous | Current | Delta |
| --- | ---: | ---: | ---: |
| Qualified structured victim reader | 0 | 0 | 0 |
| Self-dead ownership from this route | 0 | 0 | 0 |
| Formal death events from this route | 0 | 0 | 0 |

No production, schema or tests change. Existing2690PASS/6SKIP/Ruff/mypy results
remain the preceding verified code result; no unnecessary regression/full E2E
rerun. Canonical82statuses remain23PASS/55FAIL/4NEand are not a newly measured
full result. Windows qualification is unverified.

## Next action and priority

A dedicated killfeed polygon-frame/current text contract needs its own source
support, ambiguity handling and controls; copying the spectator frame policy or
using a separator alone is insufficient. The current name crop stays diagnostic
and no exposed image becomes fresh holdout later.

The largest canonical blocker remains qualified global round lifecycle/package
association. Review of existing result qualifications confirms that late/early
result references, shared translation, masked structure and raw-line OCR have
already been tested and rejected or left unqualified. Do not rerun those methods
under new candidate names. Existing result evidence also fails exact-word
confusable controls (`TEAM ACE`versus`TEAM AGE`), so high whole-word NCC is
insufficient for semantic qualification. Independent glyph discrimination and
paired temporal qualification remain prerequisites before canonical adoption.

Exact measurements and source/code bindings:
[killfeed_geometric_reuse.json](../e2e_reports/match_001/killfeed_geometric_reuse.json).

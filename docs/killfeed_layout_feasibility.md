# Killfeed structure: rejected fixed-edge reference

## Problem

The victim OCR crop improvement does not solve current row/field localization.
Target dependencies remain `GT-R2-DEATH`, `OWN-R2-SELF-DEAD` and
`event_count_constraints-005`. A fixed name crop must not become a generic
victim-role reader or self-dead fact.

## Evidence and hypothesis

Three existing development images generate frozen median grayscale references
for two independent UI portions: the separator at `[1716,96,1746,131]` and the
outer victim-frame wedge at `[1898,96,1914,131]`. Masks contain696 and377pixels,
respectively; no name, weapon or portrait interior is selected. A wider initial
frame patch was rejected before holdout prediction because its top mask could
include portrait content. Final reference/mask statistics and exact input hashes
are preserved in the machine-readable report.

Both supports search all positions inside the current478×143killfeed ROI.
Masked zero-mean NCC is evaluated independently, flat patches fail, and accepted
scores are recomputed in float64. Threshold0.90 remains fixed. Pairs must be on
the same row, separator before victim frame; one match alone cannot place a name
field. Nearby pixel poses describe one marker, not duplicate events. This is a
local offline diagnostic, not new production recognition code.

Three source images used for victim OCR are physically disjoint from reference
training. They are exposed development evidence for overall HUD/OCR, and
first-use transfer witnesses for this layout probe; they are not globally fresh
holdout. Two other-victim rows are positive transfer controls, not negatives.
One absent-row frame tests absence. No GT inputs are used.

## Results and rejection

| Physical support metric | Required | Observed | Difference |
| --- | ---: | ---: | ---: |
| Training images with both supports | 3 | 2 | -1 |
| Same-victim layout witnesses with both supports | 3 | 3 | 0 |
| Other-victim row transfer witnesses with both supports | 2 | 0 | -2 |
| Absent-row false pairs | 0 | 0 | 0 |

The separator matches all three training inputs and all five existing-row
witnesses at≥0.986. The victim edge fails one training image (best0.894022)
and both other-victim rows (best0.806967/0.828081). The absent-row image supports
neither. Strong matches on the same stable victim do not compensate for missing
minimum support or cross-layout transfer. The proposal is **REJECTED**; no
threshold adjustment, mask expansion after holdout, or production adoption.

The failing frame variants may differ in border presentation, alpha/background
or rendering. NCC alone does not prove which variation causes it. We do not
infer player ownership from the victim-frame highlight. A field inferred from
these two supports is still a candidate crop, not proof of complete text or
killer/victim semantics.

## Previous / Current / Delta

| Production metric | Previous | Current | Delta |
| --- | ---: | ---: | ---: |
| Adopted structured killfeed reader | 0 | 0 | 0 |
| Qualified self-dead ownership from this route | 0 | 0 | 0 |
| Formal events from this route | 0 | 0 | 0 |

Historical canonical23PASS/55FAIL/4NE is retained; no current full reevaluation
or global negative/discontinuity claim. Source-video SHA256, input and terminal
artifact hashes verify. No production/schema/test changes were made, so the
preceding2690PASS/6SKIP/Ruff/mypy checks are not rerun. Full E2E is unnecessary
for a rejected reference. Windows validation remains pending.

## Remaining blocker and next implementation

The separator is transferable evidence, but it cannot alone authorize a victim
field. Reuse current geometric portrait-frame and adjacent-text evidence for
that second independent support, with row association and ambiguity rejection.
Keep reference training, transfer controls and future holdout explicit; these
exposed images are now development inputs. Subject ownership, temporal death
corroboration and Strict round association still require separate proof.
Do not copy a reviewed username, actor or GT value into production.

Bindings and full measurements:
[killfeed_layout_feasibility.json](../e2e_reports/match_001/killfeed_layout_feasibility.json).

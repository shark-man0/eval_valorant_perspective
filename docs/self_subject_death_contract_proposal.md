# Proposal: source-qualified self-subject Death evidence

Status: development and source qualification conditionally approved on 2026-10-16.
Production adoption and unqualified event release remain unapproved. The original
proposal below is retained; see `self_subject_death_evidence_implementation.md`
for the separate experimental implementation and its unresolved qualification.
Base: `46584ad7fd99d18bbbdbcf0d73a2c0263ccaecce` (PR #46); fetched main remains `7e480c2f2f7f49aea73e1541d065d78881d2f11c`.
PR #44 transport and PR #46 ownership restriction are preserved unchanged. PR #42 is not modified.

## Problem established by current code and source

- `HudDirectEventBuilder.build()` now correctly requires its existing current-frame player-owned predicate on the legacy report/transition Death path. Weakening this guard is not proposed.
- `RealHudAnalyzer` masks HP/ammo/weapon when `player_specific_hud_valid` is false. The source measurement of a number is not source-player identity.
- `tests/e2e/trace_adapter.py:to_e2e_trace` exports `player_alive` from current owned HP (`hp > 0`). It has no separate subject-qualified death/life input. It intentionally preserves bad native fields so canonical negatives can detect contamination; patching the adapter to invent or hide facts would be wrong.
- The current report-field model explicitly has `status=candidate`; no owned subject is certified. The original Full has no structured killfeed or report field-reading observations.
- Previously reserved victim OCR review has 3 correct / 0 unknown / 0 wrong and rejects 3 negatives, but covers one victim name and explicitly reports `source_owner_resolved=false`. Localized report numeric review has 6 correct / 0 unknown / 0 wrong and 3 rejected negatives, but only one value/death context and no subject qualification. These are not missing facts that an adapter may recover.
- Fresh 102-frame negative replay fixes an unsafe legacy Death candidate, not the missing positive subject. The 20 state/life measurements do not supply qualified owned identity.

## Requested decision

Authorize development of a **separate subject-qualified Death producer**, whose event subject identity can be qualified independently of live first-person HUD identity. Merely seeing a report, victim text, damage, spectator view or global timer/score would remain insufficient. No positive event may be released until source/subject/temporal qualification is complete.

This is an explicit addition to the current event-identity policy and provenance contract, so implementation must wait for approval under S-01 additional instruction section 10. Approval would permit development of this path, not qualification by assertion, production adoption or a guaranteed PASS gain.

## Concrete proposed contract

Use a separate typed subject-evidence model, not arbitrary trusted booleans in `evidence_by_frame`. It must retain:

| Field | Required meaning |
|---|---|
| source video SHA, native PTS/time base, pixel SHA | Exact physical observation |
| source segment identity | No fusion across source discontinuity |
| observation role | Report candidate, killfeed victim, killfeed killer, or independently observed source-player binding; roles cannot substitute for one another |
| subject binding | unknown / self / teammate / enemy, with the actual source evidence supporting the relation |
| qualification state and proof | Candidate vs independently qualified, with code/profile/assets/dependency binding and review provenance |
| confidence and contributing source scores | Finite supported values only; no default confidence or increase from combining unknown evidence |
| corroborating observation references | Independent same-segment evidence and native PTS for the death transition |
| candidate time and confirmation time | Preserve actual onset evidence; later confirmation must not become the event time automatically |

A subject name alone is an OCR string, not proof that it belongs to the recording player. Self binding needs its own independently reviewed on-screen/source evidence. No GT expected subject, death time or round label is supplied to the producer. Runtime must make the same decision without a Validation Pack.

Formal `player_death` release would require **all** of:

1. Qualified source-player subject identity and an observed death-related role/transition; no inferred self role from report placement, teammate relation or spectator alone.
2. Independent temporal corroboration, consistent source segment, and no unresolved conflicting observation. Persistent report after respawn and a repeated report do not create new deaths.
3. Actual confidence support satisfying existing formal event acceptance rules. No new lower numeric floor is proposed. Any unsupported score remains unknown.
4. Valid native event time and provenance, one event per observed death episode, correct lifecycle-derived package association and no inferred R2 end.

The legacy live-HUD route and its new ownership guard remain intact. No new optional evidence means exactly the old behavior. An unknown subject emits a private candidate/blocker only, never an owned event or Fact.

## Limits of approval and downstream behavior

- This first scope is **event subject qualification only**. It does not set HUD `player_specific_hud_valid`, primary state, `view_owner`, HP, Armor, Weapon, Ammo, Utility, location, shot or alive/dead snapshot fields.
- Unknown HUD identity remains unknown for HUD ownership. Only an independently qualified event subject could identify that event as self; the distinction must be visible in provenance.
- It does not propagate death into a life interval until respawn by assumption. A later snapshot-life contract would require separate current/temporal evidence, persistence limits, contradiction/reset handling and review.
- Reuse native event → package → trace attributes for provenance where existing schemas allow it. Do not insert undeclared properties into closed Schema v2/v3 models. Any schema extension must be additive, explicitly versioned, and reviewed before adoption; old serialized data must parse as evidence absent.
- SQLite, checkpoint/resume and trace must preserve the distinction between absent, candidate and qualified subject evidence. Resume on a mismatched code/profile/source proof must fail closed.
- Canonical assertions, acceptance windows and negatives remain fixed. This proposal targets four direct Death first blockers conditionally, not all life/state/ownership failures. Guaranteed PASS gain is **0** until real canonical evaluation proves otherwise.

## Source qualification plan and stop conditions

First inventory available original source pixels and their historical exposure; freeze development/review/negative assignments before any new fitting. Preserve old labels and splits. Previously exposed victim/report examples cannot be renamed blind holdout. Additional recordings are not a blanket prerequisite.

Needed independently reviewed semantic roles are: source player binding, self-victim, nonself victim, killer vs victim discrimination, teammate/enemy relations, report persistence after respawn, spectator transitions without new self death, remote/menu/report overlaps, repeated reports and actual source breaks. Review must describe what the pixels establish, including unknown, without importing assertion expected values. If the available source cannot establish self binding, stop positive release and record that specific missing evidence rather than fitting more OCR variants.

Validation sequence after approval: typed-model and compatibility negatives; existing owned/unknown tests; fresh role-reader development/review/negative measurements; source-continuous temporal windows; targeted canonical evaluation; fixed sampled regression; Full only when a positive qualified hypothesis survives. A candidate-only result is not accuracy improvement. Source/confidence/actor/provenance and negative regressions are mandatory; no old raw is retagged as new recognition.

## Other independent root audit

A new read-only extraction of the original canonical evaluation confirms **50 failing assertions and 99 distinct failing predicates**. All 99 predicates are accounted for by those 50 rows; confidence/hidden global errors are not being mistaken for additional assertion failures. Four ordering assertions remain NE because point dependencies are missing. Exact predicate codes, group and original input hashes are in `e2e_reports/match_001/s01_canonical_predicate_audit.json`.

Preparation still needs qualified same-segment membership; Practical unknown fragments are already retained. Remote interface review rejected the shared-control hypothesis before fitting: source controls share the proposed design and one true remote view lacks it in the selected ROI. Existing remote heuristics cannot supply formal positive identity. Map calibration/assets remain absent for the derived targets. The separate match_002 branch documents a rejected/unadopted geometry candidate and no qualified player identity: it is not transferable subject proof. No unrelated worker branch is changed or incorporated.

## Current acceptance boundary

Original adopted Full: 23/55/4. Original unadopted Full: 28/50/4. New positive PASS gain is unproved. Current production remains exactly PR #46's CI-tested code; this branch changes only analysis/proposal records. No new source recognition, qualification, GT, threshold or event authority is introduced. Existing Linux/Windows CI success at 46584ad applies to identical production/tests, not to a nonexistent new producer. No Full is justified by this proposal alone.

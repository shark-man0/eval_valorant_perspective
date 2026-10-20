# Self Death research recovery and next-main handoff

## Scope and decision

Recovery starts at main `c688206ef4b62c8f206687a1e434fe84833105df` and research
`5ad180a321404333462dc3bdf5d9a322edda1d4c`. Common ancestor:
`7e480c2f2f7f49aea73e1541d065d78881d2f11c`.
The research branch and original stacked PRs are retained, not rebased or merged
as a chain. Only explicit source hunks and applicable tests are recovered.
The PRs linked below retain terminal CI and merge receipts.

Recognition is **B / BLOCKED**, formal Self Death events **0**, confirmed
independent whole-model held-out Death episodes **0**. Current-code canonical
targeted/sampled/Full is **unmeasured**. Adopted **23/55/4** and historical
unadopted Strict **28/50/4** remain historical, distinct results. The different
±0.1s comparison is not a recognizer gain. Safety/transport CI cannot prove
recognition quality or imply a new canonical PASS.

## Stack audit at recovery start

All six PRs were OPEN/Draft; none of their head commits was in start main.
Main already contains native integer-PTS decoding, `VideoService.native_window`,
shared timer/score contracts, the trace field-confidence adapter, source
preflight (#55), and the temporal annotation/exposure contract (#56).

| PR | Base | Head at audit | Own change / inheritance | Recovery decision |
| --- | --- | --- | --- | --- |
| #44 | main | `a067f34` | Global field transport and Preparation association; based on `7e480c2` | Recover field-only Snapshot/Fact path and read-only replay. Exclude Preparation and dataset manifest edits. |
| #46 | `codex/s01-snapshot-field-transport` | `46584ad` | Inherits #44; own production change is legacy temporal ownership guard | Guard and regression tests in [#58](https://github.com/shark-man0/eval_valorant_perspective/pull/58). No #44 code required by guard. |
| #47 | `codex/self-subject-contract-proposal` | `fd39276` | Inherits #44/#46 plus contract proposal `612a4f0`; typed subject probe and scoreboard trial | Preserve on research branch; no qualified runtime adopter. |
| #50 | `codex/self-subject-death-evidence` | `d81f238` | Inherits #47; SelfVictim link and Report episode experiments | Preserve; role/subject semantics and independent qualification incomplete. |
| #52 | `feat/s01-self-death-edge-review` | `ffdf41f` | Inherits an earlier #50 lineage; complete native subject chain | Preserve typed subject-dependent chain; existing main native API already handles decode/PTS. |
| #53 | `codex/self-subject-source-continuity` | `5ad180a` | Inherits #52 and merges edge-review lineage at `b45d130`; image readers, numeric release experiments, replay, research audit | Recover only scoped Fact consumer in #58. Preserve all unqualified producers and research artifacts. |

The #53 merge-base diff includes inherited/sibling work. It must not be read as
all being new #53 recognition work. Source continuity proves source records and
cadence, not the semantics of Self, victim, report absence or death.

## Selected implementation

[#58](https://github.com/shark-man0/eval_valorant_perspective/pull/58) recovers:

* Ownership caller guard from `4e6e02d86a9e8bb8133292832a838b0e93639cef` (#46).
* Scoped Fact consumer from `8f24020f44bf8e73b75f2de2534d031a2533ca98` (#53).
* Explicit positive/negative and Fact → trace → SQLite regression tests.

The independent field transport recovery selects from
`5b441ad35dfa2dadd11b66427d8728784be43e76` and diagnostic/test follow-up
`6ecab454e35507f1a1e5c677488bb5ece54a7211`, frozen at #44 head `a067f34`:

* Keep aggregate HUD >=0.65 and global value >=0.90 contracts unchanged.
* An explicitly unknown, unowned, calibrated, unobscured frame can retain only
  its independently accepted timer/score values at their original PTS and field
  confidence. Owned state, life, weapon, spatial context remain unknown.
* Existing shared timer/score facts remain deduplicated. Score additions are
  appended after legacy facts to preserve their IDs. No score implies life.
* Spatial resolver admission and package timeline completeness retain the
  original aggregate gate; new global snapshots do not widen those contracts.
* Same-PTS duplicate field snapshots are suppressed; current-frame value changes
  are retained. Existing schema and SQLite/checkpoint paths are reused.
* `scripts/diagnostics/replay_snapshot_gate.py` projects saved observations into
  their existing package windows. Expected values and GT are not producer input.
  Original metadata must bind the raw SHA when supplied; unavailable metadata
  is explicitly unknown. Terminal hashes and code fingerprint are checked.
  Outputs must pass the existing private-output check. This is transport replay,
  not recognition, boundary redetection or qualification renewal.

No changes to Preparation association, round boundary qualification, lifecycle
policy, ownership thresholds, GT, validation pack, sampler or main's temporal
annotation dataset are recovered. No public schema/migration change is needed.

## Diagnostics disposition

| Research capability | Decision | Reason / existing main alternative |
| --- | --- | --- |
| Source SHA / native PTS / decoded pixel hashes | Reuse main | Existing native API, source preflight and pixel archive diagnostics; no duplicate decoder. |
| Source-only review / provenance | Reuse main | Existing overview/review-plan tools and temporal annotation contract; hash identity is not semantic proof. |
| Snapshot saved-raw projection | Recover | Independent of experimental readers; narrow transport regression only. |
| Bounded native image-reader replay (`ca4b975`) | Keep research-only | Memory-bounded decoding uses main API, but runner imports experimental killfeed/image/subject classes. Porting it would require the prohibited reader stack or a new generic runner design. |
| Typed native subject chain / episode deduplication | Keep research-only | Depends on #47/#50 subject models; useful tests remain preserved, not production authority. |
| Numeric release, SelfVictim, killer agent, damage, fatal row | Do not adopt | No independently qualified whole-model positive/negative episode corpus. |
| Experimental extra Snapshot-retention patch | Do not revive | Prior investigation showed support already reached final Package/Trace. |

## Reproduce the narrow transport audit

Use only verified saved raw from its recorded source/code/profile/asset environment.
Raw includes private observations; keep raw, selectors and output local and ignored.

```bash
PYTHONPATH=.:src python scripts/diagnostics/replay_snapshot_gate.py \
  --raw /private/run/raw_processing.json --raw-sha256 RECORDED_SHA256 \
  --targets /private/selectors.json --output outputs/private/recovery-transport.json
```

Selectors contain `targets` with `assertion_id`, `target_sec`, `tolerance_sec`.
They select offline diagnostics, not detector thresholds or inferred boundaries.
The aggregate stage applies the original admission predicate; the field stage
adds the independent global path. No events or pre-existing facts are credited
as newly generated by the projection. This cannot independently establish that
an original numeric recognition was correct.

Full E2E is deliberately not repeated: reader/lifecycle code and qualification
are unchanged, and the recovery supplies no new independently qualified Death
hypothesis. Local tests plus Linux/Windows CI check integration; private saved
raw checks are explicitly recorded as transport/legacy regressions, not a new
canonical run. Do not resign the old qualification fingerprint for new code.

## Preserved research and private handoff

Original research source, tests, failures and audit history remain reachable at
[research head 5ad180a](https://github.com/shark-man0/eval_valorant_perspective/tree/5ad180a321404333462dc3bdf5d9a322edda1d4c).
Useful research documents there include `self_death_qualification_handoff.md`,
`self_death_bounded_qualification_workflow.md` and the image/role progress audits.
They are not copied wholesale into main. The research branch must not be deleted.
PR #53 stays Draft as a non-adopted research archive; recovery comments identify
replacement PRs and final merge SHAs. Parent PRs are not rewritten or bulk merged.

Private fixed Profile/NPZ/owner review, runtime/dependency fingerprints, exposure
ledger and original known84 inputs were recovered and transferred via the
user-authorized private Mac route. They are not Git assets. On Mac the isolated
Linux runtime reproduced 84/84 recognition rows exactly after restoring measured
CPU/OpenBLAS dispatch. Native macOS differed in decoder pixels/OCR/numeric
outputs. Fixed-input reproducibility is not independent qualification. Preserve
both the exact original records and the native differences, not just the success.

Existing source2 development/exposed-regression episodes and unknown historical
geometry exposure cannot become a new blind holdout. The private exposure ledger
has the exact PTS/split records; public summaries must not expose names/images/GT.

## Next development baseline and personal application direction

Start a new branch from the final latest main after both recovery PRs merge.
Keep one user = one recorder as the product premise: about ten existing matches,
with new unedited full-match recordings available over time, and optimize for
that personal recording environment. This goal does not redesign recognition.
A single recorder does **not** imply that the current spectator/control target
is self; current-frame ownership and event subject remain different contracts.

Future Self Death adoption still requires source-backed Self/nonself and
killer/victim role positives, player-as-killer and nonself-victim negatives,
continuous death transition and independent time corroboration, persistent/
reopened Report, spectator, respawn, repeated frame and source-break controls.
Freeze new development/holdout episodes before tuning, using exposure history.
Only independent qualification may authorize a formal producer. Then compare
Targeted → fixed Sampled → justified Full with identical evaluator/GT conditions,
tracking PASS→FAIL as well as new PASS. The separate current-state and Preparation
blockers remain follow-up tasks, not implied fixes from this recovery.

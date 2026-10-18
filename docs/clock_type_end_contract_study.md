# Isolated clock-type End contract — DEFER, experiment stopped

The single permitted hypothesis has been tested without production changes. **Do not adopt or release it.** A synthetic Spike→Decimal sequence can form an explicitly unqualified research pattern; saved real fragments cannot establish that pattern with the required active lifecycle and caption-freshness evidence. No independent qualification is issued. No further reader/template/foreground experiment is part of this goal.

## Contract frozen for this study

`scripts/diagnostics/clock_type_end_study.py` is outside production. It returns `Pattern`, never `BoundaryDecision`, Package, Trace or a Formal End. Its `formal_release` is always false. Production fingerprint remains `414f9d9d3f1841cfe50fdf9732bb78e1bfa35aa4382eb7c0d90d194ed81155fa`.

| State/input | Required behavior |
| --- | --- |
| No actual same-source/epoch active Start | Abstain. Synthetic tests may declare an assumed context; real replay cannot inject one |
| Pre-transition | At least100ms adjacent stable accepted old score, positive Spike and positive caption absence; confidence≥0.9 |
| Clock types | Numeric, Spike, decimal and unknown remain distinct; decimal is not numeric countdown seconds |
| Candidate | Actual adjacent +1 score transition after stable old evidence; first observed score tick is the boundary |
| Decimal witness | DD.DD accepted at the score tick or next native frame; no backdating of either score or clock |
| Confirmation | Stable new score, unchanged decimal and new complete caption for≥100ms, within an immutable1s deadline from the score tick |
| Unknown / contradiction | Never fill score. Unknown score after candidate, rollback, missing/changing clock or unsafe UI aborts and discards active context |
| Partial/stale result | Partial is not complete. An already-present caption cannot supply required prior positive absence. A template nonmatch is unknown |
| Source integrity | Exact integer ticks/timebase/source/epoch, native cadence; source break, gap or repeated raster aborts |
| Terminal | Latch after a pattern; no duplicate or automatic restart |

Global-view admissibility is not player identity or ownership. Buy/spectator/unknown/occluded observations reject. The synthetic context hash is an assumption for contract tests, not a source attestation issuer. The module has no production import/call site. Numeric tracker behavior and the1s production horizon remain unchanged.

## Synthetic and adapter tests

31 clock-contract cases pass, including a positive at boundary tick320 and confirmation700 (timebase1/1000); first decimal is tick340. Twenty-four named negative variants cover numeric-only, Spike-only, decimal-only, score-only, clock-only, partial/stale/unknown caption, buy, spectator/unknown view, unknown clock, source break, PTS gap, repeated raster, epoch change, unknown score, score rollback, late caption/decimal, changed decimal, occlusion and weak clock/score. Additional cases cover no active Start, duplicate End, unknown old-score gaps, deterministic nonmutating replay and malformed identities.

Three saved-adapter tests prove a template nonmatch stays unknown, original epoch/context is preserved, and mismatched source pixels refuse a component join. **34 study/adapter tests pass**; combined with the13 text-I/O tests,47 pass. The relevant lifecycle/source/geometry/End set passes156 tests (overlapping, not additional unique coverage). Ruff and classified text-I/O audit pass. These are software-contract checks, not measured real-world sensitivity/specificity.

## Saved-row comparison

`e2e_reports/match_001/clock_type_end_contract_study.json` freezes all input and method SHA256 values. Each component is joined only by the same source pixel/tick. Epochs are retained and never spliced. UI/state observations are historical code58117f2b…; score/timer static observations are code414f9d9d…; the frozen clock reader is99a36c8a… with profileca8aa2a0…. This is a mixed-version component diagnosis, not a current native producer run.

Both collectors receive the same archived score/timer/UI sequence; the proposed collector additionally sees the saved positive clock-type predictions and preserves missing active/global/freshness prerequisites. The baseline collector does not require all proposed safeguards, so candidate counts are **not** an accuracy or regression comparison.

| Development window | Frames | Unchanged numeric collector diagnostic patterns | Proposed research patterns | Formal Ends |
| --- | ---: | ---: | ---: | ---: |
| LOST354–362s |481|0|0|0|
| WON444–452s |481|0|0|0|
| Numeric518–526s |481|1|0|0|

The numeric diagnostic is522.95s, confirmation523.5333333333333s, confidence0.9038290977478027. Numeric support is outside the proposed Spike→Decimal hypothesis. All proposed real replay paths abstain with `no_active_context`; positive caption absence and admissible global context are also missing. Real source feasibility of the full temporal contract therefore remains **unproven**, even though saved source images support its clock ordering premise.

Each collector is replayed twice with identical results and input hashes verified unchanged. No reader/decoder calls, new PNG bytes, GT input, private-image export, Full E2E, qualification or owned facts occur. Aggregate replay CPU time is recorded in JSON (about0.18s locally). Peak RSS was not measured: the optional macOS `time -l` observation failed on sandboxed `sysctl`; this does not affect replay results. The study does not claim a pipeline performance improvement.

Reproduce with the retained private input tree (not included in Git):

```sh
PYTHONPATH=src:. python scripts/diagnostics/replay_clock_type_end_study.py \
  --input-root work/new-source-development --output /tmp/clock-type-replay.json
PYTHONPATH=src:. python -m pytest tests/unit/test_clock_type_end_study.py \
  tests/unit/test_clock_type_saved_replay.py tests/unit/test_unedited_ui_end.py -q
```

The public JSON supplies relative artifact identifiers and hashes, not private raw images/profiles/labels. Replay requires those original files; hashes alone do not reconstruct them. Timing fields vary between runs; semantic decisions and frozen inputs are deterministic.

## Decision and next prerequisite

**DEFER / UNQUALIFIED / EXPERIMENT STOPPED.** StagesA/B establish a proposed contract and deterministic abstention; C does not prove source-backed temporal success. D/E cannot be completed from the exposed fragments. Do not connect the prototype to production or sign an End bundle. E-1 score continuity and E-2 caption lateness remain separate blockers; this hypothesis does not solve them.

The next task is independent data preparation, not another threshold or reader sweep: preallocate at least two unseen physical Spike→Decimal episodes as an engineering replication minimum, independently bracket score/type/caption changes, include real same-epoch Start and complete continuity, and cover every natural negative threat class. This count is not a statistical accuracy guarantee. Confirm exposure/label provenance before prediction; unlisted inventory entries are not certified unseen. See `round_end_blocker_resolution_plan.md` for the exact data contract. Preserve match_002 as independent validation.

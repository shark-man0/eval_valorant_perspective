# R1 transient with the continuous projected-world contract

## Problem

The projected source-world method must cover the actual R1display transient, not only the earlier wall-motion example. Target remains `GT-R1-ROUND-START` and the upstream lifecycle/package contract. Main is `03bfcbf945fbf3d7b04c54d80b3c5ff103475db0`. No production behavior changes or new canonical evaluation occurs here.

## Evidence

The source consists of30native frames/29links from3.902669to4.386003seconds. Every increment is256ticks in1/15360. Video SHA256 remains `71d58558559d6f578433ce9f234bf176f76fd5a86657dbfe3eba1e7d36136b06`. All30full-context world-domain panels were reviewed at640×360, with images1/14/16/24additionally inspected at original1920×1080. Wall domains exclude timer/phase/minimap/FPS/arms through image24. Afterward slash/debris enter the domains and eligibility is conservatively withheld.

[The source/review/code declaration](../e2e_reports/match_001/r1_projected_chain_declaration.json) precedes [the terminal replay](../e2e_reports/match_001/r1_projected_chain_development.json). A new shared Python CLI verifies declaration, its own frozen bytes, source video, all native PNG/pixel hashes and native coverage before/after replay. It consumes no Validation Pack, expected value, timer reader or lifecycle detector. Source masks are explicit offline development reviews, not runtime semantic facts.

## Competing hypotheses

- A visible camera cut occurs when2:25appears: the jointly retained source-world identities, independent camera model and six projected background regions contradict that visible-cut hypothesis on the measured links.
- A transient UI display sequence occurs on a visibly continuous scene: supported by the source evidence below and separately reviewed UI ordering.
- Hidden game time advances through an edit preserving the visible scene: these measurements cannot exclude it. Visible continuity must not be advertised as proof of uninterrupted hidden game time or qualified clock semantics.

## Independent image evidence

Original seed identities, reciprocal flow, original RANSAC consensus>=0.90,bidirectional2pixel final-model errors, seed/adjacent patch NCC>=0.90and three-region quorum remain prerequisites. All fixed flow crops require100%world review at every image. Projected appearance retains the complete source population, accepts only fully reviewed current interpolation taps, and requires valid coverage>=0.90/NCC>=0.90with distributed source/current centers. No excluded timer/phase pixel or clock value influences these measurements.

All six projected regions support the following native links:

| PTS | Separately observed UI | Minimum projected background NCC |
| --- | --- | ---: |
| 4.102669 | Phase disappearance; clock0:00 | 0.995367 |
| 4.119336 | First2:25 | 0.995436 |
| 4.136003 | Second2:25 | 0.943096 |
| 4.152669 | First1:39 | 0.952934 |
| 4.169336 | Continued active display | 0.959535 |

The UI observations label source ordering only; they are not inputs to the tracker or candidate selection. The phase disappears16.667msbefore the first2:25image; first1:39follows the last phase-present image by66.667ms. Every display is retained in the earlier source record; neither2:25frame is skipped or repaired.

## Continuity decision

The integrated diagnostic supports22/29links through4.269336, including all critical native frames, and favours visible scene continuity with a transient UI sequence. It fails the original model-consensus prerequisite at4.286003 (`seed_model_incoherent`) and terminates; later frames never rejoin. It does not loosen that floor or classify unsupported images as cuts. No independent qualification, trusted producer, clock repair or boundary follows from training support.

## Contract change

No new tracker/model/threshold change is made in this checkpoint. The frozen projected mode is evaluated as implemented. `replay_reviewed_projected_chain.py` supplies portable, new-output-only orchestration with explicit source/code/pixel/native-coverage checks. It creates a development report with `runtime_proof_authorized=false`; it does not install a profile or emit events.

The existing proposed `pre_round → transient_ui_transition → round_active` contract can retain all visible displays and await qualified active-clock corroboration. Production still needs image-derived world bootstrap/current occlusion and qualified positive UI-transition evidence. Offline per-frame annotations must not be copied into runtime truth, selected by GT timestamps, or used to establish player ownership.

## Tests

Current Ruff passes `src tests scripts/e2e scripts/diagnostics`; `git diff --check`passes. The preceding53related unit cases passed10.41seconds and fresh mypy passed102production files. Tracker/review/appearance bytes are unchanged since that verification; this checkpoint adds only the shared replay runner and data/docs. The actual30-frame replay exercises source/code/pixel/coverage binding and termination, and [verification](../e2e_reports/match_001/r1_projected_chain_verification.json) binds these results. No need to repeat unchanged suites or203-link default-equivalence replay. Windows execution remains unverified; orchestration is shared Python/pathlib/OpenCV with no OS-specific acceptance rule.

Reproduce with a new output filename:

```bash
python3 -m scripts.diagnostics.replay_reviewed_projected_chain \
  --declaration e2e_reports/match_001/r1_projected_chain_declaration.json \
  --output outputs/r1_projected_chain_replay.json
```

The frozen code bindings must match; stale declarations cannot qualify changed code.

## Previous / Current / Delta

| Comparable R1development metric | Previous same-input final-membership method | Current projected-world contract | Delta |
| --- | ---: | ---: | ---: |
| Native frames | 30 | 30 | 0 |
| Adjacent links | 29 | 29 | 0 |
| Supported links | 22 | 22 | 0 |
| Qualifications created | 0 | 0 | 0 |
| New runtime events | 0 | 0 | 0 |

The replay completed in9.819518seconds. Earlier9.854874seconds includes different passive model/stage instrumentation, so a runtime performance delta is not comparable. Identical support count does not erase the stronger explicit source/current eligibility and projected-appearance provenance; it also does not establish accuracy improvement.

Canonical historical23PASS/55FAIL/4NEand negative/discontinuity0/0remain the accepted baseline. Current/Delta are unmeasured. All82stored assertion statuses remain unchanged; no new PASS, event or package is claimed. No targeted, sampled or full canonical E2E was run because trusted scene/UI and the three-boundary gates remain incomplete.

## Remaining blocker

The next production-facing task is image-derived bootstrap of reviewed world reference identities and current occlusion eligibility. A timestamp/hash-indexed annotation lookup is not a recognizer and is prohibited as runtime truth. Reference matching must use independent world structure/current pixels without timer/GT values, and carry qualification/fingerprint provenance. Freeze that method before disjoint holdout/negative-control assessment; all existing R1/wall cohorts are exposed development. The source contract now has direct evidence across the transient; adding timer/score threshold variants or relaxing the4.286003consensus failure is not the next step. R2start/result-banner qualification remains separate. Overall lifecycle/package/evaluator completion is still unproven.

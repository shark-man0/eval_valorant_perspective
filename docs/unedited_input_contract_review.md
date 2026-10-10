# Unedited input contract review

## Problem

The user guarantees that the current validation video has no intentional edits,
frame deletion/join/reordering or speed changes. Scene-preserving edits are
excluded by that input contract, not by an image-recognition test.

## Contract and removed prerequisites

`datasets/input_contracts/match_001.unedited.json` binds the assurance to video
SHA256 `71d58558559d6f578433ce9f234bf176f76fd5a86657dbfe3eba1e7d36136b06`.
The loader requires explicit true claims, provenance and an exact hash match.
Runtime orchestration must explicitly receive `--unedited-input-contract`; it
does not infer assurance for other videos.

With that contract, global lifecycle qualification requires `timer`,
`purchase_phase` and `ui_transition`. Edit-oriented `continuity` and paired
`scene_continuity` qualification are no longer mandatory for this route. World
feature correspondence, foreground animation classification and scene-preserving
edit exclusion must not become additional start gates merely to re-prove the
assurance. The route without an assurance retains its existing requirements.

Recording loss, native cadence, monotonic PTS, source epoch, repeated source
pixels, source integrity, explicit discontinuities, invalid/occluded scans and
menu/spectator conflicts remain guarded. Assurance does not qualify OCR or
establish player identity/ownership. NCC 0.90, reader acceptance, qualification
split/support checks, validation assertions and full sampling remain unchanged.

## Evidence and continuity decision

The existing current-producer replay processes all 30 native R1 development
frames from 3.902669 to 4.386003 seconds. The producer supplies current-frame
phase presence separately from its debounced phase flag. Unconfirmed positive
phase text cannot masquerade as phase disappearance.

The retained timer observations include `0:00 → 2:25 → 2:25 → 1:39`.
Phase disappearance proposes a transition at 4.102669270833333 seconds; coherent
accepted timer support begins at 4.152669270833333 and confirms the candidate at
4.202669270833334. These are observed outcomes, not production constants or GT
inputs. Source/PTS discontinuities reset the tracker; a timer inconsistency alone
restarts clock corroboration without declaring an edit or deleting the display.

## State and release contract

`pre_round → transient_ui_transition → round_active_candidate` retains every
observed display and its provenance. Existing minimum-duration and confidence
rules corroborate the later clock. Duplicate suppression remains latched until
a qualified lifecycle end/rearm or source break. This is a system-only candidate
path; it cannot establish owned HP, weapon, death or shot facts.

## Tests

Review on HEAD `e9ecaf8f2f0f0dfa1f9433d40a598ec8909e9ce3` with the existing
working-tree implementation:

```bash
PYTHONPATH=.:src python3 -m pytest -q \
  tests/unit/test_unedited_ui_start.py \
  tests/unit/test_native_assured_start.py \
  tests/unit/test_qualified_ui_transition.py
python3 -m mypy src
```

115 tests passed in 68.01 seconds; mypy passed on 121 source files. Ruff passed
on these tests and the input-contract, start-tracker, qualification and assured
producer modules. This review changed documentation only; no reader/profile,
threshold, ground truth or assertion was changed.

## Previous / Current / Delta

The saved current-producer replay reports one R1 start candidate before and after
the raw phase guard (delta 0), and zero released events (delta 0). This review did
not rerun that image workload or create qualification. Canonical baseline remains
23 PASS / 55 FAIL / 4 NE; a new canonical Current/Delta is unavailable. Canonical
negative assertions have not been reverified by this review.

## Remaining blocker

Independent temporal qualification and gated canonical verification are still
required before releasing the observed R1 candidate as a production round-start
event. Previously exposed development frames cannot be relabeled independent
holdout. No additional edit-proof gate or extra-video prerequisite is introduced.
R1 end evidence/timestamp semantics remain a separate blocker. No new full E2E
was run for this contract review.

Evidence: `e2e_reports/match_001/current_phase_presence_guard_summary.json` and
the source-bound reports it references. Further detail is in
`docs/unedited_input_lifecycle.md` and `docs/current_frame_phase_contract.md`.

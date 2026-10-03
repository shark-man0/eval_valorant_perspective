# Weapon consensus observability review

The proposed observability relaxation is not supported by this recording. The detector remains unchanged: every learned group must be observable and score at least 0.90 at one common current-frame offset within ±1 px. No observable contradiction is ignored, and missing evidence never becomes positive evidence.

## Reproducible evidence

The starting implementation is `5e0f05969eb2b88c77ef6e1ab3ac036bdd471359`; the worktree was clean. Source hashes match the previously evaluated implementation. A completely fresh 64-sample profile reproduces all reference, mask, support and allowed-region hashes, and all generation diagnostics. The same 258 analyzer-derived frames reproduce Weapon missing 142, HP missing 18, Ability missing 75, live accepted 86, structural insufficiency 158 and explicit blockers 14.

All nine existing common offsets were evaluated on each of the 35 visually valid Weapon rejects and 80 former false accepts. The source result and saved score/offset agree for all 115 frames. Images, per-frame records and candidate grids remain private; this review includes aggregates only. Validation Pack timestamps, OCR, expected ammo values, and semantic vision were not used.

## Cause categories

Categories A–E may overlap. F counts a center-to-best change in the pass/reject decision within the existing alignment contract, rather than asserting that every conceivable transform was tested. G is the complement of the measured categories.

| Category | Visible rejects /35 | Former false accepts /80 |
|---|---:|---:|
| A_all3_observable_at_least_one_score_below_0_9 | 27 | 6 |
| B_two_matching_one_unobservable | 0 | 0 |
| C_one_matching_two_unobservable | 0 | 0 |
| D_all_three_unobservable | 0 | 59 |
| E_any_observable_contradictory | 35 | 21 |
| F_pm1_search_changes_center_pass_reject | 0 | 0 |
| G_other | 0 | 0 |

All 35 visible rejects contain an observable contradiction: 27 have all three groups observable, and eight additionally have group 1 unobservable. No frame has exactly two matches and one unobservable group, at the runtime winner or at any of the nine permitted offsets. There is no such case in the 80 former false accepts either. A two-match redundancy rule would recover zero of these 35 frames.

Among the former false accepts, 59 have all three groups unobservable; the other 21 contain observable contradictions. Six of those 21 have all groups observable. No group matches in this negative cohort. Geometry/crop shapes are valid and bounded alignment recovers no positive in either cohort.

## Group status and score distributions

Each distribution lists min, p25, median, p75, max at the common winning runtime offset. Observable equals matching plus contradictory; observable plus unobservable equals the cohort size.

### Visible rejects (35)

| Group | Observable | Matching | Contradictory | Unobservable | Score | Grayscale std | Contrast std |
|---|---:|---:|---:|---:|---|---|---|
| 1 | 27 | 5 | 22 | 8 | 0.0000, 0.3240, 0.6251, 0.8051, 0.9770 | 1.3299, 7.5533, 47.5896, 61.4688, 76.4304 | 1.1178, 7.9670, 24.7252, 31.2205, 53.5425 |
| 2 | 35 | 9 | 26 | 0 | 0.2544, 0.6664, 0.8055, 0.8992, 0.9973 | 9.0833, 51.3001, 64.3764, 75.9727, 85.4156 | 5.0767, 25.4544, 43.1760, 59.2345, 70.9603 |
| 3 | 35 | 13 | 22 | 0 | 0.3915, 0.7310, 0.8599, 0.9461, 0.9971 | 30.2810, 66.2634, 69.2794, 74.1966, 81.4039 | 19.2800, 44.3908, 51.8094, 56.9612, 60.1115 |

Common winning (dx,dy) counts: `{"(0, 0)": 30, "(1, -1)": 2, "(0, 1)": 2, "(0, -1)": 1}`.
Limiting group counts: `{"1": 28, "2": 4, "3": 3}`.

Individual group best offsets, diagnostic only (these offsets are not combined to accept a frame):

- Group 1: `{"(0, 0)": 30, "(1, -1)": 1, "(1, 1)": 1, "(0, 1)": 2, "(0, -1)": 1}`
- Group 2: `{"(0, 0)": 35}`
- Group 3: `{"(0, 0)": 35}`

### Former false accepts (80)

| Group | Observable | Matching | Contradictory | Unobservable | Score | Grayscale std | Contrast std |
|---|---:|---:|---:|---:|---|---|---|
| 1 | 18 | 0 | 18 | 62 | 0.0000, 0.0000, 0.0000, 0.0000, 0.1444 | 0.5591, 2.8586, 3.7203, 7.3772, 72.8525 | 0.0000, 0.2919, 0.5606, 2.8425, 28.3978 |
| 2 | 17 | 0 | 17 | 63 | 0.0000, 0.0000, 0.0000, 0.0000, 0.2264 | 0.3909, 2.8539, 3.8586, 7.3837, 76.4459 | 0.0830, 0.3073, 0.4522, 2.5741, 27.2925 |
| 3 | 8 | 0 | 8 | 72 | 0.0000, 0.0000, 0.0000, 0.0000, 0.2402 | 0.4978, 2.9308, 4.0825, 6.4640, 68.7790 | 0.0720, 0.3246, 0.5226, 1.4876, 30.5049 |

Common winning (dx,dy) counts: `{"(0, 0)": 76, "(1, -1)": 2, "(0, -1)": 1, "(-1, 1)": 1}`.
Limiting group counts: `{"1": 69, "2": 7, "3": 4}`.

Individual group best offsets, diagnostic only (these offsets are not combined to accept a frame):

- Group 1: `{"(0, 0)": 64, "(-1, 0)": 3, "(1, -1)": 3, "(-1, 1)": 4, "(-1, -1)": 3, "(1, 1)": 1, "(0, -1)": 1, "(0, 1)": 1}`
- Group 2: `{"(0, 0)": 65, "(1, -1)": 3, "(1, 1)": 3, "(-1, -1)": 4, "(-1, 1)": 3, "(0, -1)": 1, "(1, 0)": 1}`
- Group 3: `{"(0, 0)": 74, "(0, -1)": 3, "(-1, -1)": 1, "(-1, 1)": 1, "(1, 1)": 1}`

## What observability can and cannot prove

Variance detects insufficient local contrast; it does not prove that a Weapon feature is physically visible. Both the washed-out real group and a frame without Weapon HUD can have low variance. Conversely, background texture can have high variance while disagreeing with the frozen shape. The meaningful negative signal is observable shape contradiction, not variance alone. Keeping the strict rule requires no new recording-specific constants.

Prior local visual inspection found all three icon columns discernible in the 35 frames: 32 over bright gold/cream gloves and three over a cyan weapon. Eight low-contrast left columns were still faintly visible. These are visual associations, not proof that one specific extraction stage causes every mismatch. The data does not justify redefining these observable contradictions as unobservable to increase recall.

## Runtime contract and next target

The implementation retains training-only persistent feature discovery, multi-frame consensus, holdout-only validation, dynamic-number and neighbor exclusion, no underline evidence, ±1 px common alignment, and current-frame matching. HP, Ability, Spectator and live_identity() are unchanged. Dedicated tests pin two matches plus unobservable to rejection, two matches plus contradiction to rejection, and insufficient evidence to rejection.

The next recommended diagnostic target is Ability, as requested for the unsupported-relaxation outcome. Its 75 comparable misses need their own visibility and cause audit. Weapon still has 35 visible shape mismatches and 142 total misses; this task does not claim to have resolved them or to have proven that Ability is numerically the largest blocker. A later Weapon representation change would require separate evidence and negative separation.

## Clean validation procedure

Commit this review and the rejection-semantics tests before running the full recording. Verify an empty git status and record that validation commit. The E2E metadata must record that commit and git_is_dirty=false. Commit only the bounded generated E2E reports afterward, then fetch and fast-forward push the validated HEAD to origin/main without force. The report commit intentionally follows the clean analyzer commit.

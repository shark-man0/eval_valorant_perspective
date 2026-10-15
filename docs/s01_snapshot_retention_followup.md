# S-01: Complete-path confidence-retention follow-up

## Problem and hypothesis

The Goal requires investigation beyond the first snapshot gate. On the completed current-code full raw, `_state_snapshots()` alone suppresses 357 normal-HUD observations with at least one stronger field confidence than its previously retained snapshot. This suggested a second transport defect related to #23. This count describes the intermediate function only, not final lost evidence.

Start main remains `7e480c2f2f7f49aea73e1541d065d78881d2f11c`; inspected S-01 production is `6ecab454e35507f1a1e5c677488bb5ece54a7211`. Latest `origin/main` was fetched and confirmed unchanged. The current full raw digest is `5bc81be4ed43e45db025548d236c416d24efe35fa2ab95a32260f5a4fa94a6dc`. No PR #42 changes are incorporated or overwritten.

## Independent downstream check

Follow every one of the 357 source PTS through the actual saved native packages and canonical trace. All are already present. For all 740 stronger field supports, native `source_confidence[field]` and trace `source_confidence_by_field[field]` exactly equal the current source observation's support. Missing downstream observations: **0**.

The recovery occurs in `_merge_visual_snapshots()`'s resolver loop. The full run has a resolver row at each main frame. For an eligible current HUD at that same source PTS, the loop builds a single-observation snapshot even when location resolution is unknown. This preserves the source HUD fields without asserting a map location. It is not legal to infer complete-path loss from the first-stage dedup result alone.

## Competing hypothesis / experiment

In an isolated worktree, test an additional high-confidence retention path that keeps all original periodic points, never combines confidence from different frames, and leaves gates unchanged. Its focused regression group passes 80 tests, but these are explicitly **experimental tests**, not evidence that adoption is needed.

Replay the same hash-verified raw through the original and experimental complete package builders and the unchanged canonical evaluator. All original snapshots remain exact, but final package/trace populations and all 82 assertion statuses are unchanged. The existing complete path already supplies the supposedly missing source evidence.

| Metric | Before | Experiment | Delta |
| --- | ---: | ---: | ---: |
| R1 snapshots | 3054 | 3054 | 0 |
| R2 snapshots | 2281 | 2281 | 0 |
| Canonical PASS | 28 | 28 | 0 |
| Canonical FAIL | 50 | 50 | 0 |
| NE | 4 | 4 | 0 |
| Negative failures | 0 | 0 | 0 |
| Source-break spans | 0 | 0 | 0 |
| Regressed PASS IDs | 0 | 0 | 0 |

Saved-raw two-builder replay: 168.36 s, peak process RSS 405.55 MiB including loading and both builders. No new recognition or Full E2E was run. Historical raw/profile/code/qualification identities remain original; nothing is re-signed as experimental recognition.

## Decision

**Reject the hypothesis of a remaining downstream confidence loss for these 357 observations. Do not adopt the experimental production change for this E2E.** Archive the trial and restore production byte-for-byte to the full-tested S-01 source. Recognizer fingerprint is again `ad482fe1bae0f2c4401ce0364841f749f63c6e2230ff75c49cf853962c8eb859`. Existing code-bound qualification is not invalidated by a speculative patch. No threshold, sampler, GT, assertion, profile asset, schema, ownership or source-continuity policy changes.

This does not prove that every consumer without resolver rows preserves every intermediate high-confidence observation. That narrower API concern remains distinct from demonstrated canonical failure and must not be described as an E2E fix.

## Remaining producer evidence

The remaining preparation scope needs an uninterrupted, qualified preparation episode connected to a native lifecycle boundary within the same source segment; Practical unknown fragments are already retained. Do not bridge the recorded source breaks.

The death and owned-visual clusters need independently qualified player subject/ownership plus temporal corroboration. Existing source output has no structured killfeed/report readings supplying the needed attributes; wrapping previously rejected bare OCR text or a persistent report cannot establish self-death. Remote-state controls already reviewed are not discriminative. Strong global score/timer support cannot supply these missing conditions.

The local video inventory contains only match_001. It does not add new independent holdout evidence. Required future evidence is concrete: source-bound current identity references/masks with all four independent anchors, disjoint qualification/negative samples, self-subject and killer/victim role evidence for death, and mode-specific remote-state evidence that survives ordinary-world/menu/smoke controls. Existing exposed development frames must not be relabeled as new blind holdout. Additional source acquisition is one option, not an automatic prerequisite for every remaining diagnostic.

Adopted baseline remains 23/55/4; current unadopted source full remains 28/50/4. This follow-up corrects a causal classification; it claims no additional accuracy improvement. Windows real-video qualification and the unresolved producer predicates remain unverified. S-01's prior Linux/Windows CI belongs to its recorded code commit; this follow-up changes documentation and sanitized metrics only.

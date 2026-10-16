# Native source continuity for experimental Self Subject linking

Start main: `7e480c2f2f7f49aea73e1541d065d78881d2f11c`.
This branch started from PR #50 at `3e27b0f` and incorporated its subsequent `a20e0b5` update, preserving the PR #44/#46/#47 work and the separate Round work. It changes no production HUD, ownership, lifecycle, Fact, Package, Schema, trace or evaluator behavior.

## Problem and evidence

PR #50 adds two-episode visual review and a non-releasing source-player/victim linker. Its endpoint source context and bounded time horizon do not themselves retain all intervening native evidence. A diagnostic caller must also prove it did not skip a frame or combine across a known break. This follow-up adds that explicit check without promoting experimental observations.

The original review verifier was executed once against the original SHA-identical video. It failed closed at the first decoded pixel hash comparison (frame index 4434). The review records OpenCV 4.13.0; this Pi has 4.14.0. The decoder difference is **not a proven explanation** of the mismatch. No original hash was changed, and no claim is made that the 17 original review rasters were verified locally. Re-running a semantic label verifier cannot fix this by accepting similar images.

Instead, the previous private structural scoreboard profile and fixed victim text crop were frozen without tuning, and four explicit source windows were decoded with the native production decoder. Every frame in those windows was processed, with actual native PTS, decoded-pixel hash, decode epoch, code/profile and dependency fingerprints. All selected contexts were previously exposed. These are development/regression measurements, **not new blind holdout**.

Two archived native rasters were also checked against the new decoded pixel hashes and visually inspected. The first contains death animation and a partially displayed report; the second contains death animation and the self-referential report heading. These observations neither transfer all old review labels automatically nor qualify an autonomous role/edge reader.

## New diagnostic contract

`experimental/subject_continuity.py` composes the existing PR #50 linker with a complete typed `ProbeFrame` chain. Both exact endpoint observations must occur in that chain. Intervening source context must remain identical; native PTS must be ordered at the supplied source cadence, previous-PTS links and proof hashes must exist, and repeated pixels or declared discontinuities reject the join. The cadence is an input source contract, not inferred from widely separated endpoints. Reordering, missing records or substitutions remain unknown even when the endpoint segment labels agree.

The diagnostic result retains native source/proof records for audit, including rejected records. A successful chain only allows the existing **unqualified** name-agreement candidate. Relation remains UNKNOWN and review remains CANDIDATE. Output always says `qualified=false`, `content_continuity_qualified=false` and `formal_events=[]`. A pixel-pair digest is a source audit record, not independent semantic content-continuity qualification. No event actor or player-owned state is modified.

The upstream PR #50 update includes the variable-length blocker tuple annotation needed by mypy and its non-releasing report/victim episode model. Both are preserved; this follow-up does not duplicate that model or use its diagnostic similarity cutoff to qualify an event.

## Real native replay

The frozen replay processed 96 frames in **204.324 seconds**, including native decoding, unchanged scoreboard and text readers. Source and asset terminal hashes passed. Peak memory was not measured. The reader fingerprint remains attributed to that execution; the later continuity check is separately hashed postprocessing of preserved raw records, not new recognition or re-signing.

| Source context | Native frames | Marker candidates | Accepted victim-crop text | Unqualified name-agreement pairs | Formal Death |
| --- | ---: | ---: | ---: | ---: | ---: |
| First episode, exposed | 24 | 0 | 7 | 0 | 0 |
| Second episode, exposed | 48 | 7 | 30 | 204 | 0 |
| Persistent report control | 12 | 0 | 0 | 0 | 0 |
| Spectator/report control | 12 | 0 | 0 | 0 | 0 |

No cadence/repeated-pixel break was observed within these four windows. This does not certify continuity between windows. Six same-frame owner/victim pairings are rejected by the existing independent-frame guard. The 204 other combinations are **correlated observation pairs from one episode**, not 204 deaths or 204 independent correct classifications. No name/role labels or GT values were passed to a reader.

The first episode's accepted crop text agrees with the later second episode's marker name. This is diagnostic text agreement only: it is not used to bridge their source segments, supply the missing first-episode local binding, or establish current player ownership. Source-local identity support remains a real blocker in the first window.

Both control windows emit no source-player or Death candidate. That is a bounded abstention result, not an independently measured perfect false-positive rate: nonself killer/victim role negatives and independent positive episodes remain unqualified. The existing Death probe remains unknown throughout all 96 frames because Self role qualification and independent death-transition evidence are absent.

| Metric | Previous | Current | Delta |
| --- | --- | --- | --- |
| Complete native reader/link replay | Unmeasured | 96 frames | Not comparable |
| Continuous-chain check of preserved pairs | Unmeasured | 204 unqualified, 6 unknown | Not comparable |
| Qualified Self subjects | 0 | 0 | 0 |
| New formal Death outputs | 0 | 0 | 0 |
| New canonical recognition PASS/FAIL/NE | Unmeasured | Unmeasured | Unmeasured |

The adopted Full remains 23/55/4, archived unadopted Full remains 28/50/4, and PR #48's separate evaluator-policy comparison remains 30/49/3. None is relabeled as a new recognition result. No new targeted formal Death E2E, sampled qualification or Full was run: the missing positive qualification still prevents formal event release. Re-running the unchanged production recognizers would not test this diagnostic chain contract.

## Tests and next gate

Synthetic controls exercise complete source retention, missing/reordered/duplicate native frames, interior source context changes, absent proof, wrong previous PTS, repeated pixels and substituted endpoint observations. Existing role/name/ownership/model guards are retained. After incorporating upstream PR #50, the related local suite passes **138 tests in 12.61 seconds**, Ruff passes and mypy passes **139 source files**. Linux/Windows CI results are recorded on the follow-up PR.

Next establish an independently qualified victim-role reader and a source-local Self binding, then independently corroborate an actual death-transition edge. Persistent report, spectator or a name match alone cannot supply that edge. Continue with frozen source-backed negative controls; do not relabel either exposed episode as a blind positive. Any formal production adoption remains subject to the user's additional approval. Private images, names, profiles, full raw observations and review labels stay local; the committed JSON contains hashes and aggregates only.

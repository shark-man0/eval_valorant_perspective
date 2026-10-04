# HUD numeric safety and close-anchor review

## Reproducibility

Starting shared commit: `b7e41d77f69e0840cdd604d29489e7f29d5ac4f2`. Production analyzer remains `3e9df3dab16d6dce83f3973f0386638d11286c0c`. Video SHA256: `71d58558559d6f578433ce9f234bf176f76fd5a86657dbfe3eba1e7d36136b06`. Active profile sidecar SHA256: `8e764d6eb2b7a6a8ce6a5f144300bdf809f16f9dcf2b689ac659333c2265b615`. Canonical configuration SHA256 (sorted compact JSON payload, excluding its hash field): `1a5d499513305fc6b6061a20767ce6a9da88f9d358e5d75e23f71ea1d84b8b40`; candidate runtime SHA256: `d26b1ca92fe46ae475f226f86405800f0a553e391631707505c8d3de790e2463`.

The freeze JSON file-byte SHA256 is `acf6b7bd3c3e18e65e125bad127d79c1f896e399a90c9bc5e2b1566807b6399f`; its semantic configuration hash above has a different, explicitly verified meaning. The source worktree was clean at the start. No production source, active profile, identity gate or threshold is changed. Images, timestamps, individual labels, reference assets and per-frame dumps remain private. Same-recording samples do not establish independent recording or Agent generalization.

## Hash-ledger correction

Earlier four/five/six-pool unique counts of 274/298/322 were incorrect. The original 72 and expanded 96 annotation hashes used encoded PNG bytes; subsequent pools used contiguous decoded BGR pixels. Normalizing every source image produces **268/291/315** unique decoded crops, respectively. Two additional uncertain crops produce 317 reviewed unique crops from 346 annotation rows. There are zero contradictory non-null numeric labels and zero absent-versus-visible duplicate contradictions. Three earlier exact-image adjudications remain separate preserved overrides.

The canonical private ledger SHA256 is `d16521eae0e353d5aad4e3b985d0ca64df706a18934b2d5b465d73d2126abd93`. Independent decoding of the saved even cache gives 2,023 unique crops, 220 intersecting the 317 reviewed crops, and 1,803 unreviewed crops. The latest 24-item morphology challenge adds exactly 24 crops to the earlier 291. The historical aggregate counts are superseded; their image-level measurements need individual provenance checks rather than blanket invalidation.

## Frozen Ammo holdout

The candidate keeps field-local Otsu, all foreground components, border rejection, complete 0–9 competition, .90 top-score/.04 margin, and a six-component cap/stem separator. Role medoids add current 1/2 and reserve 3/6 references. No values provide identity evidence. The separator uses training-derived geometry; an earlier interim centroid-versus-top implementation must not be conflated with this frozen code. A reproducible BGR-to-gray replay matches all 168 preserved separator statuses (44 accepted, 124 rejected, zero mismatch). Direct grayscale decoding instead changes one status; the frozen code keeps BGR-to-gray. Missing historical generator AST limits source-level equivalence claims.

An image-only review preceded candidate scoring on 69 odd samples. Their exact pixels are disjoint from the canonical even ledger. The 41 legible pairs comprise 19 clean and 22 readable foreground/background overlaps; 24 samples have no numeric display and four are uncertain.

| Frozen method | Correct current /41 | Correct reserve /41 | Correct complete pairs /41 | Wrong complete pairs | Absent/uncertain accepted /28 |
|---|---:|---:|---:|---:|---:|
| Generic bank | 14 | 1 | 0 | 0 | 0 |
| Role medoids + separator | 14 | 16 | 6 | 0 | 0 |

All six complete accepts are clean. All 22 overlap positives are rejected by the complete candidate. Separator outcomes on all 69 are 18 accepted, 48 border-contact rejects, two component-count rejects and one geometry reject. This is a limited holdout; zero observed errors does not prove general safety.

The six accepted images have exact decoded-ROI matches in the latest committed-source Clean E2E. Five are UNKNOWN and one is Spectator; none is self-owned live. Their numeric matches therefore provide zero safe native fact opportunities.

## Actual current-owned opportunities

The same frozen candidate, without refitting, accepts 31 of the latest 166 current-owned live observations. A separately frozen, shuffled image-only review verifies all 31 complete values. Pair-minimum NCC ranges .9021–.9756 (median .9452); pair-minimum class margin ranges .1671–.2773 (median .2587). This is a score-selected opportunity audit, not an unbiased holdout. The remaining 135 rejections are not labelled in this audit.

These opportunities show possible native benefit but are not production facts. Numerical confidence must remain separate from geometry/HUD confidence, and current/prior numerical confidence and ownership continuity must reach Visual before Ammo-delta inference. Current-frame identity gates remain mandatory.

## Accepted-pool audit and invalid intermediate join

Among the 1,803 previously unreviewed even crops, the generic bank accepts 230 current fields: nine single-component and 221 two-component cases. A morphology-selected 24-item audit includes all nine single-component cases and fifteen multi-component cases. On the immutable, exact-hash re-review, all 24 current values are correct; candidate reserve has seven correct and seventeen UNKNOWN, and the complete candidate has three correct and twenty-one UNKNOWN. No wrong values occur. All 24 contain legible numeric text; this sample supplies no no-number hard negatives and does not evaluate all 230 accepts.

An initial review read contact sheets during regeneration, then joined those labels against the completed selection. This produced spurious claims of twelve current errors and one wrong complete pair. Those annotations, joins and mechanism claims are retained privately with invalid markers. They are **not detector-error evidence**. The corrected review binds PNG hashes, decoded BGR hashes, manifest and contact-sheet hashes; rerunning predictions on immutable copied pixels exactly reproduces the frozen predictions. Predictions had already been exposed, so the corrected audit is not blind validation. Freeze-ready notification and immutable image/hash snapshots are required before future annotation.

## Close-anchor mechanism

The actual production buy close-anchor has no learned reference asset. It uses the configured 93×95 top-right ROI, Canny and opposing Hough diagonal signs, with minimum line length 23 pixels and a 31-vote threshold. The separate possible-obscuration hint uses five-pixel lines and eight votes. On 524 globally obscured local-portrait candidates, the broad hint fires 418 times and strict anchor once. Broad-hint recomputation matches all 4,081 saved observations.

Measured real X edges often split into short segments; strict extraction fails to obtain both signs on the inspected X examples. Conversely, an inspected strict hit is diagonal world structure without an X. Broad-hint examples also include non-X world/hand texture. Simply copying the broad veto into positive buy evidence would be unsafe.

A diagnostic-only fixed center-patch matcher, frozen at .90 from three even examples, matches eight already-exposed X examples and rejects four already-exposed world/hand controls. These are development results. Eight odd midpoints and an expanded 24-item odd hint/control sample provide no clear X positives; there is no independent positive holdout yet. A frozen representation challenge with actual X positives and hard diagonal controls is the next experiment. Local X presence, buy-grid evidence, portrait appearance and primary view mode remain separate.

## Verification and decision

Full pytest in the existing UTF-8/configured-validation-pack environment: **830 passed /2 skipped**, 290.16 seconds. An initial invocation omitted those settings and produced two CP932 decoding failures and five environment skips; the corrected invocation passes without a source change. Ruff `src tests scripts` passes; mypy passes on 86 source files. Diff/privacy checks are recorded in the metrics companion.

No new Clean E2E is run for this diagnostic-only phase. The latest source Clean E2E remains **22 passed /56 failed /4 not evaluated**, negative **20 passed /0 failed**, `git_is_dirty=false`.

**Decision: NEED MORE EVIDENCE.** Keep production unchanged. Continue with frozen Ammo completeness/foreign-texture stress, a close-X positive/diagonal-control challenge, and a concrete numeric-confidence/ownership integration contract. The global goal remains active; these are selected next experiments, not a request for user direction or a declaration of completion.

# Round End temporal data preparation — final readiness, 2026-10-20

**Decision B: BLOCKED for independent Formal End qualification.** The bounded data preparation work now includes actual independent source reviews and a validated private freeze. Formal End remains unqualified. This report supersedes the pending-review snapshot of 2026-10-19; no recognition qualification or Full E2E was run.

## 1. Git and scope

Starting main: `ba90c0ba05185642265d269979d7a0cb25c9e517`. Branch: `codex/round-end-temporal-data-contract`. Draft PR: [#56](https://github.com/shark-man0/eval_valorant_perspective/pull/56). Production and offline validator code remain unchanged from `b515771`; this final update adds reviewed-data counts, hashes and documentation. Current PR HEAD and checks are reported by the PR, rather than embedding a self-referential commit hash here.

No production confidence/timer policy, source decoder, canonical GT or separate PR48 tolerance was changed. No research PR or main merge. Issue16 remains open. The canonical **23 PASS / 55 FAIL / 4 NE** baseline is unchanged.

## 2. Exposure audit and split

The available-history audit covers **4 recordings**, **825 saved JSON artifacts**, **952 historical tool calls**, **64 resolved actual image-view calls** and **87,224 frame-evidence rows**. Duplicate evidence is retained and is not counted as independent samples. The historical normalized ledger has **408 evidence records / 397 source-artifact groups**, representing all ten exposure categories. Original source/profile/assets and reference-parent lineage remain only partially reconciled.

The user confirms exclusive use of the two supplemental recordings in this chat. Fresh pool eligibility uses that assurance together with the available complete acquisition/tool history, saved diagnostics and resolved image views. Git absence alone is not proof of no exposure. This is a scoped provenance conclusion, not an assertion that unavailable external history is known.

There are **8 mapped historical development episode units** and **2 newly reviewed display-change episode units**. The machine dataset has **17 event/scope records**, not 17 independent physical events:

| Record category | Count | Interpretation |
| --- | ---: | --- |
| Historical development physical episode units | 8 | Already exposed; two have unresolved historical caption responses |
| Historical development exposure scopes | 4 | Physical identities unresolved; excluded from physical-event counts |
| Reserved, reviewed display-change positives | 2 | Narrow source-display bracket target only |
| Reserved candidates still unknown | 3 | Retained, not discarded or converted to negatives |

Thus development has 12 records representing 8 mapped episodes plus 4 unresolved scopes. The 5-candidate reserved cohort is now **2 narrow positives / 0 negatives / 3 unknown**. There are 10 mapped physical identities and 7 unresolved candidate/scope identities. The sealed recording is a source reservation only, with no invented event coordinates or verified timebase; its Pack/images/GT remain unopened.

A real validation failure exposed one private aggregation error: a historical file containing sparse points had been represented by its minimum/maximum interval. The original candidate still fails `exposed_holdout`. The corrected dataset retains all **1,149 actual points** for that source, including their unknown usage, instead of filling unobserved gaps. It preserves the original index, failed candidate and correction provenance. The validator and leakage rules were not weakened. The final private ledger has **1,594 exposure rows**; that expansion is evidence granularity, not new physical events. Available acquisition-history audit remains necessary in addition to the sparse index.

## 3. Temporal GT actually obtained

The independent reviewer confirmed two old/new score witness pairs. Both remain conservative, nonadjacent brackets exactly as answered. Intervening frames are not promoted to independently confirmed old witnesses. No exact adjacent transition, midpoint or internal game End time is inferred.

| New-cohort evidence | Completed | Denominator / scope |
| --- | ---: | --- |
| Independently reviewed display-score brackets | 2 | 2 reviewed / 5 enrolled candidates |
| Exact adjacent native transition brackets | 0 | 2 reviewed brackets remain conservative |
| Complete-caption visibility witnesses | 1 | A complete word in the shown group |
| Independently established whole-episode first-complete caption onsets | 0 | Onset GT remains null |
| Complete active Start → End → next Round temporal GT | 0 | 5 enrolled candidates |
| Independent natural-negative episodes | 0 | All required classes missing |

The complete-word response is retained as a visibility witness at its real source frame. It does not independently exclude every earlier animation/occlusion frame in the entire episode; therefore global `first_complete_caption_pts` remains null. Last-partial-caption, full score pairs, clock typing/literals, active Start, next Round and reviewed whole-scene continuity remain null/unknown where not independently established. The other reviewed event has no independently confirmed complete-caption witness in its bounded acquisition. Internal game End is not labelled from video.

Actual shared preflight verified the source/unedited contract and all **130,039 source frame timestamps**, with uniform increasing cadence. The two bounded native acquisitions contain **121 / 181 frames**, each in its actual single decoder epoch and within the predeclared 256 MiB limit. Frame encoded/pixel hashes and source/profile/assets were rechecked. Timestamp integrity does not exclude capture loss or certify semantic continuity.

## 4. Contracts, verification and privacy

- [Annotation contract](annotation_contract_v1.md), [readiness policy](readiness_policy_v1.json), [schema](../../schemas/round_end_temporal_dataset_v1.json), [offline CLI usage](validator_usage.md).
- **38 new synthetic contract tests**, **116 related tests** and the existing **38 dataset cases** pass. Ruff and mypy pass. The production source and offline validation code have no change in this review update.
- Whole local macOS suite: **3,784 passed / 4 failed / 9 skipped**, 87% coverage. The same four existing spectator rendering failures reproduce on a clean starting-main archive in the same environment. No test suppression or recognizer fix was introduced; see [verification](verification_20261019.md).
- The pre-update HEAD `8c56330` passed both Linux and Windows workflows and the text-I/O gate. An earlier Windows dependency-feed 503/504 failure is retained in the history. Final-HEAD CI must be read from PR56; earlier results are not silently substituted.
- All private source, images, detailed PTS/GT, responses and ledgers remain outside Git. Public artifacts contain contracts/code, anonymous counts and hashes only. [Current anonymous summary](readiness_snapshot_20261020.json), [review scope counts](source_review_counts_20261020.json), [private audit anchors](private_audit_anchors_20261020.json).

Final private dataset canonical SHA256: `b5c765c5c81ac7a5407da4eaeb74338b29dd3dc92f10aa7b9951d3b06bb1096c`.

External freeze SHA256: `fd96234b94cf05adf22650096797eb67329c7f70699d5e76245fa7998278167f`.

Earlier frozen snapshots, the rejected intermediate candidate and scope corrections are preserved. The annotation schema/policy/validator hashes are unchanged from the pre-curation reservation. No predictions were used to choose cases, adjust labels or repair the sparse-support representation.

## 5. Why qualification remains blocked

The two reviewed positives are for `display_score_change`; they do not satisfy the full temporal End target. No complete whole-episode caption-onset or active Start/next Round GT, independent clock typing, two Spike→Decimal replications or fully reviewed scene continuity is available. Historical/reference-parent lineage remains incomplete.

Every required natural-negative class still has **0 independently reviewed physical episodes**: countdown, score-only, clock-only, Spike-only, decimal-only, partial caption, stale caption, buy phase, menu/scoreboard, spectator, source break, PTS gap and repeated raster. A mixed positive interval, sparse frame, old spatial negative crop or detector nonmatch is not a pure negative.

## 6. Minimum evidence for the next qualification goal

1. Preserve this method/data freeze and source-review history. Preregister operational metrics, acceptance thresholds and stop conditions before prediction opening. A changed method cannot reuse these viewed cases as a newly unused holdout.
2. Obtain at least **2 distinct independently reviewed Spike→Decimal temporal episodes**, with actual source witnesses and full active Start → End → next Round context in reviewed continuity. The current two narrow display brackets do not meet that requirement. Context outside an original reserved pool needs a documented, audited preregistered acquisition amendment, not a backdated split claim.
3. Independently review at least **1 pure-negative physical episode for each of the 13 required threat classes**, retaining unknowns and excluding intervals containing an End. Count events, not repeated frames.
4. Resolve original reference-parent/split/exposure provenance and bind actual assets, source contracts and current method hashes. Do not repair old qualification by replacing its fingerprint.

The present recordings may supply additional bounded reviews, including the three retained unknown candidates, but their sparse discovery does not guarantee that all required classes exist. Missing classes require additional auditable unedited recordings and independent source/interval review. No further unbounded experiments are part of this data preparation goal.

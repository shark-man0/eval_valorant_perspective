# Self Subject / Death evidence: experimental implementation

## Status and authorization

Development and source qualification were conditionally approved on 2026-10-16. Production adoption, unqualified event release and weaker HUD identity were not approved. This independent branch starts at proposal commit `612a4f0b6b0be82e2fa15f1a427a85e6b3b6f4bd`; fetched main is `7e480c2f2f7f49aea73e1541d065d78881d2f11c`. PR #44 transport, PR #46's legacy Death guard and PR #42 remain unchanged.

**Partial result B:** the typed model and non-releasing trial producer are implemented and source-tested. Positive Self Subject qualification is still missing. This is not completed Death recognition, a new canonical PASS or authorization to adopt the producer.

## Typed evidence model

`experimental/subject_death.py` is deliberately outside the production HUD pipeline. It is not imported by the application and constructs no native Event. Its own fingerprint binds experiment source bytes plus the existing runtime fingerprint; it does not inherit a global lifecycle qualification.

- `SourceBinding`: video SHA-256, exact native tick/time-base, source segment, pixel hash, code/profile/dependency fingerprints. Rational time is preserved until reporting.
- `SubjectObservation`: typed role and relation, opaque observed subject token, source confidence or explicit absence, method, source ROI and review provenance. Roles distinguish source-player binding, victim, killer, death transition, report, spectator and respawn. Relations distinguish self/nonself/teammate/enemy/unknown.
- `ReviewStatus` distinguishes raw candidate from source-reviewed evidence. **Neither status is recognizer qualification.** A label or high OCR confidence is not a qualification grant.
- `ProbeFrame` binds all observations to the same physical frame, rejects duplicate IDs and retains explicit continuity proof/discontinuity metadata.
- `DeathProbeDecision` retains support observations, original transition time, later confirmation time and the minimum actual contributing confidence. Its serialized output always has `qualified=false`, `formal_events=[]`; no actor or player-owned HUD field is supplied.

Malformed confidence (NaN, Inf, bool, string or out-of-range), missing source identity, invalid time bases, foreign-frame evidence and unsupported roles are rejected. JSON round-trip retains confidence absence, review status, source and provenance. These are standalone experimental records, not additions to public HUD/Package/SQLite schemas. No public Schema migration or new saved-data default is introduced.

## Trial producer and temporal safety

`SubjectDeathProbe` assembles only a review candidate. It requires a reviewed, source-supported self binding, a self victim and independent death-transition evidence for the same observed token. Source support below the unchanged 0.90 image-evidence floor remains insufficient. At least two native PTS and disjoint source ROIs/methods are required; different role labels on the same evidence do not create independence. This is a conservative experimental test, not proof that these conditions alone suffice for production.

The explicit experimental corroboration horizon is 1 second in the frozen probe configuration. It is not a GT window, timestamp tolerance, or production threshold change. The candidate boundary time is the actual death-transition observation time, not the later subject confirmation time. Its semantic accuracy remains unqualified.

Missing native frames, reordering, unknown continuity, a declared source break, or changed source/segment/profile/code/dependencies clear pending joins. Conflicting subjects or conflicting Self/Nonself roles invalidate earlier support and remain unknown. A regression first reproduced the stale-role candidate, then verified the correction. Report persistence, spectator and self-killer observations cannot replace a victim or self binding. A latch suppresses repeated episode candidates; ambiguous or foreign-subject respawn cannot rearm it. A reviewed same-subject respawn clears pending support rather than reusing old evidence. Any future production checkpoint/resume and life-interval semantics need their own reviewed contract; this probe is not installed in resume processing.

Even complete synthetic support produces an **unqualified candidate**, never `player_death`. A qualification loader, formal event release policy and production wiring are intentionally absent pending real qualification and adoption review. The existing legacy ownership guard is not bypassed.

## Frozen source evidence and exposure

A private plan was frozen before implementation, preserving the existing five development rasters and the original three victim-OCR review / three negative rasters. No reassignment or template fitting occurred. All are previously exposed same-video material, not new blind holdout. Original OCR evaluation labels remain separate and are consulted only after new reader calls; expected values are never inputs to the model or candidate selection.

Source SHA-256: `71d58558559d6f578433ce9f234bf176f76fd5a86657dbfe3eba1e7d36136b06`. Every image is checked against its encoded and decoded-pixel hash. Frozen source PTS are retained. The unchanged Tesseract crop/engine settings and 0.90 acceptance floor were used, with decoder binaries, OCR executable/language data and runtime versions fingerprinted. No private images, profiles, subject strings or evaluation labels are published.

Two full-frame images were visually inspected. One shows distinct killer/victim positions and a highlighted scoreboard row; the other shows live-world context without the target killfeed row. The recording owner subsequently reviewed the yellow outline as a fixed recording-player row (see the source-scoped trial below). This semantic review does not qualify a detector. A matching name or portrait is therefore not promoted to Self. There is no qualified Self/Nonself truth set from which to compute subject precision/recall. Real respawn-role qualification is also missing.

## Real-image and continuous results

| Measurement | Actual result |
|---|---:|
| Source review images re-recognized | 6 |
| Victim text correct / unknown / wrong in original positive OCR cohort | 3 / 0 / 0 |
| Existing negative crop rejected / falsely accepted | 3 / 0 |
| Independently qualified Self subjects | 0 |
| Formal Death events / owned Facts | 0 / 0 |

The first two OCR rows measure **text in a configured victim crop**, not a qualified role detector, Self identification or Death correctness. Nonself/Killer/Self semantic detection rates remain unmeasured. Zero formal output is a safety outcome, not a measured perfect Death false-positive rate.

The four previous continuous HUD measurement windows were replayed only after their unchanged runtime fingerprint matched and **102 freshly decoded native frames** matched original source PTS/pixel hashes. The model consumes report/spectator context from that explicitly identified old artifact, not newly claimed HUD recognition. No temporal window is spliced into another segment.

| Window | Native frames | Subject decision | Formal events |
|---|---:|---|---:|
| First report appearance | 24 | unknown throughout | 0 |
| Second report appearance | 30 | unknown throughout | 0 |
| Persistent report control | 24 | unknown throughout | 0 |
| Spectator/report control | 24 | unknown throughout | 0 |

The transition-time field is exercised synthetically but cannot be verified as a real self-death timestamp without subject/role qualification. No GT time is copied or adjusted. Source/code/asset terminal hashes passed. Runtime and sanitized fingerprint summary are in `e2e_reports/match_001/self_subject_death_probe.json`; peak memory was not measured.

## Tests and unchanged contracts

The focused suite has **55 PASS**: typed-model/temporal tests, integration isolation tests and existing legacy Death ownership regressions. It covers missing/invalid confidence, source/PTS/provenance, actor isolation, victim/killer distinction, report/spectator persistence, respawn, duplicate episodes, gaps, profile/code changes, independent evidence, delayed confirmation and JSON preservation. A complete probe candidate is rejected by the existing native Event Schema and cannot mutate an unowned HUD observation. Synthetic success is not source accuracy.

Local Ruff passes, including the diagnostic script; mypy passes 135 source files. Production HUD, lifecycle, builder, Fact, trace adapter and schemas are byte-identical to PR #46. Existing full-video/negative verdicts are not reclassified as new measurements. The first Linux/Windows CI run found one text-I/O inventory failure: two diagnostic-only `encode()` calls omitted the encoding. Both now explicitly specify UTF-8; the inventory and its test are retained unchanged. This changes no reader/model/runtime result. The source execution remains attributed to commit `14d5b71`, not retagged as a new recognition. Final Linux/Windows CI results are recorded on [PR #47](https://github.com/shark-man0/eval_valorant_perspective/pull/47).

| Canonical scope | PASS | FAIL | NE |
|---|---:|---:|---:|
| Adopted Full baseline | 23 | 55 | 4 |
| Previous unadopted Full | 28 | 50 | 4 |
| New experiment Full | Unmeasured | Unmeasured | Unmeasured |

Targeted formal Death E2E, fixed sampled qualification and Full are not run: no new qualified Subject predicate exists to release a positive event. Running the old unchanged pipeline would not qualify this experiment. A positive source/role/temporal hypothesis is required before those next gates.

## Available S-01 LFS point smoke

The separate `origin/feat/s01-lfs-point-smoke` branch at `9a4314a` provides `scripts/e2e/run_s01_lfs_smoke.py`: seven fixed round-boundary points, or 16 with `--include-regressions`. The LFS object binds the same source SHA and **267056165 bytes**. In its independent checkout both 7- and 16-point `--preflight-only` commands exited 0, and all nine wrapper tests passed.

This Pi has no Git LFS client. For preflight, an existing identical-SHA video was copied into that disposable checkout; actual LFS-server download and point recognition were not tested. Validation Pack and HUD profile remain separate inputs. The smoke is useful for bounded point transport/regression; it cannot establish native continuous lifecycle, Self Subject or Death qualification. No LFS or private video is added to this experimental branch.

## Remaining evidence and adoption decision

**Do not adopt.** The recording-owner review now establishes the source-specific marker semantics. Next qualify its detection against ordinary unmarked/foreign rows and spectator controls, and bind the observed subject to a separately recognized victim rather than killer. Source-continuous death/respawn evidence and source-disjoint review/negatives must survive frozen qualification. Existing victim-only OCR and report numeric success cannot substitute.

Use available current-video context first; do not demand another video by default. Preserve all prior exposure and freeze any genuinely unseen review material before fitting. If source-player binding cannot be established from the available images, record that precise limitation and keep unknown. Formal event identity/schema changes require the additional pre-adoption approval specified by the user. HP, Ammo, Weapon, Alive and view owner remain unchanged.


## Source-owner scoreboard review and structural trial

The source owner answered that the scoreboard yellow outline fixes the recording player's row; it does not follow a selected or spectated row. This statement is retained as a private source-specific review, bound into the experimental profile fingerprint. It is not a qualification pack, an ownership promotion, or authorization to release a Death event.

`experimental/scoreboard_subject.py` adds an isolated diagnostic reader. Three disjoint border masks exclude the name and value-bearing row interiors. Each structural NCC support must meet the unchanged 0.90 floor before the existing text reader receives the matched row's name crop. Its own source/profile/code fingerprints and decoded-pixel hash must agree. Multiple separated matching rows are rejected. Name confidence must be finite and at least 0.90; malformed or missing confidence remains unaccepted. The output is only `SOURCE_PLAYER_BINDING`, with relation **UNKNOWN** and review **CANDIDATE**, retaining actual PTS, source and ROI. No production import, native Event, owner, Alive, HP, Ammo or Weapon changes are introduced.

The structural reference was frozen from one development native frame before applying it to the separate original review raster. Three original victim-OCR review rasters are not three scoreboard positives: only the first contains the scoreboard. The others are marker-absent controls. The six archived review/control rasters were freshly re-decoded at their original native PTS; all six decoded-pixel hashes matched. Development and positive review images are neighboring frames in the same previously exposed episode. They are **not independent holdout**. No threshold, mask or reference was retuned from the review result.

| Source-image trial | Result |
|---|---:|
| Development marker present / candidate emitted | 1 / 1 |
| Exposed same-episode review marker present / candidate emitted | 1 / 1 |
| Marker-absent controls / candidates emitted | 5 / 0 |
| Review row-name match to separately read victim crop text | 1 |
| Qualified Self / formal Death events | 0 / 0 |
| New blind holdout frames | 0 |

The three review structural NCC supports were approximately 0.9995, 0.9999 and 0.9826. The name comparison is performed after recognition, without passing expected text or GT to the probe. It is text agreement, not independent qualification of the victim role, ownership or Death time. Exact code/profile/result fingerprints and runtime are in `e2e_reports/match_001/scoreboard_subject_probe.json`; private names, profiles, images and per-frame labels remain unpublished. Peak memory was not measured.

The focused model/reader/isolation suite passes **71 tests**; adding legacy Death identity and text-I/O audit regressions gives **93 PASS**. All 38 dataset contracts, Ruff (the CI source/test/E2E scope plus the diagnostic script) and mypy (136 source files) pass locally. Synthetic controls require all three supports, exclude name pixels from structural scoring, reject ambiguous marked rows, invalid confidence and mismatched source/pixel/profile/code bindings, and preserve UNKNOWN/CANDIDATE. They demonstrate contract behavior, not real-video recognition accuracy. Production qualification and canonical PASS remain unchanged/unmeasured, respectively. Independent role negatives and source-continuous Death/respawn qualification remain the next gate. A short-lived scoreboard view cannot itself establish a death transition or bridge absent subject observations. Updated Linux/Windows CI results are tracked on PR #47 separately from the earlier green commit.

# Observed acquisition in the native cohort runner

## Problem

The previous native cohort runner initialized hypothetical source-world identities from its first image. That path cannot independently validate the image-supported observer's acquisition contract: a coherent seed and an actually observed reference match are different evidence. Target lifecycle assertions remain GT-R1-ROUND-START/END and GT-R2-ROUND-START, but this source-stage investigation alone passes none.

## Contract change

The existing common Python cohort runner now accepts an optional frozen `observer_profile` reservation. This selects the complete `ObservedSceneChain` path: profile-supported actual native initialization, reference-to-observed identity binding where needed, and continuous current/prior native links with measured joint witness provenance. Each explicit input window creates exactly one source episode. Failed acquisition or tracking permanently terminates it; there is no later per-frame restart/reacquisition. Individual windows never share observations or clock continuity. No manual seed, timer/phase input, GT, round ID or threshold override is supplied.

Observer mode requires pre-decode profile/assets/dependency code bindings and a decoded-native-pixel exposure inventory. It rejects the legacy hypothetical seed boxes/tracker options/audit overrides so they cannot silently override the frozen observer method. The profile loader validates review scope, asset confinement and native pixels before video decode. Every input PNG and frozen file is verified at termination. Legacy reservations without `observer_profile` retain their existing hypothetical-seed route/schema. The report exposes `initialization_reason`, native-pixel overlap and the actual observer's result per frame. It remains unreviewed/not qualification; no production proof or event follows.

## Evidence

One frozen real-video run processes43native frames in70.165144seconds:

| Explicit input interval | Native frames | Native links supported | PNG/native pixel exposure | Acquisition |
| --- | ---: | ---: | --- | --- |
|3.88–4.39sec|31|19/30|31/31 known for both|image-supported observed seed|
|13.0–13.2sec|12|0/11|0/12 known for both|initialization unavailable|

The first interval exactly reproduces the previous non-self initial observation/continuous result, including5/5critical native R1transient links, and terminates without rejoining. The second interval was reserved before decoding with no expected-state label and is disjoint from the frozen conservative exposure inventory. It never reaches joint-link evaluation: all later rows remain `episode_terminated`. This is **initialization coverage failure**, not11incorrect continuity predictions or proof of a real content cut. Its first full image reviewed after prediction shows another camera pose with foreground players/weapon, so the old seed boxes cannot be presumed semantically world-only. The other11images remain unreviewed. No new continuity ground truth or player-owned facts are generated. After these measurements the cohort is exposed and cannot be reused as a fresh holdout.

The exposure inventory combines the prior PNG/native inventory and recorded native hashes in current reports before decode. This is conservative known exposure, not a claim of exhaustive semantic review history or independent recordings. Same-video disjointness is weaker than independent capture generalization. Qualification still requires independent correct positives plus appropriate negative and paired UI evidence; initialization-unknown cannot count as correct continuity.

## Tests

37observer/initializer/joint/cohort tests PASS in32.99seconds. New tests reject missing frozen profile/code/assets/exposure, refuse hypothetical-seed overrides, exercise full orchestration with actual synthetic native camera motion, count decoded-pixel overlap, and verify failed first-frame acquisition cannot restart on later matching frames. Ruff and diff checks pass. Production source unchanged; preceding104-source-file mypy PASS remains applicable. The two real intervals verify FFmpeg/ffprobe native coverage plus terminal source/profile/code/assets/PNG hashes. No standard targeted/sampled/full E2E was started because runtime source/UI qualification and all boundary acceptance gates remain absent.

## Previous / Current / Delta

| Metric | Previous | Current | Delta |
| --- | ---: | ---: | ---: |
| Same-input exposed non-self native links |19/30|19/30|0|
| Critical R1source links |5/5|5/5|0|
| New disjoint context evaluated for acquisition |Not measured|1episode/12frames|Not comparable|
| New context acquisition proposals |Not measured|0|Not comparable|
| New context joint links actually evaluated |Not measured|0|Not comparable|
| Runtime qualification/event generation |0/0|0/0|0|
| Canonical PASS/FAIL/NE |Historical23/55/4|Not rerun|Unmeasured|

The previous44.322226second replay covered31saved images without native extraction/new context; runtime70.165144seconds includes43decoded images and metadata/verification. The workloads differ and this is not a speed comparison.

## Recommended command

```bash
python -m scripts.diagnostics.validate_scene_chain_cohort \
  --reservation e2e_reports/match_001/observed_cohort_runner_reservation.json \
  --output-dir outputs/recognition-investigation/NEW-observed-cohort \
  --output e2e_reports/match_001/NEW-observed-cohort.json
```

Use a **new independently reserved manifest and output** for qualification research; replaying the example is an exposed integration check. The runner refuses an existing output/directory. Freeze all file bindings and the observer profile first; preserve continuous native input, source integrity and exposure provenance. Python/OpenCV/FFmpeg path handling is shared with Windows; Windows execution itself remains unverified.

## Remaining blocker

The integration can now test genuine acquisition-plus-continuity instead of hypothetical seed support. Broad acquisition coverage, foreground eligibility/full camera hypothesis scope, independent positive/negative controls, paired current UI-transition evidence and trusted producer qualification remain absent. Unknown on the fresh context rules out calling this a generally qualified camera continuity producer. No acceptance policy is relaxed. R2start and R1result-banner qualification remain separate blockers; no canonical gain is claimed.

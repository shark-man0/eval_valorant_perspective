# Near-seed image-derived acquisition investigation

## Problem

The earlier eight-pose stateless check only acquired the exact reference image. Before independent qualification, determine whether the observer can acquire a different actual native image and carry that observed source history through R1's transient display sequence. Target assertions remain GT-R1-ROUND-START, GT-R1-ROUND-END and GT-R2-ROUND-START; this source-stage evidence alone does not pass them.

## Evidence and competing hypotheses

Hypothesis A: acquisition requires byte-identical self-reference. Hypothesis B: the frozen reference accepts a limited nearby pose, while distant/occluded poses remain unknown. Twelve preselected, already-exposed native images were checked without modifying bootstrap, reference, boxes or thresholds. Six prefix observations are validated against their original extraction report's PTS, PNG hash and native pixel hash, rather than inferred filenames alone. Six subsequent images come from the original native R1 declaration. All inputs/code/profile/source hashes are declared before predictions and verified at termination.

## Independent image evidence

The prefix at3.802669–3.852669 has0reference tracks;3.869336 has51tracks/31inliers and fails unchanged90%consensus. At3.886003,151tracks/147inliers plus five joint distributed domains support acquisition. The exact reference at3.902669 and four later native images support acquisition too;3.986003 fails133/154consensus. Result:6/12proposals in14.979627seconds. The different3.886003image is not a byte-identical reference, so hypothesisA is contradicted. These are timer/phase-independent image measurements, but **previously exposed development**, not independent holdout and not broad pose coverage.

## Continuity decision

A separate frozen31-frame native replay initializes on that non-self3.886003observation, retaining only original reference identities. No asset supplies previous native PTS/pixels and no manual current mask is used. It produces19/30supported links, including all five critical native links through phase disappearance, both2:25images and first1:39. At4.219336original seed-model consensus fails; the episode terminates without joining later images. The result supports visible continuity around the transient UI sequence, not uninterrupted hidden game time.

## Contract change

No implementation or threshold change. The observer's existing non-identical initialization path is now exercised on actual native images. The initial observation was selected from exposed acquisition diagnostics, explicitly development selection; no production PTS exception, round timestamp or round ID is installed. The stateless acquisition improvement is evidence against a self-match-only assumption, not permission for arbitrary reseeding after discontinuity.

## Tests

Both frozen measurements complete with source/profile/assets/code/PNG terminal bindings intact; outputs contain no nonfinite JSON scores. Original extracted prefix metadata agrees exactly. Prior30related unit cases/Ruff and104-source-file mypy apply because diagnostic/production code is unchanged in this followup. No targeted, sampled or full E2E was run: source/UI qualification and the other two boundaries are still missing.

## Previous / Current / Delta

| Metric | Previous | Current | Delta |
| --- | ---: | ---: | ---: |
| Broad eight-image static acquisition proposals |1/8| Not rerun|Not comparable|
| Near-seed acquisition proposals |Not measured|6/12|Not comparable|
| Actual non-self initial observations validated through R1 transient |0|1|+1|
| Critical native links (same five endpoints) |5/5|5/5|0|
| Common R1 links after3.902669 (different initialization histories) |22/29|18/29|-4; acquisition history differs|
| Non-self prefix link into3.902669 |Not measured|1/1|Not comparable|
| Independent qualifications |0|0|0|
| Canonical PASS/FAIL/NE |Historical23/55/4|Not rerun|Unmeasured|

Replay takes44.322226seconds; the earlier provenance replay47.621045seconds has different starting image/retained-track lifetime, so this is not a speed or recognition improvement claim. The shorter tracker lifetime is retained honestly rather than repaired with reseeding/threshold changes. Runtime round start/end/packages remain unmeasured, with no new event generated.

## Remaining blocker

The static route covers a narrow acquisition neighborhood, not arbitrary poses. All measured inputs are now exposed and cannot be reused as independent holdout. The next source qualification experiment must reserve disjoint native observations before inspecting them, include actual image-supported acquisition followed by continuous native links and negative episodes, and report initialization failure separately from joint-link accuracy. It must assess the paired positive UI-transition evidence too. Broad source eligibility/foreground scope and trusted runtime qualification remain absent; do not substitute near-seed6/12 or critical5/5 for qualification. R2start/result banner are separate unqualified blockers. Windows execution is unverified.

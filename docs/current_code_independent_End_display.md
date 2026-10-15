# Current-code independent End-display assessment

A new physical End-display event on the user-confirmed unused, unedited additional source was selected with the recognizer and profile fixed. The current method fails to emit an End on this event. This is evidence against End admission; no qualification is issued.

Method commit `abeb0118f4700b91e939e9ee27b0e9c72a103593`, recognizer `d14e4b78b3e1fae4df0d154d21067b452796794a9c954992cf7f2ebb12a6d091`, profile `6411f7d326f71076efa54bb431a8efc501d01678fccd19a1f3a07a62c2146c80`. Source SHA256 `06919642d69f68895ac123b505bfd7d3643dd28d903585008fcdc2b7f1b7e3fd`. The source-only discovery selection predates this event-image view. Earlier active-round endpoint context at1500s and later source-only context at1530s were already viewed; this is not a wholly blind Round or new-video generalization. The rejected temporal prototype's former future-pool plan remains historical and is not retroactively qualified by this separate fixed-method assessment.

## Source review before prediction

The human selected **C** as the first of six adjacent source frames with right score7 and read **LOST**, with subtitle **チーム全滅**, in the three post-result supports. C is tick23158528, timebase1/15360, **1507.7166666666667s**; B at1507.7s still shows6. The literal response is saved privately with the request-sheet, manifest and frozen-label hashes before prediction starts. Original labels are preserved unchanged. Their historical `human_review_pending:true` field is resolved by the separate review-response sidecar, not silently rewritten.

This confirms displayed content only. It does not supply an internal game End time or approve the recognizer. The target is the first visible score display point, with no expanded acceptance window. Six support labels cover literal clocks1:05/0:04, scores10–6/10–7, absent/complete result. Full frame-by-frame temporal ground truth and independent negative annotations remain unavailable.

## Actual result and failure path

One actual production-reader call processes301 consecutive decoder-owned frames1506.5–1511.5s. A same-source earlier frame300s initializes geometry only. The raw rows are saved before label scoring. Source PTS/epoch/pixels, profile/code/contract and cached images are rechecked at completion. No source breaks occur. There are **zero diagnostic End patterns, zero formal events and zero player-owned facts**.

| Saved-row observation | Time (s) | Consequence |
| --- | ---: | --- |
|Accepted clock1:05→0:06|1507.4333333333334|Starts a pending candidate|
|Ally score becomes unknown|1507.5|Interrupts the previous accepted score run|
|Old score10–6 reappears|1507.5666666666666|Existing conservative adjacency rule discards the pending candidate|
|First accepted score10–7|1507.7166666666667|Matches human C exactly, but no pending candidate remains|
|First accepted complete LOST|1509.0833333333333|1.65s after the clock change, outside the unchanged1s horizon even if the earlier score interruption were resolved|

Thus caption lateness alone does not explain the miss: interrupted score evidence is an earlier independent obstacle. The score target is read correctly but the End boundary is **missing**; no timing PASS is claimed. On the six selected supports: timer6 correct; enemy score6 correct; ally score5 correct/1 unknown; result6 correct. No selected-support wrong values. These sparse counts are not full-window accuracy or formal qualification.

The producer takes87.306851667s, retains601,238,762 PNG bytes, and peaks at111,345,664 process RSS bytes (decoder child peak unmeasured). It accepts146 result frames and286 complete score pairs. Saved rows are replayed through the unchanged tracker for failure diagnosis without invoking readers again. No threshold, horizon, timestamp, GT, profile or recognition-code change follows this held result.

## Current-code regressions and limits

The original numeric development window518–526s contains481 frames and still produces a diagnostic End at522.95s, confirmed523.5333333333333s, confidence0.9038290977478027. This is training regression with no independent correctness labels. Four previously exposed fixed negative windows total76 frames, zero End/result matches/owned facts; they lack independently reviewed full temporal GT, so no formal false-positive rate is inferred.

All hashes and measured counts are in `e2e_reports/match_001/current_code_independent_End_display.json`. Private source frames, labels, profile, review ledger and raw rows remain outside Git. Existing A/B, WON, CLUTCH and rejected-prototype results keep their original fingerprints and exposure status.

## Reproduction and next gates

With the private decoder-owned cache and profile available, run the frozen `work/new-source-development/replay_border_score_case.py next-End-native next-End-result` once under `PYTHONPATH=src:. .venv/bin/python`. It verifies selection/source/code/profile identities, saves raw observations, then scores supports and checks terminal integrity. `evaluate_next_End.py` evaluates only those saved rows and binds the prior human response; it does not read the video or rerun recognition. Output directories are exclusive-create so the original run cannot be silently overwritten. The aggregate is evidence of this run, not a standalone reconstructible qualification bundle.

Any new method must address both reliable complete score evidence and complete caption evidence using development data, then be frozen before a different independently reviewed event is assessed. This event is now exposed and cannot be reused as blind evidence for an improved method. Do not revive the rejected score-proposal restart guard, bridge unknown score gaps, extend the horizon or backdate the boundary to make this case pass.

Formal End, whole-lifecycle qualification, exact independent temporal/negative labels, current R2 ordinary-application calibration and match-wide ownership remain incomplete. Main is not merged; Issue16 stays open and PR42 stays draft. Full E2E is not rerun; canonical23 PASS/55 FAIL/4 NOT_EVALUATED is unchanged. This report-only checkpoint does not change the recognizer fingerprint. Current implementation CI status could not be refreshed because automatic approval review rejected the network action due to its usage limit; the previous observed Linux/Windows runs were still in progress.

# Timer source review: recognizer unknown is not absence

## Problem and fixed targets

Qualified global lifecycle inputs remain a release blocker for
`GT-R1-ROUND-START` and `GT-R2-ROUND-START`. The existing native spectator
control interval has 19 unknown timers among 30 frames. A rejected prediction
cannot establish that the source field is absent or unsuitable for reading.

## Evidence and hypothesis

Review all 30 already exposed native images from the existing 160.0–160.5 second
spectator-control interval. Selection includes the entire interval, rather than
choosing samples by recognizer confidence or correctness. A contact sheet hides
predictions and shows the actual timer region. This is development source review,
not new independent holdout. Review labels are saved before the new static replay;
the earlier diagnostic predictions were already exposed.

All 30 images contain legible timer text: the first 23 display `0:51`, and the
last seven display `0:50`. These values come from the actual images, not a
validation assertion, countdown inference or neighbouring-frame fill.

## Change and results

No production, profile, threshold, assertion or source changes. Replay the same
current frozen reader at its declared nominal ROI, and compare its result to the
existing current native system projection. Both yield 11 correct, 19 unknown,
0 wrong. Of the 19 rejections, 16 report
`strict_timer_foreground_touches_roi_border` and three report
`strict_timer_expected_exactly_two_separator_dots`. No fallback or ROI expansion
is adopted. Static reader replay takes 4.690 seconds on saved images; this excludes
decode and is not a full pipeline runtime.

| Metric on the same 30 source frames | Previous | Current | Delta |
| --- | ---: | ---: | ---: |
| Accepted | 11 | 11 | 0 |
| Unknown | 19 | 19 | 0 |
| Wrong against this complete manual review | not measured | 0 | unavailable |
| Verified absent-timer controls | 0 | 0 | 0 |
| New qualification files | 0 | 0 | 0 |

Existing native system values agree with all accepted static reader values.
The 19 unknowns are recognition rejections of positive source evidence. They
must not be relabelled as negative absence cases to populate a qualification
file. Spectator is a negative condition for player ownership and some lifecycle
transitions, but it does not mean a global timer is absent.

## Tests and remaining blockers

Input image hashes, decoded pixel hashes, profile fingerprint, current recognizer
fingerprint and terminal input hashes verify. No shared code changed; the prior
2707 PASS / 6 SKIP, Ruff and mypy results are retained without an unnecessary
full regression or full E2E. Canonical 23 PASS / 55 FAIL / 4 NE remains historical;
no updated canonical accuracy or safety claim is made. Windows runtime unverified.

This investigation only rules out these 30 images as absent-timer negatives.
It does not add a requirement that every negative be natural, invalidate
separately reviewed synthetic or alternate-field controls, or require another
video. Each control must state what failure it tests, and component qualification
must match its actual runtime input and retain physical split independence.
Next, complete the joint timer/phase/UI proof with honest control provenance
and continuous transition review before enabling formal start events.

Machine-readable source ticks, image hashes, manual labels and reader outcomes:
[timer_control_source_review.json](../e2e_reports/match_001/timer_control_source_review.json).

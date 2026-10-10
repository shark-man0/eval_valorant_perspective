# R1 result text localization feasibility

## Problem and hypothesis

`GT-R1-ROUND-END` still lacks a qualified boundary. The frozen late TEAM ACE
reference has NCC0.387553on the early visible word, below the unchanged0.90
threshold. Test whether a common position shift inside the existing configured
round-result ROI can recover it. Do not change the reference, masks, thresholds,
geometry, GT, acceptance windows or production behavior.

## Evidence and method

Use all108existing hash-bound native images at74.202669–75.986003sec, including
every source frame in that saved window. The existing late reference retains its
three distinct training exemplars and three semantic groups. Search only a shared
translation in the existing520×230ROI, with no scale/rotation search or parameter
selection from Validation Pack values. Each group uses the same location. A
group cannot select its own best patch elsewhere in the image.

The vectorized NCC maps select a candidate; the original float64 fixed-position
semantic matcher confirms it with its existing contrast floor and threshold.
Undefined/low-contrast maps remain unaccepted. Source encoded/pixel hashes,
profile/assets, script bytes and production recognizer fingerprint are checked
at terminal. The prototype never emits an event or writes a profile.

## Previous / Current / Delta

| Diagnostic metric | Fixed position | Shared translation | Delta |
| --- | ---: | ---: | ---: |
| Accepted result frames | 29 | 29 | 0 |
| Early word NCC | 0.387553 | 0.387553 | 0 |
| First accepted result PTS | 75.319336 | 75.319336 | 0 |
| Released events | 0 | 0 | 0 |

Every accepted frame keeps the original position[137,73]inside the ROI. The early
word's best shared position is also[137,73]. Translation therefore does not solve
this particular failure. Do not add the search to production or tune a larger
search/threshold around this result.

The initial diagnostic takes48.200942sec. The code-bound repeat takes46.807745sec,
Delta−1.393197sec (−2.89%). All108result records are identical. The repeat adds
production-code binding; these timings do not establish a speed improvement and
are not comparable to full-analyzer or canonical E2E runtime.

## Independent source appearance and limits

Manual review of the complete result ROI on the first32native images finds one
complete visible TEAM ACE word, at source index15 (74.436003sec). Subsequent
frames show expanding borders over the world/weapon image before the later
text stabilizes. This is UI animation under the explicit no-edit input contract,
not an attempt to re-prove or reject that guarantee.

A red display visibly overlaps the early glyph region. A diagnostic color rule
`R>=120, R>=1.5G, R>=1.5B` overlaps7.29%,22.01%,5.93%of the three unchanged
semantic masks. At late source indices68and73the overlap is0in allgroups. This
is an observed contamination, not proof it alone explains all NCC loss and not
a player-owned damage/death fact. No red pixels are removed and no mask is
modified to force acceptance.

This reviewed early interval supplies only1complete-word frame, below the
existing minimum3distinct supported training images. Duplicating or transforming
that frame cannot manufacture independent support. Existing late support does
not prove the occluded early appearance. No new reference/qualification is made.

## Tests and decision

33related tests PASS; RuffPASS. New tests require all groups to share a location,
reject independent group mixing, flat/undefined NCC, corrupted text and incomplete
ROIs. Existing semantic source-support tests remain green. Production source is
unchanged, so the previous121-file mypyPASS applies to the identical source tree.

Reject the shared-translation hypothesis before spending independent controls or
running canonical E2E. Archived canonical Previous remains23PASS/55FAIL/4NE;
Current/Delta unavailable. The82original assertion status digest is unchanged.
Canonical negative/discontinuity outcomes are not newly verified. Windows remains
unverified on hardware.

## Artifacts and next action

`result_shared_translation_bound_replay.json` and
`result_shared_translation_review.json` in `e2e_reports/match_001` contain counts,
PTS, common positions, group scores, hashes and review scope. Source images stay
local. The exact run script is retained hash-verified at
`outputs/recognition-investigation/result-shared-translation-rejected/probe-at-run.py`;
the maintained script subsequently received import-order formatting only. No
historical report is re-signed.

Next test the independent timer/score composite evidence already authorized for
system-level lifecycle: an observed clock reset plus a stable one-point score
transition, with native continuity, context/contradiction guards and separate
qualification. First establish the temporal meaning of those observed changes
without selecting a timestamp from GT. Keep it diagnostic until actual active
lifecycle and independent qualification are proven. It must never infer owned
facts or manufacture a result word, and a late score timestamp must not simply
be backdated into an acceptance window.

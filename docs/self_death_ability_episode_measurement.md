# Self Death: ability episode and current-frame binding limitation

Status: **measured development false negative, not a qualified positive result**.
Source code: `93b2a7a77aac20ae83aa9bb6da9fde630239a008`; fetched main
`7e480c2f2f7f49aea73e1541d065d78881d2f11c`.

Subsequent [luminance-binding and explicit ability-separator work](self_death_luminance_ability_recognition.md)
recognizes this exposed development episode as one unqualified diagnostic
candidate. The historical failure measurements below remain unchanged; they
are not the result of that newer feature/profile or independent qualification.

## Fixed discovery and source review

The unchanged static caption reference was scanned within the frozen v3 search
rectangle. This localization inspected 2,245 keyframes and found two later
caption-bearing groups beyond the old cropped scan's last positive. Selection
reserved the first such group before actor review/full native recognition.
Keyframes supply localization only: no absence, continuity or event proof.

The selected three-second window contains all 181 native frames. Source SHA,
rational PTS, encoded/pixel hashes and source epoch were verified; original
source and sampled full-resolution context images are preserved privately.
Initial/middle images show the recording first-person view without a Report;
the final image shows death animation, the user-confirmed recording-player
yellow outline on the right victim portrait, an ability pictogram, and the
new self-referential Report. This is evidence of one actual self-death episode.
The source review was saved before running the continuous recognizer.

A later image from this same episode informed the v3 search-geometry fix.
Consequently, this is **development temporal validation**, not a new blind
holdout or independent whole-producer qualification. The context-image review
also does not certify every frame's content continuity. Canonical GT is unchanged
and neither expected identity nor expected timestamp is a recognizer input.

## Actual unchanged-reader result

| Measure | Current result |
| --- | ---: |
| Native frames | 181 |
| Source-observed self-death episodes | 1 |
| Diagnostic death predictions | 0 |
| Missed source episode in this development window | 1 |
| Caption-positive frames at unchanged NCC >=0.90 | 106 |
| Recording-player marker readings | 22 |
| Marker readings with unknown role | 22 |
| Numeric/geometric victim-role readings | 0 |
| Source-blocked frames | 0 |
| Formal Events / qualification grants | 0 / 0 |

All 181 image readings report `fresh_report_and_self_victim_unproved`. Each of
the 22 marker readings reports `weapon_separator_unavailable`. The current
reference/geometry path does not establish the ability pictogram's independent
separator role. It must not borrow a weapon score, infer victim from Report
presence, or declare a spectated player's death to be self death.

Recognition took 157.837 seconds, complete replay wall time 301.150 seconds and
peak Python RSS 99,921,920 bytes. Native acquisition took 272.544 seconds;
307,067,785 encoded bytes stayed in the temporary RAM cache. No original video
was copied. Source/config/dependency terminal checks passed.

## A single ability template cannot resolve this case

There is a separate temporal binding limitation. The measured marker readings
inside the existing one-second caption-onset horizon consist of two isolated
frames. Neither can supply the existing multi-frame corroboration spanning
at least 0.05 seconds. The first measured marker run long enough to satisfy that
duration ends 1.133333 seconds after the caption onset, outside the horizon.

This calculation is an **upper bound**: even assuming perfect future separator
support on every existing accepted marker reading cannot satisfy the unchanged
temporal gate. It does not fabricate a separator score, qualify those pixels,
or assert that a longer horizon would safely recognize the death.

Rejected next change: append one ability image and claim the episode solved.
No additional reference was fitted, no confidence/NCC threshold lowered, no
horizon extended and no event backdated. The separate missing current-frame
binding coverage must also be addressed and independently qualified. This
prevents another local reference adjustment with no viable positive hypothesis.

## Private evidence and remaining work

### Rejection audit: search loss was not observed

An additional frozen-box audit used all 181 original native images, verifying
encoded and pixel hashes. It compared the exact existing masked NCC with the
OpenCV candidate screen at the same pixels, using the final recorded marker box
without optimizing its position per frame. The profile, three disjoint masks,
color thresholds and source images were unchanged.

Across the window, 20 frames passed the complete fixed-box rules. None of those
was rejected by the screen or absent from the original production readings.
No frame exceeded the 128-candidate ambiguity limit. Original localization
found 22 markers in total, including two at a different position. These results
do **not** make the fixed box an alternative localizer or prove the absence of
all possible search defects; they refute the measured fixed-box loss hypothesis.

| Fixed-box measurement after caption onset | Result |
| --- | ---: |
| Native frames | 106 |
| Upper structural mask below NCC 0.90 | 32 |
| Middle structural mask below NCC 0.90 | 83 |
| Lower structural mask below NCC 0.90 | 49 |
| Yellow-color support below 0.90 | 42 |

These rejection counts overlap and must not be summed. In the first second
after onset, the middle mask passed on 0 of 61 fixed-box frames. The original
localizer still found the two isolated markers described above at other pixels.
The middle-mask median across all 106 post-onset frames was 0.804674, compared
with 1.0 for the upper mask and 0.928414 for the lower mask. This is measured
reference-support failure, not evidence permitting a lower threshold, removal
of a mask, or propagation of a later successful binding to an earlier frame.
The audit took 74.059 seconds; no video was decoded again.

### Existing Scoreboard path: border works, name remains unaccepted

Full-frame review also found a Scoreboard during the same post-onset interval.
Four already exposed context images were frozen for an alternative-path check.
The original Scoreboard reference, masks, search geometry and name crop were
reused unchanged. A diagnostic profile explicitly bound them to the second
source; this does **not** transfer any first-source qualification. The existing
`ScoreboardSubjectProbe` and Tesseract reader ran without source changes.

Three context images without the Scoreboard returned `marker_not_matched`.
On the Scoreboard-present image, the three border supports were 0.985075,
0.999404 and 0.936022. The probe reached the name reader but returned
`name_not_accepted`. A direct diagnostic on the identical original crop measured
OCR confidence 0.628499, below the unchanged 0.90 acceptance condition. No name
was supplied to the reader and no expected string selected a result.

The four-image probe took 3.041 seconds and produced no subject candidate or
formal event. This separates successful exposed-image border recognition from
unaccepted name recognition. It is neither blind holdout nor continuous
Scoreboard qualification, and it does not solve the missing ability-separator
role. No name preprocessing, threshold change, reference fitting or event
integration was added on the strength of this single exposed positive.

Private reproduction records are `s01_marker_rejection_probe.py`,
`marker-rejection-probe-plan.json`, `marker-rejection-probe-result.json`,
`s01_scoreboard_alternative_probe.py`,
`ability-scoreboard-alternative-plan.json`,
`ability-scoreboard-alternative-result.json`,
`ability-scoreboard-name-diagnostic.json` and
`marker-and-scoreboard-rejection-assessment.json`.

The next implementation hypothesis must therefore address actual binding and
role recognition with measured positives and negatives. Changing the search
screen, reviving the weaker yellow feature, adding only one ability template,
or bypassing name acceptance has no demonstrated safe solution here. Current
reader/test source and its previously recorded CI results are unchanged. No
new canonical targeted, sampled or Full result was generated by these audits.

The existing private investigation directory contains:

- `match002-v3-caption-discovery-plan.json` / `match002-v3-caption-result.json`:
  frozen discovery and first-group selection.
- `v3-new-caption-native-plan.json` / `v3-new-caption-native-manifest.json`:
  complete source-native records and storage limit.
- `v3-new-caption-source-review.json`: source context review before recognition.
- `v3-new-caption-native-replay.json`, SHA-256
  `f225f4ff058b7b437d227f32837c92772f623e5fe3c1fc5d8563d66a862e04bf`.
- `v3-new-caption-temporal-assessment.json`: original marker runs and exact
  rational horizon/duration calculation. No production configuration is changed.

Next required evidence is independent current-frame recording-player binding
coverage and explicit ability-separator semantics, with frozen development,
holdout and negative splits. A real qualified image/continuity provider remains
missing at the Event-session entrance. Existing known weapon-based candidates
are not newly qualified by this ability episode; its diagnostic false negative
is not an additional canonical assertion or a change to the 82-assertion Pack.

No new canonical targeted, sampled or Full run was performed. Adopted 23/55/4,
archived Strict candidate 28/50/4 and the separate timing-policy comparison remain
historical and distinct. No precision/recall generalization, canonical PASS gain,
main merge or goal completion is claimed. Production/test source is unchanged
from `93b2a7a`; its successful Linux/Windows checks remain source-specific evidence.

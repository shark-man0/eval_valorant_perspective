# Camera evidence from the spectator label and the own ability bar

Development supplement for the shared timeline (`DevelopmentGameTimeline`). It
adds measured camera evidence; it does not add a state machine and issues no
formal Facts/Events.

Code: `src/valorant_ai_coach/temporal/camera_panel.py`, engine option
`measured_view_precedence` in `game.py`, `export --measured-view-precedence`.

## Why

On the ten admitted DEVELOPMENT matches every camera observation in the
existing inputs came from a learned view classifier (`unqualified_view_model`).
4,118 of 21,999 seconds had no camera value, mostly purchase phases, menus and
scoreboards, and some SPECTATOR seconds were carried from learned claims.

## Measurements

| Display | Measurement | Decision |
| --- | --- | --- |
| Spectator label (lower left, "switch player") | Normalized cross-correlation with a 158x28 reference crop of the label, searched within 6 px, at 1920x1080 (other 16:9 sizes are resized; other aspect ratios are UNCHECKED) | `PRESENT` at 0.55 or more, `ABSENT` at 0.30 or less, otherwise undecided |
| Ability bar (bottom centre) | Four icon slots compared with the recorder's own icons; the second-lowest slot score is used, so three of four icons must agree | own HUD at 0.60 or more |
| Remote control (optional references) | The key hint shown above the ability bar while an ability is steered, searched across the band above the bar, and the control-duration icon at the screen centre above the bar | remote at 0.60 or more for both |

The recorder's own icons are learned per recording: 300 evenly spaced frames
with the label `ABSENT` are clustered and the dominant cluster becomes the
prototype. It is rejected when it is not a majority, or when any frame with the
label `PRESENT` matches it. A team never fields one agent twice and only
teammates can be spectated, so a matching bar identifies the recorder's own HUD.

Rows (`stream_kind: camera_panel`, strong evidence):

- label `PRESENT` gives `spectator` (unless a remote cue is also present: no row);
- a remote cue without the label gives `remote`;
- label `ABSENT` and own ability bar give `owner_hud`;
- anything else gives no row. Label absence alone is never evidence.

`python -m valorant_ai_coach.temporal.camera_panel --video V --timeline T
--label-reference LABEL.png [--remote-hint H.png --remote-duration D.png]
--output S.json` decodes exactly the timeline's
native samples, keeps only frames whose decoded pixels hash to the sample's
`native_pixel_sha256`, and writes a supplement for `export --supplement S.json
--measured-view-precedence`. The label reference is a private asset.

## Engine option `measured_view_precedence`

- In a frame with a measured `owner_hud`, `spectator` or `remote` row, learned
  (`unqualified_view_model`) claims of those three are ignored. Other learned
  signals are kept. A measured `remote` row also gives life ALIVE: only a living
  recorder steers an ability.
- A run of measured own-HUD rows (which require the own health value) after an
  elimination hypothesis keeps life UNKNOWN, or a victim-display DEAD, while the
  Round token is unchanged. The run is a respawn only when it continues, without
  death, spectator, result or score change, until a measured BUY with a new
  Round token; a Round result inside the run ends it. The return time stays
  unknown (`measured_view_return_history`).
- Without such a BUY, the own-HUD rows of the run that lie in a running Round
  (Round ACTIVE or BUY, or followed by a measured ACTIVE/BUY row of the same
  Round token before any result) become ALIVE on their own
  (`measured_own_hud_with_health_during_round`): a recorder that is not alive
  cannot hold its own first-person view with its health shown. Rows with an
  elimination display, death, spectator, remote or result cue, and rows between
  the own-HUD rows, are not revised.
- A measured spectator row (the player switch prompt and the spectated player's
  name), without an own HUD, remote or BUY cue in the same frame, gives life
  DEAD (`measured_spectator_view`): only a recorder who is not alive is shown
  that label. Learned spectator claims stay a competing hypothesis.
- A carried ALIVE value (`bounded_missing_observation`) directly before such a
  row, with only UNKNOWN rows between, returns to UNKNOWN
  (`carried_alive_before_measured_spectator_view`): the death lies somewhere in
  the carried interval.
- With the option, the return-tail bracket no longer reopens a victim-display
  DEAD in a frame that shows the Round result or the intermission unless the
  recorder's own health or menu is current: a recorder that died returns only at
  the next purchase phase. Rows after the result display keep the bracket.

The default path is unchanged.

## Health digit gate

`owner_hud` rows additionally require digit-shaped glyphs in the own health box
(575, 1000, 105x58 at 1080p). A first full-length run without this gate turned
30 seconds of correct DEAD into ALIVE on the spike camera after the recorder
died (6 of 6 sampled frames were wrong), which this gate removes.

## Validation (2026-11-16)

### Fixed comparison: ten DEVELOPMENT matches, 21,999 second rows

All 32,089 native samples were decoded again from the original recordings on
the recording machine; all were pixel identical to the acquisition. Label and
ability-bar scores were measured on JPEG crops (quality 92) of those frames;
the health digits and remote cues were measured on the recording machine from
crops of the same frames with the same formulas. For DEV2 the health digits
come from the same timestamps decoded in the Linux container (not pixel
identical there, recorded as such).

| Measure | Before | After |
| --- | ---: | ---: |
| Camera UNKNOWN seconds | 4,118 | 1,039 |
| Life UNKNOWN seconds | 5,322 | 1,195 |
| Round UNKNOWN seconds | 7,230 | 7,230 |
| Matches where any UNKNOWN count rose | – | 0 of 10 |
| Camera REMOTE seconds | 0 | 87 |
| Fixed 69 attributes: correct / incorrect / abstained | 69 / 0 / 0 | 69 / 0 / 0 |
| Fixed labels (77, union scorer): Camera / Life correct | 20 / 20 (1 abstained each) | 21 / 21 |
| Supplemental 9 and 6 attributes | 9/9, 6/6 | 9/9, 6/6 |
| Frames: DEAD recorder with a first-person camera | 223 | 149 |
| Frames: ALIVE recorder with a spectator camera | 0 | 0 |
| Formal Facts/Events | 0 | 0 |

Seconds changed between known values: life DEAD to ALIVE 991, ALIVE to DEAD 2;
camera SPECTATOR to SELF 107, SELF to REMOTE 87, SELF to SPECTATOR 6. Life
values withdrawn to UNKNOWN: 340 seconds. Before the measured spectator rule
(6e786ae) the same replay gave Life 2,904 with 59 withdrawn seconds; the rule
changes no known value, Camera, the 69 attributes or the fixed labels. Before
the own-HUD-during-Round rule (8c398d1) it gave Life 4,336 with 188 DEAD to
ALIVE and 862 withdrawn seconds; Camera is unchanged by that rule.
Per match, Life UNKNOWN seconds now: DEV2 106, issue_oldfull001 124,
issue_oldfull002 139, issue_oldfull004 113, issue_newfull001 119,
issue_newfull002 146, issue_freshfull003 119, issue_newfull004 146,
issue_freshfull005 67, first_new_cold 121.

### Fresh full-length analysis: all ten matches from the original recordings (2026-11-18)

The existing acquisition command (`generate`, 1 s sampling, ScreenCueObserver)
was run on all ten DEVELOPMENT recordings in a Linux container (21,999
seconds); `camera_panel` then measured every sample from the same recording at
full resolution. All 21,999 samples were pixel identical to the acquisition;
4,818 gave spectator rows, 87 remote rows and 13,204 own-HUD rows, and 3,890
were undecided. Holdout recordings were not used.

| Measure | Before | After |
| --- | ---: | ---: |
| Camera UNKNOWN seconds | 3,333 | 997 |
| Life UNKNOWN seconds | 4,059 | 1,076 |
| Round UNKNOWN seconds | 7,071 | 7,071 |
| Matches where any UNKNOWN count rose | – | 0 of 10 |
| Human labels sampled by the fresh run (72 of 78): correct / abstained / incorrect | 72 / 0 / 0 | 72 / 0 / 0 |

Per match (Camera, Life UNKNOWN seconds before to after): DEV2 320 to 101, 554
to 108; issue_oldfull001 438 to 116, 535 to 118; issue_oldfull002 457 to 101,
288 to 104; issue_oldfull004 231 to 83, 309 to 86; issue_newfull001 323 to 89,
428 to 79; issue_newfull002 333 to 82, 367 to 140; issue_freshfull003 299 to
126, 367 to 130; issue_newfull004 459 to 134, 519 to 122; issue_freshfull005
175 to 46, 266 to 66; first_new_cold 298 to 119, 426 to 128.

Changes between known values: life DEAD to ALIVE 937 seconds, camera
SPECTATOR to SELF 89, SELF to REMOTE 87, SELF to SPECTATOR 4. Life withdrawn
to UNKNOWN: 280 seconds (30 DEAD, 250 ALIVE). Life UNKNOWN to DEAD from the
measured spectator rule: 2,211 seconds. Before that rule (6e786ae) Life UNKNOWN
was 3,025 with 52 withdrawn seconds. In the sampled frames below every
DEAD that became ALIVE showed the recorder's own HUD with health; the old DEAD
was a death hypothesis carried past its Round or a victim display that did not
belong to the recorder.

The fresh run reproduces the replay of the stored observations: Camera agrees
in 21,925 of 21,999 seconds, differs between two known values in 8 and is
UNKNOWN on one side only in 66.

DEV2 alone (2,052 seconds, also reported on 2026-11-16): Camera 320 to 101,
Life 554 to 391; SELF to REMOTE 38, SPECTATOR to SELF 6.

### Protected recordings: final check (2026-11-19)

With the user's permission, all four full_match_5 recordings (7,414 seconds)
were acquired from the originals and measured once, with no tuning. UNKNOWN
seconds before / this PR / combined with #150: Camera 1,112 / 355 / 355, Life
1,318 / 368 / 255, Round 2,206 / 2,206 / 762. No match rose in any domain. Every
second of the combined run that changed between two known values was viewed
(248 seconds, AI review): 247 consistent, 1 contradicted. The contradicted
second (match 4, 1752) is a measured spectator value carried 1 s into the
purchase phase by the existing 2 s carry. Not carrying a measured spectator
value into a frame with a learned SELF claim fixed it but withdrew 134 Camera
and 64 Life seconds in the fixed comparison (the learned SELF claim is often
wrong while spectating), so it was not kept. No REMOTE was measured in these
matches.

Result-display rule (3d9ec86): it adds DEAD to 5 fresh-run seconds and 2
protected seconds and changes no known value; all 7 were viewed and show a
Round result while the recorder spectates the spike or a teammate. A wider
version keyed on the Round state instead of the result display also kept the
human-labelled DEAD at DEV2 207 s, but made one protected second already in the
next purchase phase DEAD, so the narrower version was kept and DEV2 207 s
remains an abstention.

### Random human GT: 80 frames of all ten matches (2026-11-19)

The user labelled 80 frames of the fresh run without seeing any prediction: 40
drawn uniformly from all 21,999 seconds and 40 drawn uniformly from the seconds
that #150 or this PR changed. Frames marked unknown are excluded. Correct /
incorrect / abstained:

| Sample | Domain | Base | This PR | Combined with #150 |
| --- | --- | --- | --- | --- |
| Uniform 40 | Camera | 28 / 1 / 10 | 34 / 0 / 5 | 34 / 0 / 5 |
| Uniform 40 | Life | 25 / 1 / 13 | 35 / 0 / 4 | 36 / 0 / 3 |
| All 80 | Camera | 52 / 3 / 24 | 70 / 2 / 7 | 70 / 2 / 7 |
| All 80 | Life | 38 / 6 / 35 | 73 / 0 / 6 | 76 / 0 / 3 |

This PR adds no incorrect value. The two remaining Camera errors were already
wrong in the base: an Astra astral form read as SELF (first_new_cold 1083, a
remote view this PR does not measure) and DEV2 2005, labelled SELF by the user
and SPECTATOR by both timelines, where the frame shows the spectator label and
a teammate's name at the lower left (the label may be worth a second look).

### Human GT: 36 DEV2 frames labelled by the user (2026-11-19)

The user labelled 36 sample frames of DEV2 without seeing any prediction
(camera SELF/SPECTATOR/REMOTE/unknown, life ALIVE/DEAD/unknown). Frames the user
marked unknown are excluded (Camera 29 and Life 34 frames remain). The frames
were picked for review, not drawn at random, so the counts are not an accuracy
estimate for the whole match. Fresh run, correct / incorrect / abstained:

| Timeline | Camera | Life |
| --- | --- | --- |
| Base engine | 19 / 6 / 4 | 17 / 0 / 17 |
| This PR (9e50d20) | 26 / 0 / 3 | 26 / 0 / 8 |
| This PR at 6e786ae | 26 / 0 / 3 | 16 / 0 / 18 |
| Combined with #150 | 26 / 0 / 3 | 28 / 0 / 6 |

All six base Camera errors are Owl Drone views read as SELF; this PR reads all
six as REMOTE. One correct DEAD (frame 34, DEV2 207 s, between a Round result
and the next purchase phase) becomes UNKNOWN: the measured own HUD of the next
purchase phase lets the existing return-tail option bracket the earlier victim
display. The earlier run-level review found 13 wrong and 1 correct DEAD among
such withdrawals, so the rule is kept.

### Visual review by the implementing agent (not human GT)

Frames decoded at the exact native PTS from the original recordings.

| Sample | Consistent | Contradicted | Undecidable |
| --- | ---: | ---: | ---: |
| Fixed comparison, all ten matches (64 frames) | 43 | 4 | 12 |
| of which life DEAD to ALIVE (16) | 16 | 0 | 0 |
| of which camera SPECTATOR to SELF (12) | 11 | 0 | 1 |
| of which life DEAD to UNKNOWN (8) | old DEAD wrong in 5 | | 3 |
| Fresh DEV2 changes (24) | 21 | 0 | 0 (3 abstentions were correct DEAD) |
| Fresh life DEAD to ALIVE, all nine matches with such seconds (62 of 657 seconds) | 62 | 0 | 0 |
| Fresh camera SPECTATOR to SELF, six matches (16 of 89 seconds) | 16 | 0 | 0 |
| Fresh life DEAD to ALIVE from the own-HUD-during-Round rule (24 of 282 seconds) | 24 | 0 | 0 |
| Fresh camera SELF to SPECTATOR (all 4 seconds, match result screens) | 3 | 0 | 1 |
| Fresh life DEAD to ALIVE added only when combined with #150 (12 of 158 seconds) | 12 | 0 | 0 |
| REMOTE frames (11 full frames, 7 crops) | 18 | 0 | 0 |
| Owl Drone views in a 252-frame sweep of one match | 11 of 11 read REMOTE | | |

Run-level review of the fresh run. Frames were decoded 0.2 s after the
sample time, except where noted; at a run boundary that offset can show the
next state, so boundary disagreements were decoded again at the exact sample
time.

| Every changed second or run of 6e786ae+1 | Consistent | Contradicted | Undecidable |
| --- | ---: | ---: | ---: |
| Camera SPECTATOR to SELF, all 89 seconds | 88 | 0 | 1 (third-party overlay) |
| Camera SELF to REMOTE, all 87 seconds | 87 (2 after decoding at the exact time) | 0 | 0 |
| Life UNKNOWN to DEAD from a measured spectator view, all 153 runs (2,231 s) | 146 | 0 | 7 (result screens, settings menu) |
| Life carried ALIVE withdrawn before a spectator view, all 144 runs (287 s) | old ALIVE wrong in 143 (death camera or spectator map already shown) | old ALIVE right in 1 | 0 |

Earlier run-level review (6e786ae), one frame per changed run:

| Changed runs | Consistent | Contradicted | Undecidable |
| --- | ---: | ---: | ---: |
| Life DEAD to ALIVE, all 201 runs (939 seconds) | 199 | 1 | 1 |
| Life DEAD withdrawn to UNKNOWN, all 16 runs | old DEAD wrong in 13 | old DEAD right in 1 | 2 |

The contradicted run was issue_newfull002 2485 to 2486: the own HUD with health
was measured up to 2484, the two carried seconds after it already show the
recorder's combat report after its death. The withdrawn correct DEAD was the
following run, 2487 to 2502: the spectator label is measured from 2488, but the
base rule kept a spectator view alone as a competing hypothesis. Both are fixed
by the measured spectator rule: 2485 to 2486 are now UNKNOWN and 2488 to 2502
DEAD. The undecidable frames
are an overlay over the whole screen and a map loading screen.

The four SELF to SPECTATOR seconds are match result overlays; in three of them
the spectated teammate's name panel is still visible under the overlay at the
lower left, so the recorder was spectating (the fourth is a full-screen
transition). The four contradicted values are one event: two seconds at the start of a
purchase phase in DEV2 (camera SPECTATOR and life DEAD), where measured
spectator rows kept a death latch alive and the learned own-view rows in the
buy menu could not end it. The undecidable frames are mostly Round or match
result screens.

## Limits

- Development matches only; holdout recordings were not used.
- The thresholds and geometry assume the recordings' HUD scale and language.
- REMOTE is measured only for the Owl Drone control hint of this recorder's key
  bindings. Other steerable abilities (Fade's Prowler, Cypher's camera, Skye's
  Trailblazer) and Astra's astral form were not reviewed and are still
  read as SELF when the own ability bar stays visible.
- A measured spectator label before a purchase phase can keep a death latch
  for the first seconds of the buy menu (one event of two seconds seen).
- The fresh run repeats the same ten development matches; generalization to
  unseen matches is unmeasured.
- Every changed Camera second of the fresh run was viewed; Life runs were viewed
  in at least one frame each, not every second.
- One withdrawn carried ALIVE (first_new_cold 1992) was correct: the recorder
  still had its own HUD one second before the spectator view.
- Pixel identity depends on the decoder: the recording machine's acquisitions
  and the container's acquisition each match their own decoder only.

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
| Life UNKNOWN seconds | 5,322 | 4,336 |
| Round UNKNOWN seconds | 7,230 | 7,230 |
| Camera REMOTE seconds | 0 | 87 |
| Fixed 69 attributes: correct / incorrect / abstained | 69 / 0 / 0 | 69 / 0 / 0 |
| Fixed labels (77, union scorer): Camera / Life correct | 20 / 20 (1 abstained each) | 21 / 21 |
| Supplemental 9 and 6 attributes | 9/9, 6/6 | 9/9, 6/6 |
| Frames: DEAD recorder with a first-person camera | 223 | 149 |
| Formal Facts/Events | 0 | 0 |

Seconds changed between known values: life DEAD to ALIVE 188, ALIVE to DEAD 2;
camera SPECTATOR to SELF 107, SELF to REMOTE 87, SELF to SPECTATOR 6. Life
values withdrawn to UNKNOWN: 862 seconds (abstentions; in the review below the
old DEAD was wrong in 5 of 5 decidable frames).

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
| Life UNKNOWN seconds | 4,059 | 3,324 |
| Round UNKNOWN seconds | 7,071 | 7,071 |
| Human labels sampled by the fresh run (72 of 78): correct / abstained / incorrect | 72 / 0 / 0 | 72 / 0 / 0 |

Camera UNKNOWN fell in every match (DEV2 320 to 101, issue_oldfull001 438 to
116, issue_oldfull002 457 to 101, issue_oldfull004 231 to 83, issue_newfull001
323 to 89, issue_newfull002 333 to 82, issue_freshfull003 299 to 126,
issue_newfull004 459 to 134, issue_freshfull005 175 to 46, first_new_cold 298
to 119). Life UNKNOWN fell in nine; in issue_oldfull002 it rose from 288 to 430
because DEAD values were withdrawn.

Changes between known values: life DEAD to ALIVE 657 seconds, camera
SPECTATOR to SELF 89, SELF to REMOTE 87, SELF to SPECTATOR 4. Life withdrawn
to UNKNOWN: 336 seconds (332 DEAD, 4 ALIVE). In the sampled frames below every
DEAD that became ALIVE showed the recorder's own HUD with health, mostly in the
purchase phase after a death in the previous Round; the old DEAD was a death
hypothesis carried past its Round.

The fresh run reproduces the replay of the stored observations: Camera agrees
in 21,925 of 21,999 seconds, differs between two known values in 8 and is
UNKNOWN on one side only in 66.

DEV2 alone (2,052 seconds, also reported on 2026-11-16): Camera 320 to 101,
Life 554 to 391; SELF to REMOTE 38, SPECTATOR to SELF 6.

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
| Fresh camera SELF to SPECTATOR (all 4 seconds) | 0 | 0 | 4 (match result screens) |
| Fresh life DEAD to ALIVE added only when combined with #150 (12 of 158 seconds) | 12 | 0 | 0 |
| REMOTE frames (11 full frames, 7 crops) | 18 | 0 | 0 |
| Owl Drone views in a 252-frame sweep of one match | 11 of 11 read REMOTE | | |

The four contradicted values are one event: two seconds at the start of a
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
- In the fresh run, 595 of the 657 DEAD to ALIVE seconds and 73 of the 89
  SPECTATOR to SELF seconds have not been viewed; the viewed samples were drawn
  at random across matches.
- Pixel identity depends on the decoder: the recording machine's acquisitions
  and the container's acquisition each match their own decoder only.

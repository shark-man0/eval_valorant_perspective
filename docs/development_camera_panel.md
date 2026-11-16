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
- A run of measured own-HUD rows after an elimination hypothesis keeps life
  UNKNOWN while the Round token is unchanged. It becomes ALIVE only when the
  Round has demonstrably changed: a measured Round result lies between the
  elimination and the run with only spectator or unmeasured rows in between, or
  the run continues without death, spectator, result or score change until a
  measured BUY with a new Round token. Unmeasured rows inside the run follow it.
  The return time stays unknown (`measured_view_return_history`).

The default path is unchanged.

## Validation (2026-11-16)

Ten admitted DEVELOPMENT matches, the same 21,999 second rows. All 32,089
native samples were decoded again from the original recordings; 32,089 were
pixel identical to the acquisition. The supplements used for this replay were
measured on JPEG crops (quality 92) of those frames. The label reference comes
from one match; thresholds were chosen on four matches and applied unchanged to
the other six. The own-bar prototype was available in 10 of 10 matches
(cluster 227 to 281 of 300; 0 spectator frames matched). A check of 301
full-resolution frames (one match, 1,000 to 1,300 s) with the module itself gave
the same label state as the crops for 301 of 301 frames (largest score
difference 0.027).

| Measure | Before | After |
| --- | ---: | ---: |
| Camera UNKNOWN seconds | 4,118 | 518 |
| Life UNKNOWN seconds | 5,322 | 2,632 |
| Camera REMOTE seconds | 0 | 87 |
| Round UNKNOWN seconds | 7,230 | 7,230 |
| Fixed 69 attributes: correct / incorrect / abstained | 69 / 0 / 0 | 69 / 0 / 0 |
| Fixed labels (77, union scorer): Camera / Life correct | 20 / 20 (1 abstained each) | 21 / 21 |
| Supplemental 9 and 6 attributes | 9/9, 6/6 | 9/9, 6/6 |
| Frames: DEAD recorder with a first-person camera | 223 | 51 |
| Formal Facts/Events | 0 | 0 |

Seconds that changed between known values: camera SPECTATOR to SELF 182, SELF
to SPECTATOR 5, SELF to REMOTE 87; life DEAD to ALIVE 1,191, ALIVE to DEAD 1.

Remote references come from one Owl Drone frame. Remote cues were measured on
the four matches whose recorder agent has a steerable or out-of-body ability
(two Sova, one Fade, one Astra): 50 and 49 frames in the Sova matches, 0 in the
others. The other six matches were not measured for REMOTE.

Visual review of decoded original frames by the implementing agent (not human
GT):

| Sample | Consistent | Contradicted | Undecidable |
| --- | ---: | ---: | ---: |
| Per-frame cues (24) | 20 | 0 | 2 (2 without a cue) |
| Camera changes (45) | 37 | 0 | 8 |
| Life DEAD to ALIVE (10) | 9 | 0 | 1 |
| Life UNKNOWN to ALIVE (6) | 6 | 0 | 0 |
| Life UNKNOWN to DEAD (1) | 0 | 1 | 0 |
| REMOTE frames (11 full frames, 7 crops) | 18 | 0 | 0 |
| Owl Drone views found by a sweep of 252 frames (2 to 24 s after each start in one match) | 11 of 11 read REMOTE | | |
| Life DEAD to UNKNOWN (4): the old DEAD was wrong in | 3 | | 1 |

The contradicted frame is a buy menu without visible camera evidence inside a
pending elimination hypothesis.

## Limits

- Development matches only; holdout recordings were not used.
- The thresholds and geometry assume the recordings' HUD scale and language.
- REMOTE is measured only for the Owl Drone control hint of this recorder's key
  bindings. Other steerable abilities (Fade's Prowler, Cypher's camera, Skye's
  Trailblazer) and Astra's astral form were not reviewed and are still
  read as SELF when the own ability bar stays visible.
- 35 seconds of DEAD in one match became UNKNOWN: a measured remote frame
  ended a stale elimination hypothesis that had supplied that DEAD.

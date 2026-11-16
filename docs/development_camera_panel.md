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

The recorder's own icons are learned per recording: 300 evenly spaced frames
with the label `ABSENT` are clustered and the dominant cluster becomes the
prototype. It is rejected when it is not a majority, or when any frame with the
label `PRESENT` matches it. A team never fields one agent twice and only
teammates can be spectated, so a matching bar identifies the recorder's own HUD.

Rows (`stream_kind: camera_panel`, strong evidence):

- label `PRESENT` gives `spectator`;
- label `ABSENT` and own ability bar give `owner_hud`;
- anything else gives no row. Label absence alone is never evidence.

`python -m valorant_ai_coach.temporal.camera_panel --video V --timeline T
--label-reference LABEL.png --output S.json` decodes exactly the timeline's
native samples, keeps only frames whose decoded pixels hash to the sample's
`native_pixel_sha256`, and writes a supplement for `export --supplement S.json
--measured-view-precedence`. The label reference is a private asset.

## Engine option `measured_view_precedence`

- In a frame with a measured `owner_hud` or `spectator` row, learned
  (`unqualified_view_model`) `owner_hud`/`spectator` claims are ignored. Other
  learned signals are kept.
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
(cluster 227 to 281 of 300; 0 spectator frames matched).

| Measure | Before | After |
| --- | ---: | ---: |
| Camera UNKNOWN seconds | 4,118 | 517 |
| Life UNKNOWN seconds | 5,322 | 2,598 |
| Round UNKNOWN seconds | 7,230 | 7,230 |
| Fixed 69 attributes: correct / incorrect / abstained | 69 / 0 / 0 | 69 / 0 / 0 |
| Fixed labels (77, union scorer): Camera / Life correct | 20 / 20 (1 abstained each) | 21 / 21 |
| Supplemental 9 and 6 attributes | 9/9, 6/6 | 9/9, 6/6 |
| Frames: DEAD recorder with a first-person camera | 223 | 51 |
| Formal Facts/Events | 0 | 0 |

Seconds that changed between known values: camera SPECTATOR to SELF 182, SELF
to SPECTATOR 5; life DEAD to ALIVE 1,189, ALIVE to DEAD 1, UNKNOWN to DEAD 1.

Visual review of decoded original frames by the implementing agent (not human
GT):

| Sample | Consistent | Contradicted | Undecidable |
| --- | ---: | ---: | ---: |
| Per-frame cues (24) | 20 | 0 | 2 (2 without a cue) |
| Camera changes (45) | 37 | 0 | 8 |
| Life DEAD to ALIVE (10) | 9 | 0 | 1 |
| Life UNKNOWN to ALIVE (6) | 6 | 0 | 0 |
| Life UNKNOWN to DEAD (1) | 0 | 1 | 0 |
| Life DEAD to UNKNOWN (4): the old DEAD was wrong in | 3 | | 1 |

The contradicted frame is a buy menu without visible camera evidence inside a
pending elimination hypothesis.

## Limits

- Development matches only; holdout recordings were not used.
- The thresholds and geometry assume the recordings' HUD scale and language.
- REMOTE is not measured; a remote view that keeps the own ability bar would be
  read as SELF.

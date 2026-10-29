# Development recorder episode hypotheses

This dependent Draft builds on #115 (common timeline) and #116 (current owner
observations). `temporal.game.DevelopmentGameTimeline` remains the single owner
of Round, life and camera state. No supplier implements another state machine.
Existing Production readers, default consumers, GT and fixed windows are intact.

## Observation API

`python -m valorant_ai_coach.temporal.killfeed_evidence` accepts an explicit
DEVELOPMENT policy, recovered owner input, native acquisition archive, image
directory, development victim-column profile, Tesseract executable and tessdata
directory. It validates Source/physical-match/epoch/roster/pixels/dimensions before
reading each retained image. The Source-bound recorder alias must appear as an
exact word with confidence at least 0.90 in both gray and bright-stroke renderings
of a bounded victim-name ROI. These renderings are correlated measurements, not
independent confirmation. Current spectator controls are required to attempt OCR.
Non-attempts and failures to match remain UNKNOWN, never evidence of being alive.

Outputs retain native sample contracts, raw OCR, ROI, uncalibrated confidence and
code/profile/executable/traineddata/input fingerprints. The geometry is a private,
exposed development experiment. It is not a qualified generic killfeed detector;
normal death versus downing and exact event time remain unresolved. The reader
emits `recorder_elimination_display`, never a qualified `death` signal.

```sh
PYTHONPATH=.:src python -m valorant_ai_coach.temporal.killfeed_evidence \
  --policy /PRIVATE/policy.json --owner-input /PRIVATE/recovered-cycle.json \
  --acquisition /PRIVATE/native/acquisition.json --images /PRIVATE/native \
  --profile /PRIVATE/victim-profile.json --tesseract /PATH/TO/tesseract \
  --tessdata /PATH/TO/tessdata --output /PRIVATE/new-run/killfeed.json

PYTHONPATH=.:src python -m valorant_ai_coach.temporal.replay \
  --policy /PRIVATE/policy.json --hud /PRIVATE/recovered-hud.json \
  --hud-supplement /PRIVATE/recovered-cycle.json \
  --hud-events /PRIVATE/new-run/killfeed.json --map /PRIVATE/map.json \
  --output /PRIVATE/new-run/timeline.json
```

The policy admits accepted DEVELOPMENT Sources only. Outputs are exclusive
private artifacts outside Git. No video decoding is performed by these commands.
The exact-frame human labels are read afterwards by the private comparison, never
by these prediction commands. This separation does not make exposed profile
selection or the three-point review a blind evaluation.

## Shared inference contract

Timeline v2 adds the following development behavior:

- A prior directly observed recorder ALIVE/SELF, an observed Round token, current
  SPECTATOR and current recorder victim-column support can form a
  `death_hypothesis`. Report/spectator alone cannot establish death.
- The ranked life estimate can be DEAD with competing DEAD/DOWNED/UNKNOWN
  hypotheses and explicit uncertainty. It does not establish normal death.
  Later direct DOWNED evidence within the guarded future window can revise the
  earlier ranking while preserving the candidate ID and revision history.
- A later observed BUY token followed by current recorder ALIVE/SELF can form a
  linked `return_hypothesis`, including when the first self observation is already
  ACTIVE. Same-Round self without observed revival remains unresolved.
- Source/epoch/profile changes, confirmed breaks, failed decoding and uncovered
  gaps reset pending hypotheses. Rules alone do not invent a death or new Round.
- Witness samples remain exact native PTS. Display brackets have no internal
  event timestamp. One-second views retain hypotheses, uncertainty, reasons and
  original evidence IDs. Formal Fact/Event collections remain empty.

## Optional exact-current-pixel sharing

`--fuse-exact-native-evidence` enables an additional experiment. It requires equal
Source ID/hash, integer native PTS, canonical rational timebase, native pixel hash
and dimensions. Encoded PNG bytes and acquisition IDs may differ. It reuses only
current raw measurements; another acquisition's inferred state is never copied.
Failed decoding or confirmed breaks exclude a frame from sharing.

`current_pixel_evidence_links` retains each observation's original and target
sample IDs. Shared evidence is one measurement, not an extra observation or an
independent vote. Each origin's producer/profile stream is checked separately:
an intermittent second observer is not a profile change, while a real change
within either origin still resets carry. Acquisition state lanes stay separate,
and semantic continuity remains UNKNOWN. Near timestamps and similar pictures
never qualify for sharing. Conflicting current observations preserve hypotheses
and abstain. This option remains off by default.

## Validation and remaining work

The private reproduction runs three conditions with identical recovered HUD,
native frames and Map pools: baseline, additional victim observations, and those
observations plus exact-current-pixel sharing. It runs the pinned actual Map
consumer for each condition. Timing and peak RSS cover replay only; OCR and
decode costs must not be inferred from those numbers.

The user confirmed three selected exposed frames as ALIVE/SELF,
DEAD/SPECTATOR, and next-Round ALIVE/SELF. The answer qualifies those points only,
not the intervals or exact event times. The new elimination observation improves
life agreement on these points from 2 correct/1 abstained to 3 correct; camera
agreement remains 3 correct. There are no independent population, normal/downed
classification or event-time accuracy estimates. Three correct points do not
complete continuous episode reconstruction or strict qualification.

The same-code fixed comparison retains 11,402 acquisition frames, 11,308 physical
points and 1,170 Source-second rows. The baseline has 11,609 observations;
the two additional-observation conditions have 11,736. The additional 127 records
contain two positive victim-slot measurements, not 127 recognized deaths.

| Measure | Baseline | Victim observations | Also share exact current pixels |
| --- | --- | --- | --- |
| Round UNKNOWN second bins | 963 | 963 | 951 |
| Life UNKNOWN second bins | 1160 | 1151 | 1149 |
| Camera UNKNOWN second bins | 1139 | 1139 | 1123 |
| Previously non-UNKNOWN Round values changed | 0 | 0 | 7 |
| Original native Round boundary witnesses retained | Yes | Yes | No |
| Actual Map consumer selections | 0 | 0 | 0 |
| Previously reviewed Map self-role losses still unrecovered | 4 | 4 | 4 |
| Current Map candidate acquisition views / unique physical points | 0/0 | 0/0 | 11/9 |
| Replay seconds / peak RSS MiB in the recorded run | 7.409 / 571.9 | 7.311 / 573.1 | 7.668 / 589.5 |

UNKNOWN bins include missing observations and parallel-acquisition disagreement;
they are not negative exposure or measured continuous duration. Victim
observations retain all previous known domain values and native Round boundaries.
They support one elimination and one linked return hypothesis. The exact-pixel
experiment introduces current BUY measurements into a lane previously carrying
ENDED, changing seven old estimates and native boundary witnesses. Their
correctness has not been reviewed; seven changed estimates are not seven proven
lost correct labels. This experiment remains **unadopted and off by default**.
Lower UNKNOWN counts and nine physical Map candidate points do not establish
accuracy. The actual consumer still abstains because required semantic
continuity/ownership evidence is unresolved.

The bounded 127-point cycle has 12 ALIVE, 22 competing DEAD and 93 UNKNOWN
life estimates with victim observations, versus 12 ALIVE and 115 UNKNOWN without
them. Only the three explicit human-reviewed points enter correctness metrics.
The other estimates, including conditional continuation, remain unverified.
All conditions retain five start/four end overlapping display-bracket groups,
which are not counts of independently correct events.

Local validation: 132 related tests, full-source mypy (143 modules), the CI Ruff
scope and classified text-I/O pass. The reproduction reruns current-image OCR,
all three common replays and all three actual pinned Map consumers. Complete
repository/Windows/package verification belongs to this Draft's own exact-head
CI; parent PR CI is not reused.

The older Map regression, including four reviewed recorder-role selections,
remains a release blocker. Candidate coverage is not position/Zone accuracy.
This Draft does not adopt a learning model, change evaluation specifications or
request a main merge. The earlier disjoint-match learning experiment remains
unadopted because proxy metrics do not establish recognition improvement.

HUD follow-up: validate victim-name/actor/normal-versus-downed observations on
additional independent episodes, including unread/occluded slots and false
attribution controls, then pass observations to this API. Map follow-up: preserve
the four existing role controls, validate marker identity/Zone at shared current
frames and consume UNKNOWN conservatively. Common-timeline follow-up: evaluate
transition brackets against independent temporal evidence and test uncertainty
revisions across additional matches. None should redefine the common states.

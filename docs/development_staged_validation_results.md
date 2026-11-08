# First staged DEVELOPMENT transfer and recovery candidates

This Draft builds on #135 (`4be4910`). Source registration, recognition research
and formal qualification remain separate. Main is unchanged. No other five new
recordings were decoded, viewed or supplied to models.

## Admission and immutable first prediction

Six newly supplied recordings were measured with format/stream probes and
SHA-256 before and after probing. Byte hashes were distinct from one another
and prior registry hashes. Physical separation from all prior recordings,
unedited full-match status and unused history were separately confirmed by the
user; different hashes alone do not establish these properties. A declared
content-blind SHA order reserves two DEVELOPMENT, two QUALIFICATION and two
FINAL_HOLDOUT recordings. Only the first DEVELOPMENT Source is activated.

The unchanged #135 observer, Profile, models, thresholds, native decoder and
state options were frozen before inference. A 20-second pilot produced 34
native points and informative HP/timer/state candidates. JSON/CSV and the
candidate evaluation handoff passed an explicit operator go/no-go inspection.
The subsequent full run completed before integrating the new recovery rule.
Both first predictions and their failures/limitations remain immutable.

| First whole recording, unchanged recognizer | Result |
| --- | ---: |
| Recording duration | 2,253.183 seconds |
| One-second rows / observed seconds | 2,254 / 2,254 |
| Retained native samples | 2,807 |
| Round BUY / ACTIVE / ENDED / UNKNOWN | 508 / 908 / 106 / 732 |
| Life ALIVE / DEAD / UNKNOWN | 1,451 / 323 / 480 |
| Camera SELF / SPECTATOR / UNKNOWN | 1,506 / 379 / 369 |
| HP / Timer / score-pair candidate seconds | 1,493 / 1,433 / 1,627 |
| Armor / current Ammo / reserve Ammo | 193 / 341 / 335 |
| Credits / visible weapon-label seconds | 1,063 / 391 |
| Round-start / Round-end candidates | 21 / 15 |
| Death / spectator / return candidates | 9 / 20 / 8 |
| Python peak RSS | 756.94 MiB |
| Acquisition and recognition wall time | 1,956.79 seconds |

These are output counts, **not accuracy or full episode correctness**. The Map
reader is `UNCONFIGURED`: zero Map/Zone/position candidates represent a missing
provider, not evidence that no markers or locations existed. A current generic
Map-name/geometry/owner calibration route remains unresolved. Displayed HUD
values and weapon labels do not prove recorder ownership or equipped weapon.
All full rows agree between JSON and CSV; the existing evaluation consumer
retains a null coaching decision and zero formal outputs.

## Fixed old-eight comparison

The optional `current_hp_return_candidate` reuses the one shared state engine.
It requires offline `return_display_tail`, weak current SELF evidence, supported
current numeric HP and a nearby directly observed next-Round owner return.
The visible combat report still prevents ownership qualification. Alternatives
and the forward estimate remain available; strict Map ownership and lifecycle
events do not gain authority. This is disabled by default.

On identical saved native inputs from eight exposed DEVELOPMENT matches,
17,693 rows remain. Life UNKNOWN falls from 4,395 to 4,342 and Camera UNKNOWN
from 3,495 to 3,442, selecting 53 unqualified positive bins each. Round UNKNOWN
stays 6,020. Among 83 prior exact attribute labels, 69 match observed native
points and 14 remain NOT_OBSERVED. The 69 observed attributes change from
65 correct / 0 incorrect / 4 abstained to 67 / 0 / 2. All 65 previous correct
attributes, including five DEAD and nine SPECTATOR controls, survive. These are
attributes, not distinct labelled frames; unlabelled changes are unscored.

The new Source's first whole prediction remains the frozen before result.
Any later same-native replay with this option is DEVELOPMENT analysis, never a
second unseen first application. The eight historical acquisition conditions
and sparse HUD sidecars differ from the new automatic whole-file acquisition;
candidate coverage across those cohorts is not a controlled accuracy gain.

## Rejected experiments and outstanding recognition work

- Map: retain 140 packets, 17,414 raw proposals, 16 provisional highlights and
  four prior provisional self-role controls. Strict recorder correspondence
  remains zero. Archived rim-score family ranking is circular as a validation
  witness. A preregistered outer-annulus feature ranked the old self highlight
  first in only 1/4 fixed positive controls, all from one physical match; reject
  it for selection. Exact original-pool guards prevent alias/foreign UI scores
  from being attached to unrelated candidate indices in application output.
- Credits: on the same 51 old images, inversion gives 9 candidates versus 11
  ordinary, gaining one and losing three. It gains none on the five comparison
  matches; reject it for the ordinary supplier. Existing Armor/Ammo/inventory
  observations are retained.
- Learning: 164 return-tail candidate points contain only two exactly labelled
  positive candidate points and no negatives. All eight physical-match
  leave-one-out training folds fail the preregistered class gate. No model is
  fit and no weights are adopted; the rule fallback contributes all gains.
- Round boundary accuracy, complete episode truth, strict Map correspondence,
  and new-recording value accuracy remain unmeasured or unresolved. Additional
  candidates, UNKNOWN reduction and successful CI do not establish them.

## Reproduction and next-stage order

Use `development_staged_six_intake.md` for the private declaration and frozen
pilot/full API. Use a clean frozen #135 checkout plus the admission wrapper for
the original cold experiment. The current changed runtime deliberately fails
the old protocol's active-runtime guard; do not replace old fingerprints to
claim a new first use. Preserve the old checkout and receipts.

For a **separate**, same-native research replay of a completed acquisition:

```sh
PYTHONPATH=.:src python -m valorant_ai_coach.temporal.application export \
  --timeline /PRIVATE/first-full/timeline_PRIVATE.json \
  --receipt /PRIVATE/first-full/completion_PRIVATE.json \
  --policy /PRIVATE/first-development/policy_PRIVATE.json \
  --output /PRIVATE/positive-application \
  --return-display-tail --current-hp-return-candidate
PYTHONPATH=.:src python -m valorant_ai_coach.temporal.viewer \
  --bundle /PRIVATE/positive-application/timeline_PRIVATE.json --policy /PRIVATE/first-development/policy_PRIVATE.json
```

The viewer references the original full-match video; candidate-only evaluation
is in `evaluation_PRIVATE.json`. It never promotes values to formal engine
inputs. Keep all real paths, media, PTS, responses, profiles and weights local.

Next consider the second DEVELOPMENT recording to examine whether these
problems and candidate recovery recur. Do not open it within this first work
unit. Freeze recognition code, models, settings, acquisition and assessment
items before QUALIFICATION 1, preserve its first output, then decide whether
QUALIFICATION 2 is justified. Open neither FINAL_HOLDOUT recording without a
separate governing decision. No generic six-source iteration is provided.

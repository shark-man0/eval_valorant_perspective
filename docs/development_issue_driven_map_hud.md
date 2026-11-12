# Issue driven Map and HUD development candidates

This opt-in development work adds an on-screen Credits reader and makes Map
marker competition visible. It uses the shared timeline's existing observation
and projection interfaces. Neither component changes Round, life or camera
state, qualifies a Fact/Event, or assigns a marker or HUD value to the recorder.

## Credits display

`CreditsSupplementObserver` wraps an existing pixel observer and appends one
separately fingerprinted supplier observation. Its configuration names the
parent observer, parent configuration and a frozen Credits ROI profile. The
research reader requires the specified frame size, a bounded bottom-right crop,
numeric display format and OCR confidence of at least 0.90. A missing or weak
reading remains `UNKNOWN` with its reason and OCR attempt. The fixed ROI has no
independent geometric qualification; it does not relax the parent HUD calibration
or Production thresholds.

The supplier uses the existing HUD-value observation schema with
`value_reader_method = development_credits_display_v1`, empty `signals`, and
`ownership = UNKNOWN`. A candidate has
`value_scope = displayed_credits_unattributed`. The screen can show a spectated
player, so a displayed amount cannot be used as recorder Credits or as evidence
for SELF. The existing application projector carries the amount into the
`hud.credits` candidate list with its exact native observation and sample refs.
The JSON and CSV outputs retain the same nested candidate data.

The frozen development run reused 51 saved native images from eight admitted
physical matches. The prior Credits reader produced 0/51 candidates because the
ROI was unconfigured. This profile produced 11/51 displayed-number candidates,
with at least one in each match; 40 remained `UNKNOWN`. The numbers were checked
against saved pixels as an image-derived plausibility review. They are not human
ground truth, an accuracy estimate or evidence of recorder ownership. Previously
recorded Armor, Ammo and visible inventory-label candidates use separate
suppliers. A visible inventory label still has
`current_weapon_selection = UNKNOWN`.

## Map marker competition

`map_correspondence` adds `same_appearance_competitor_indices` to each current
Map review. The indices point into the unchanged exact-native marker candidate
pool. A competitor shares the appearance reference fingerprint; this is a
review cue, not proof that either proposal identifies a particular player.
`provisional_highlight_ambiguous` records whether such a competitor exists.
The diagnostic contract is `development_map_correspondence_review_v2`; the
current Map projection transport remains v1.

In the separate 140-packet Map cohort, the original 17,414 raw proposals and
16 provisional highlights remain. All 16 highlights have one to three other
same-family proposals at different image centers. Four previously reviewed
self-role controls retain their provisional highlight and have competitors; the
reviewed non-self UI control has no highlight. Strict recorder correspondence
remains 0/140. No map coordinate, Zone, path or interval occupancy is inferred
from a candidate or from a gap. The Map cohort uses a different acquisition and
configuration from the eight primary full-match bundles, so its counts are not
part of a same-condition accuracy comparison.

## Connection and reproduction

Keep the Source policy, profile, original media, native observations and output
artifacts outside Git. An already admitted fixed-input run can connect the new
Credits observation sidecar through the existing application exporter:

```sh
PYTHONPATH=.:src python -m valorant_ai_coach.temporal.application export \
  --timeline /PRIVATE/shared-timeline.json \
  --receipt /PRIVATE/acquisition-receipt.json \
  --policy /PRIVATE/development-policy.json \
  --hud-values /PRIVATE/credits-observations.json \
  --output /PRIVATE/application-after
```

The sidecar must contain `observations`, with each original Source/native PTS,
timebase, epoch and pixel digest. The exporter admits each sample through the
Source policy and joins exact native evidence. It writes
`timeline_PRIVATE.json`, `timeline_1s_PRIVATE.csv`, an evaluation review and a
hash receipt. The generated candidate keeps its evidence ref; unmatched native
observations are retained for review. For an authorized acquisition already
available for reuse, the opt-in provider route is:

```sh
PYTHONPATH=.:src python -m valorant_ai_coach.temporal.application generate \
  --policy /PRIVATE/development-policy.json \
  --source-id ADMITTED_SOURCE_ID \
  --reader-config /PRIVATE/credits-supplier.json \
  --observer valorant_ai_coach.temporal.credits_provider:CreditsSupplementObserver \
  --reuse-acquisition /PRIVATE/completed-acquisition \
  --output /PRIVATE/application-after
```

The Map diagnostic can be reproduced from the same admitted shared timeline:

```sh
PYTHONPATH=.:src python -m valorant_ai_coach.temporal.map_projection \
  --policy /PRIVATE/development-policy.json \
  --timeline /PRIVATE/shared-map-timeline.json \
  --output /PRIVATE/current-map.json
```

Unit checks cover the Credits threshold, numeric format, frame mismatch,
parent-supplier preservation, and same-family Map alternatives. These checks
validate transport and abstention. Human review of displayed Credits, independent
marker roles, geometry, spectators and unseen recordings remains future work.

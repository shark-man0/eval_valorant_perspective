# Advisory HUD visibility

Purchase menus and Tracker windows can obscure current HUD values. A visible menu
does not establish BUY, recorder life, camera ownership or a Map correspondence.
The development application now displays these UI candidates separately from the
existing shared timeline state. No new state machine or Production rule is added.

`HUDVisibilityReader(tessdata, language="jpn+eng").inspect(native_bgr, ui)` uses
configured existing OCR languages, a fixed normalized header/center ROI and current
pixel UI anchors. Purchase-menu candidates require a confident close anchor plus
multiple category words. Tracker candidates require both branding and navigation
words; a scoreboard logo alone is insufficient. Missing analysis is NOT_ANALYSED;
unread text or no recognized target remains UNKNOWN, never proof of an unobscured
HUD. OCR errors remain explicit. Binary, language assets and code are fingerprinted.

The reader is an optional image-only API. It is not enabled by default or invoked
automatically throughout a recording. An existing observer can call it on its
native image; transport the result as a value-only observation with empty signals
and Map candidates, `context.stream_kind="hud_visibility"`,
`raw.schema="development_HUD_visibility_observation_v1"`,
`raw.hud_visibility=<measurement>` and `raw.formal_outputs=0`.

`build_application_timeline(..., hud_visibility_observations=rows)` and
`temporal.application export/generate --hud-visibility PRIVATE_OBSERVATIONS.json`
accept these advisory records. The JSON envelope uses `observations` as its list.
The CLI admits each record through the existing DEVELOPMENT Source policy.
Attachment requires exact Source ID/hash, native PTS, timebase, pixel hash and
dimensions. Re-acquisition epochs remain in the evidence; they do not count as
independent confirmation. Unmatched observations are retained without nearest-time
substitution. Stateful sidecars and foreign Sources are rejected.

Each application second adds `hud_visibility_observations` and
`HUD_visibility_sample_refs`; native evidence is available through
`HUD_visibility_observation_links`. JSON/CSV and the existing evaluation handoff
retain these fields. The shared engine's Round/life/camera, HUD values, Map,
native frames and event candidates retain their prior values.

Example (paths are private local inputs):

```sh
python -m valorant_ai_coach.temporal.application export \
  --timeline PRIVATE_TIMELINE.json --receipt PRIVATE_RECEIPT.json \
  --policy PRIVATE_DEVELOPMENT_POLICY.json \
  --hud-visibility PRIVATE_OBSERVATIONS.json --output PRIVATE_OUTPUT
```

## Development measurement

A fixed cohort of 22 previously retained native images from eight exposed
DEVELOPMENT matches was re-analysed. The output contains two purchase-menu and two
Tracker candidates; the other 18 produce no target-UI candidate. All agree with
AI visual inspection of this cohort. This is not human-labelled accuracy,
independent generalization evidence or proof that the other images are clear.
No labels were read by inference, no fitting occurred, and no new whole-video
visibility acquisition was performed.

All 22 records attach exactly to eight preserved whole-match application views
(17,693 second rows). Prior state, HUD values, Map, native frames and events are
unchanged. A real export CLI run also attaches the matching purchase-menu record
to a separately acquired full timeline; browser inspection confirms the candidate
and original-video seek. UNKNOWN game-state counts and recognition accuracy are
unchanged/unmeasured respectively. No formal Fact/Event is generated.

Reproduction requires the admitted private Sources, exact retained native images,
parent observer configuration and OCR assets. None are bundled in Git. Synthetic
tests verify word/anchor gates, exact-pixel joining, no state authority, mismatched
PTS/timebase/pixels/dimensions, foreign Sources and default NOT_ANALYSED behavior.
This change depends on the preceding Draft timeline stack and does not authorize
main integration or replace recognition qualification.

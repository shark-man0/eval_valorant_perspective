# HUD location observations on the common timeline

This dependent Draft builds on #118. A measured HUD location name describes the
currently viewed actor. The common engine keeps it as unassigned display evidence
until the same native acquisition supplies direct current recorder evidence.
The observer and Map projection never implement another life/camera state machine.
All outputs remain development-only, ownership UNKNOWN, with no qualified facts
or events and no geographic coordinates or paths inferred from a name.

## API and admission

`temporal.zone_observations.normalize_zone_batch(batch)` accepts a sealed
`development_hud_zone_measurements_v1` batch. It requires complete native samples,
the bounded frozen ROI/profile, original OCR words and bounding boxes, validated
TSV receipts, implementation/profile/model/binary SHA-256 fingerprints, and an
explicit declaration that labels/reviews were not used. Two correlated image
renderings must agree and pass the fixed 0.90 word-confidence and crop-border
checks. Disagreement or an unread name remains UNKNOWN. A reader/configuration
error is rejected rather than converted into an absent name.

This is an adapter for measured observations, not an OCR runtime or model bundle.
The external reader, model, private profile and native images remain separate.
Changing any reader/profile/model requires new evidence; old qualification cannot
be inherited. The two renderings are correlated and do not establish independent
identity evidence. A seal establishes content identity, not recognition truth.

The adapter emits ordinary observations with no game signals or marker candidates.
`temporal.game` alone adds these MapState fields:

| Field | Meaning |
| --- | --- |
| `zone_candidates` | Original Map Zone payloads plus unassigned viewed HUD names |
| `zone_observation_ids` | Attempted location observations, including unread ones |
| `current_recorder_zone_candidates` | Same-sample names associated with the existing direct current SELF gate |
| `zone_context_contract` | `development_zone_context_v1` |

Names retain their original sample, PTS/timebase/epoch, observation ID and producer
fingerprint. `zone_subject=unassigned_viewed_actor` does not identify the recorder.
The current-recorder hypothesis requires current owner HUD, ALIVE/SELF, and no
conflicting or failed current evidence. Carried SELF, spectator, remote camera,
terminal conflicts and exact-pixel aliases from another acquisition cannot supply
that association. Names are never carried to later samples. The associated copy
retains the observed candidate ID and separately records current-view evidence.

The engine also exposes supplier `zone_resolution` dictionaries in the dedicated
Zone view, alongside the older `zone_candidate` spelling. Raw candidate payloads
were already retained; this fixes their omission from the dedicated view.

`project_current_map(timeline)` adds unassigned viewed names and current-recorder
Zone hypotheses to native Map rows and one-second views. It checks original
observation content and shared associations. New Zone fields are additive;
frozen #118 timelines without the new contract remain readable. One-second rows
contain sampled evidence, not continuous occupancy or an event-time estimate.
HUD-only native observations remain in the full shared timeline even when no Map
row exists at that sample.

## Private CLI

```sh
PYTHONPATH=.:src python -m valorant_ai_coach.temporal.zone_observations \
  --policy /PRIVATE/policy.json --measurements /PRIVATE/measured.json \
  --output /PRIVATE/new-run/zone_observations.json
PYTHONPATH=.:src python -m valorant_ai_coach.temporal.replay \
  --policy /PRIVATE/policy.json --hud /PRIVATE/hud.json \
  --map /PRIVATE/map.json --hud-zones /PRIVATE/new-run/zone_observations.json \
  --output /PRIVATE/new-run/timeline.json
PYTHONPATH=.:src python -m valorant_ai_coach.temporal.map_projection \
  --policy /PRIVATE/policy.json --timeline /PRIVATE/new-run/timeline.json \
  --output /PRIVATE/new-run/map_views.json
```

The SourcePolicy checks every sample against the frozen DEVELOPMENT allowlist.
Outputs must be new paths outside Git. No media or review answers are opened by
these CLIs. Synthetic contracts and gate tests run with:

```sh
PYTHONPATH=.:src python -m pytest -q tests/unit/test_shared_zone_context.py
```

## Fixed development comparison

The same 140 previously retained native Map images produced 15 unqualified viewed
names: 14 with camera UNKNOWN and one with camera SPECTATOR. Eligible recorder
Zone hypotheses were **zero**. This is an evidence-preservation improvement, not
an accuracy improvement. No independent Zone labels were available; correct Zone
counts and false-attribution rates remain unmeasured.

The exact same normalized observation archive was replayed by frozen #118 and this
engine. Native Round/life/camera estimates, one-second states, transitions, Round
groups, original observations and current self-position candidates were identical.
Current position candidate samples stayed six; the four earlier reviewed Map role
abstentions remain unresolved. UNKNOWN Round/life/camera second bins stayed
963/1149/1137. These include unobserved bins and are not continuous exposure.

One local archive replay measured 5.655 s / 1049.5 MiB before and 6.140 s /
1089.8 MiB after. This harness loads a full frozen timeline and both observation
archives, so RSS includes comparison material. Runs shared the host; these are
single development measurements, not stable throughput or full video E2E claims.
The separate public CLI reproduction is recorded privately with its own runtime.

An earlier private probe produced plain text instead of TSV because a runtime
configuration was missing; its zero candidate count was invalid and excluded.
The corrected reader explicitly validates TSV. A later training-side crop change
kept weights, confidence, border rejection and two-render checks fixed. All exposed
probes remain archived; this was not a blind accuracy evaluation.

HUD follow-up: improve independent current SELF observability and measured name
readability, keeping errors distinct from absence. Map follow-up: consume these
shared fields, retain the four role regression controls, and obtain separate Zone
and coordinate evidence. Common-engine follow-up: retain conflicts and original
timing, and assess associations only with independent labels. No production,
main, GT, fixed-window or qualification changes are authorized by this Draft.

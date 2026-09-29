# VALORANT Visual Analyzer Patch v2

## 1. Purpose

This patch supersedes `valorant_visual_analyzer_patch_v1` and fills the world-view / minimap temporal-analysis gap between `valorant_hud_analyzer_patch_v2` and the v3 Round Package / Rule Engine pipeline.

It does **not** judge gameplay. It extracts observed facts and event candidates. `GOOD / IMPROVE / UNSCORED`, reasons, and coaching remain the AI Coach responsibility.

```text
Decoded video
  ├─ HUD Analyzer v2 -> HudObservation timeline
  └─ Visual Analyzer v2
       ├─ Always-on low-cost trigger scan
       ├─ Motion / minimap fusion
       ├─ Entity + engagement tracking
       ├─ Burst-start / first-shot detector
       ├─ Preaim / peek analyzers
       ├─ Utility / team-entry / site analyzers
       └─ Semantic adapter (bounded candidate windows only)
             ↓
        VisualObservation v2
             ↓
        VisualEventCandidate v2
             ↓
        Visual confidence + event fusion
             ↓
        Projection into strict v3 Event / StateSnapshot
             ↓
        Round Package v2
             ↓
        Deterministic Rule Engine -> AI Coach
```

## 2. Authority and non-goals

The existing v3 schemas/rules and HUD v2 remain authoritative. This patch is additive.

Non-goals:

- no audio analysis;
- no hidden-enemy inference;
- no full 3D reconstruction;
- no per-frame GOOD/BAD judgment;
- no always-on source-FPS semantic model processing;
- no exact per-bullet reconstruction of full-auto fire;
- no homography/back-projection preaim pipeline in MVP;
- no VLM-authored `exposed_directions_count`.

Unknown/null is preferred to fabrication.

## 3. Inputs and common clock

Visual Analyzer consumes:

1. original video frames with original-video timestamps;
2. HUD Analyzer v2 observations;
3. round boundaries when available;
4. map/zone providers defined by `map_zone_runtime_contract_v1.json`;
5. optional static peek exposure registry;
6. previously confirmed events for temporal fusion.

All components use the original video clock.

## 4. State gating

Target-player mechanics may be emitted only when the target player's first-person attribution is safe.

Allowed for target-player mechanics:

- `live_first_person`

Suppress target-player mechanics in:

- `spectator_first_person`
- `remote_control_view`
- `buy_menu_open`
- `expanded_tactical_map`
- transition / unknown

World/minimap context may still be consumed where appropriate.

Remote-control detection uses HUD v2 state plus `remote_view_detection_policy_v1.json`. When remote-vs-live is ambiguous, choose `unknown` and suppress mechanics.

## 5. Sampling and trigger bootstrapping

Use `visual_sampling_policy_v2.json`.

### Pass A — 2 fps
Broad context only.

### Pass B — 5 fps always-on trigger scan
This pass is the guaranteed low-cost trigger path. While `live_first_person`, request/consume:

- `ammo_current` at >=5 fps;
- cheap recoil / muzzle score;
- enemy visible transitions;
- minimap self displacement;
- location changes;
- utility cast candidates.

Pass B exists specifically so Pass C is not dependent on a signal that only Pass C could detect.

### Pass C — 15 fps micro window
Refine candidate windows around:

- ammo decrease / burst start;
- recoil/muzzle cue;
- enemy appearance;
- cover transition;
- utility cast;
- engagement transition.

### Pass D — native frame burst
Optional ±0.35 s burst only for first-shot/stopping timing when 15 fps is insufficient.

**MVP shot granularity:** one event around trigger/burst start, especially the first shot. Do not attempt to emit one reliable event per bullet during full-auto fire.

## 6. Visual confidence

Visual confidence is its own layer. It is neither HUD OCR confidence nor final AI Coach confidence.

Use `visual_confidence_policy_v1.json`.

- Tier A: strong deterministic/low-level signals.
- Tier B: temporal/spatial fused signals.
- Tier C: high-semantic or difficult events.

A detector must meet its tier threshold and independent-source requirements before becoming `confirmed`. Otherwise retain as candidate, set unknown, or suppress according to the policy.

Semantic-only moving-preaim facts are capped below deterministic-label confidence.

## 7. Shot detection

A `shot` event represents the **start of a firing action/burst**, not every bullet.

Preferred evidence:

1. ammo decrease consistent with firing;
2. recoil/muzzle temporal cue;
3. weapon state;
4. reload/switch/purchase exclusion.

Ammo increase is never a shot signal. A weapon change can cause an ammo discontinuity and must be excluded.

The always-on Pass B must be sufficient to open Pass C. Missing one HUD sample must not silently disable all shot-dependent rules, so cheap visual recoil/muzzle scoring is a redundant trigger.

## 8. Movement: macro and micro are different tasks

Do not use one evidence priority for all movement questions.

### Macro movement / position / rotation
Prefer:

1. minimap self-marker displacement;
2. zone/location transitions;
3. world optical-flow decomposition;
4. semantic sequence fallback.

### Shot-time movement / stopping
Prefer:

1. local world optical-flow translation near the shot;
2. weapon-bob / first-person motion cue;
3. high-cadence camera-motion decomposition;
4. minimap displacement only as supporting evidence.

If camera turning cannot be separated from translation, return `unknown`.

## 9. Aim and primary target

When multiple enemies are visible, `head_alignment_error_norm` always refers to `primary_target_ref`, selected by the engagement FSM.

Do not store an ambiguous scalar against an arbitrary enemy.

`detection_id` is a short-lived tracker association across adjacent frames. It is not a permanent enemy identity and need not survive long occlusion.

## 10. Preaim — MVP scope

Homography/back-projection is removed from the MVP path.

### Deterministic / CV-supported path
Allowed only when:

- target player is `live_first_person`;
- player translation is near-static/low;
- a trustworthy visible enemy head or static corner reference exists;
- crosshair timing is sampled densely enough.

Then `lead_sec` can be measured.

### Moving-peek path
If the player is translating materially, do not pretend a global homography can accurately back-project a near corner/head position. Use semantic keyframes only as a low-confidence factual fallback. The confidence is capped and cannot feed deterministic labeling.

## 11. Peek and PEEK-04

A basic `peek` may be detected from:

- cover/occlusion transition;
- supported player translation;
- newly revealed region / line-of-sight.

`peek_style` may use semantic assistance.

`exposed_directions_count` is special:

- VLM inference is forbidden;
- hidden/off-screen possible enemy lines are not inferred from the current frame;
- the only high-confidence production source is `map_peek_exposure_registry_v1.json` matched to a calibrated map position/anchor;
- if no registry match exists, the value is null and PEEK-04 cannot fire deterministically.

See `map_spatial_fact_policy_v1.json`.

## 12. Map zones and MVP availability

Rotation, team-entry, and named position facts require map semantics.

Preferred provider:

- static normalized minimap polygons for coarse zones/sites.

Optional fallback:

- auto-detected A/B site anchors with conservative proximity/persistence rules;
- macro groups only;
- confidence capped;
- never used for PEEK-04 exposure counts.

If no provider resolves the map, emit a feature-availability diagnostic rather than silently fabricating named events.

`tests/fixtures/coarse_zone_fixture_test_map.json` demonstrates the required geometry shape. Production map data remains a separate data-authoring/runtime-provider concern.

## 13. Rotation and team entry

`rotation_started/completed` require a resolved coarse `from`/`to` macro zone and sustained displacement.

`ally_entry_start/ally_enter_site` require ally minimap tracking plus resolved site boundary or conservative site-anchor fallback.

If map geometry is unavailable, related rule paths must be explicitly marked unavailable, not silently fail.

## 14. Utility slots and keybinds

Logical ability slots `C/Q/E/X` are canonical slot identities/positions, **not literal keyboard labels shown to the player**.

A player may rebind keys. Never OCR the displayed key text and compare it to `C/Q/E/X`.

Use `ability_slot_contract_v1.json`.

## 15. Remote-control views

Agent-specific templates are preferred, but v2 also defines cross-Agent fallback signals:

- normal weapon/ammo HUD disappears or becomes invalid;
- an ability slot is active/controlling/cooldown;
- remote reticle/overlay or non-player locomotion appears;
- normal player hands/weapon model disappears.

At least two independent signals are needed when no agent-specific template matches. Confidence is capped. Ambiguous cases become `unknown`.

Cypher Camera / Sova Drone / Skye Trailblazer remain explicit real-video validation tasks; Astra is the currently verified real sample.

## 16. Semantic adapter

Use `visual_semantic_inference_policy_v2.json`.

The semantic adapter:

- extracts narrow visual facts only;
- runs in a separate API request/context from AI Coach;
- receives no evaluation labels, coaching text, or rule-result context;
- has per-round and per-match call budgets;
- returns unknown/null on budget exhaustion.

It must never author `exposed_directions_count`.

## 17. Spatial projection into v3

`VisualObservation.spatial` contains intermediate-only debug fields such as `cover_edge_score`, source metadata, and confidence.

v3 `spatial_context` is strict (`additionalProperties:false`). Therefore use `event_projection_contract_v1.json` and remove intermediate-only fields before validation.

## 18. Event conversion

1. Detector creates `VisualEventCandidate`.
2. State gating applies.
3. Tier-specific visual confidence policy applies.
4. HUD/visual/semantic sources are fused as required.
5. Only confirmed candidates become v3 events.
6. Projection strips intermediate-only fields.
7. v3 event registry remains authoritative.

Compatibility note: `rotation_started.attributes.delay_since_enemy_info_sec` is consumed by the existing deterministic rule engine even though the current v3 event registry does not list it in `common_attributes`. Preserve it; see `base_compatibility_notes_v1.json`.

## 19. Required tests

In addition to v1 gating tests, v2 explicitly tests:

- reload ammo increase != shot;
- weapon switch ammo discontinuity != shot;
- full-auto burst => burst-start event, not per-bullet event stream;
- shot-time movement micro-evidence priority;
- moving preaim fallback confidence cap;
- PEEK-04 static-registry-only source;
- coarse-zone rotation happy path;
- TEAM-02 ally site entry happy path;
- shot detection inside smoke;
- multiple-enemy primary-target head alignment;
- cross-Agent remote-view fallback;
- ambiguous remote view => unknown;
- semantic call-budget exhaustion;
- Visual tier confidence promotion;
- strict v3 spatial projection;
- rebind-safe logical ability slots.

## 20. Cost and storage

Semantic/Vision calls are bounded. Default policy limits semantic adapter calls to 8 per round and 96 per match. Budget exhaustion produces unknown/null.

Keep JSON measurements and selected keyframes around candidates. Do not retain every decoded frame.

## 21. Supersession

This v2 patch supersedes Visual Analyzer v1. Codex should integrate v2 only if both are present.

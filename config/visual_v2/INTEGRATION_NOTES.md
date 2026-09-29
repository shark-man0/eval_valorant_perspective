# Integration Notes — Visual Analyzer Patch v2

## Base compatibility

Requires:

- `valorant_codex_ready_bundle_v3`
- `valorant_hud_analyzer_patch_v2`

This patch supersedes `valorant_visual_analyzer_patch_v1`.

## Merge order

1. Keep v3 schemas/config authoritative for final Round Package and coaching.
2. Keep HUD v2 authoritative for HUD recognition/state.
3. Add VisualObservation v2 and VisualEventCandidate v2 as intermediate runtime/debug contracts.
4. Use `visual_sampling_policy_v2.json` for frame scheduling.
5. Use `visual_confidence_policy_v1.json` before promoting candidates.
6. Use map/spatial contracts for zone-dependent facts.
7. Project confirmed visual candidates into strict v3 objects with `event_projection_contract_v1.json`.

## HUD scheduler integration

The Visual Analyzer requires an always-on low-cost trigger path. While `live_first_person`, the scheduler must obtain `ammo_current` at >=5 fps or request the existing HUD ammo ROI reader at that cadence. This is not a second independent OCR implementation; it is a scheduling requirement for the same HUD parser.

Visual Pass B also runs a cheap recoil/muzzle score as a redundant trigger.

## Map-dependent feature availability

The base `map_zone_contract_v1.json` may still be empty. Visual v2 therefore makes this explicit:

- high-confidence named rotations and team-entry require static/coarse map geometry;
- optional auto site-anchor fallback can produce only low-confidence macro site groups;
- PEEK-04 exposure count requires static peek registry only;
- missing map data must produce feature-availability diagnostics rather than guessed named facts.

## Ability slots

`C/Q/E/X` are logical slot identities. Never bind them to OCR of the user's displayed key label.

## Remote views

Agent-specific templates should be added incrementally. Until then, use the cross-Agent fallback in `remote_view_detection_policy_v1.json`; ambiguous remote/live attribution becomes `unknown`.

## AI separation

Semantic visual adapter and AI Coach must be separate API calls/contexts. Do not feed coaching labels/rule results back into fact extraction.

## Data retention

Retain:

- emitted candidate/event JSON;
- confidence/evidence measurements;
- selected keyframes for emitted or high-confidence rejected candidates.

Do not retain all decoded frames by default.

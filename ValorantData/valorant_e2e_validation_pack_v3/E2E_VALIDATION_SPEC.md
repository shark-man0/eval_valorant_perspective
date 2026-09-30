# VALORANT E2E Validation Pack v3

## Purpose

Validate observable facts through the real pipeline:

`video -> HUD Analyzer -> Visual Analyzer -> Map/Zone Resolver -> Round Package -> Rule selector`

This pack does **not** prescribe GOOD/IMPROVE coaching labels.

## Canonical timebase

All canonical times are container presentation timestamps in seconds from container start. The video stream begins at `0.036003s`. Every reference-frame filename contains the requested extraction time, while `ground_truth/frame_pts_sidecar_v3.json` records the nearest exact presentation PTS from the source packet stream. The largest filename-to-PTS delta is constrained to at most one source frame.

The source contains a real game-content discontinuity at approximately `74.433 -> 74.450s`: encoded PTS is continuous, but the visible game timer and score jump. Temporal derivatives or causal durations may not cross this boundary. `continuous_segments` declares where temporal reasoning is permitted.

## Ground-truth types

- `point_event`: observed transition bracketed by last-absent / first-present evidence.
- `state_interval`: a confirmed state with a core interval, outer/don't-care interval, and where available explicit start/end edge brackets.
- `ownership_interval`: owner of the current view (`self`, `self_dead_ui`, `teammate_spectated`).
- `snapshot`: factual UI/HUD values at one PTS.
- `visual_observation`: directly visible evidence such as muzzle flash. These are now executable assertions, not passive documentation.
- `derived_expectation`: contract-derived result such as Map/Zone `zone_id`; kept separate from purely visual facts.

Unspecified facts are unknown, not false, unless a negative assertion closes the relevant category/window.

## Ownership is first-class

After the target player dies, the teammate view contains valid gameplay, HUD values, location labels, enemies, and muzzle flashes, but they do not belong to the target player. v3 evaluates ownership intervals directly and keeps spectator location labels in `spectated_location_label_raw` rather than silently treating them as player location.

## State-edge policy

Astral Form, smoke, and buy-menu edges are re-bracketed from source frames. For those states, the detector interval start must land inside the observed last-absent/first-present bracket, and the end must land inside the observed last-present/first-absent bracket. This replaces broad 0.1–0.5s state-edge tolerances where source evidence permits tighter bounds.

## Shot/reload policy

The real clip contains a visible reload followed by three muzzle-flash observations. Because Visual Analyzer v2 defines shot granularity as burst/trigger-start rather than per-bullet, the real-video Round Package accepts 1..3 `shot` events in the verified firing window. `fixtures/shot_granularity_contract_v1.json` independently fixes the logic contract:

- separated semi-auto trigger starts -> separate shot events;
- one continuous full-auto burst -> one burst-start event;
- reload ammo increase -> zero shot events;
- weapon-switch ammo discontinuity -> zero shot events.

The synthetic fixture validates event semantics, not visual perception.

## Utility policy

This clip visibly contains Astra state/effects, but v3 still does not fabricate `utility_used` from a purple effect alone. The production contract requires ability charge/availability transition plus cast/world evidence when observable. Exact `utility_used` remains partially covered until a clean dedicated fixture exists.

## Map/Zone policy

The real video validates raw Japanese labels and selected contract-derived coarse zones. v3 also includes `fixtures/map_zone_synthetic_v1.json`, an independent geometry/calibration oracle for point-in-polygon, calibration, and boundary ambiguity. That synthetic fixture proves resolver mechanics; it does **not** prove that Summit polygons are geographically exact.

Observed Japanese labels that were missing or spacing-variant in the existing Map/Zone vocabulary are supplied as a provenance-preserving overlay under `integration_overrides/map_zone_v3/`.

## Discontinuity enforcement

Runtime E2E traces expose `temporal_features`. Any feature named by `NEG-CONTENT-JUMP-SPAN` fails if its interval spans the known content jump. This closes the v2 gap where the rule existed in GT but the lightweight evaluator did not execute it.

## Confidence

v3 checks structural confidence sanity only:

- confidence values must be finite and in `[0,1]`;
- layer-specific confidence may remain separate;
- Ground Truth must never manufacture confidence;
- no minimum confidence is inferred merely because an event is true.

Statistical calibration/reliability curves require a larger labeled corpus and remain an explicit data-acquisition requirement.

## Audio

Semantic audio analysis remains outside MVP. Transport is now testable: the source contains three stereo AAC tracks, and evidence clips are expected to preserve all three tracks. `tests/validate_media_transport.py` can validate a generated clip when supplied.

## Leakage boundary

Production runtime may read only the source video and `inputs/e2e_inputs_v3.json`. `ground_truth/`, evidence assets, generated assertions, sidecars, and fixture expected values are evaluator-only. `validate_pack.py --project-root` scans production Python for obvious GT leakage.

## Required runtime trace

`schemas/e2e_output_trace_schema_v1.json` defines the E2E trace consumed by `tests/evaluate_trace.py`:

- events
- state intervals
- ownership intervals
- snapshots
- visual observations
- temporal features

## Remaining real-data limits

Synthetic fixtures now cover several logic gaps, but they do not replace perception evidence. The exact recordings still needed are enumerated in `fixture_requirements/real_video_gap_manifest_v1.json`.

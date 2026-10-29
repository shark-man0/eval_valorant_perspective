# Map observations for the common timeline owner

This is a **provisional Map consumer boundary**, not a common timeline engine.
The common owner and its connection API are still being prepared. This branch
preserves the existing Map/HUD experiments and adds an opt-in route that never
constructs `DevelopmentOwnerTimeline` or `DevelopmentSelfTimeline`. Production
contracts and the default recognizers are unchanged. All outputs are
`development_only`, `ownership=UNKNOWN`, `formal_outputs=0`.

## Responsibilities and connection

`make_map_observation` packages the existing native candidate pool, current
marker UI evidence, reference comparisons, Profile/reference fingerprints,
Map/build/geometry version and current calibration. It preserves every raw
candidate, including unassigned geometry-only coordinates. The Map-only initial
candidate is the existing unique joint rim/reference selection, without the
legacy HUD/HP/life decision. Scores are uncalibrated evidence, not probabilities.
Reference matches and highlights are **not recorder ownership proof**.
The complete input geometry envelope is retained as `geometry_observation`,
including supplied detector and execution provenance. Its independently copied
calibration/version summary must agree with that envelope on consumption.

`DevelopmentMapStateConsumer.observe` consumes that packet, native appearance
features, acquisition continuity receipt and an optional external state snapshot.
It links observed endpoints using the existing mutual appearance/position kernel.
It does not recognize Round, life, camera or account identity. Without external
state it exposes no recorder-associated current position; the raw packet remains
available to the common engine. External state never supplies a marker ID.

The integration owner should implement an adapter to this boundary, or agree a
replacement API before connection. Do not copy these strings into another game
state model. Each external snapshot is sealed by `context_sha256` over the other
fields using the existing canonical `_digest` helper:

| Field | Required meaning |
| --- | --- |
| `schema` | `map_consumer_provisional_v1` |
| `sample_sha256` | Exact native sample, including Source SHA, epoch, PTS/timebase and image hashes |
| `producer_fingerprint`, `revision` | External engine/adapter implementation and snapshot revision |
| `origin` | `common_engine`, `human_exact_frame`, or `controlled_ablation`; never conflate these |
| `round_state` | External BUY / ACTIVE / ENDED / INTERMISSION / UNKNOWN |
| `recorder_life` | External ALIVE / DEAD / DOWNED / UNKNOWN |
| `camera` | External SELF / SPECTATOR / REMOTE / UNKNOWN |
| `recorder_correspondence` | supported / conflicting / UNKNOWN; must address recorder-to-current-camera correspondence, not just Agent agreement |
| `round_token` | External opaque Round scope, or null if unresolved |
| `self_view_round_token` | Scope in which external evidence reconfirmed SELF; must match the current Round |
| `tracking_epoch` | External invalidation token; change on source/semantic breaks, including intervening camera/life transitions missed by Map sampling |
| `source_continuity` | continuous / discontinuous / UNKNOWN; semantic permission is separate from native receipt validity |
| `evidence_sha256s` | Nonempty references to the upstream observations, reasons and uncertainty ledger |
| `qualification`, `ownership`, `formal_outputs` | development_only / UNKNOWN / 0 |

These are requirements on a trusted development producer, not a cryptographic
proof of the inferred state. The checksum detects mutation, not human truth.
No automatic common-engine accuracy can be measured until that producer exists.
Human state applies only to reviewed native samples; a reviewed frame does not
authorize propagation to intervening frames. Controlled state is a contract
ablation and cannot be counted as automatic recognition.

## Stops, resumption and missing observations

Selection needs external ALIVE + SELF + supported recorder correspondence +
BUY/ACTIVE + reconfirmation in the current Round + continuity permission.
SPECTATOR/REMOTE, DEAD/DOWNED and ENDED/INTERMISSION explicitly stop it. UNKNOWN
does not become SELF. Observing a spectator does not change recorder life to DEAD.

Source/epoch/timebase, Profile/ROI/frame shape, Map/build/geometry, reference
context, external producer/origin/Round/tracking epoch changes discard the
association. Native continuity additionally needs exact previous/current sample
hashes and a verified receipt, with positive native PTS gap at most 0.3 seconds.
Normal PTS cadence alone never grants semantic continuity. A new scope requires
fresh unique current-image Map evidence; Round change alone cannot initialize it.

Within one eligible, verified stream, a missing marker preserves an identity
candidate and the original `last_known_observation`. Current observation is null.
A unique appearance/position reappearance within 0.6 seconds can resume in a new
observed segment. Ambiguity/conflicting current UI cannot silently switch the
identity. No missing coordinates or edges across the gap are generated. A fresh
highlight cannot override an unresolved retained identity. After the 0.6-second
association horizon expires, fresh unique evidence can initialize a **new**
lineage without connecting it to the historical one. Historical positions
carry their original native sample and are explicitly non-current. Scope changes
clear historical geometry too. These bounds reuse the existing Map research
policy and do not qualify tracking accuracy.

## One-second output and existing paths

`aggregate_map_seconds` groups acquired records into native-time `[s,s+1)` bins,
with Source PTS zero as the explicit origin. It keeps all native observations,
state snapshots, reasons, current measurements and stale history. It creates no
empty seconds and does not treat the final point as the position at a bin end.
Different scopes in the same second remain separate rows. Duplicate/backward
native samples are rejected; data is not silently sorted. The common owner can
represent missing seconds using its own state model.
The consumer itself also rejects nonincreasing native time per Source/epoch,
even after a camera veto, and clears its retained history on rejection. A
backward input therefore cannot expose a later sample as a past last-known
position. The raw input can still be quarantined by the calling acquisition
layer; it must not silently reorder it or fabricate an acquisition epoch.

`map_candidate_path_record` adapts consumer output to the existing private
`analyze_candidate_path` / `write_candidate_path_html` pipeline. Use the
development Registry and `ZoneResolver(controlled_player=False)`, resetting its
history on missing positions or segment/scope changes. Supply only actual
measurement scores and current calibration, never a fabricated confidence.
The adapter rejects formal, different-Map, different-frame or different-time
Zone envelopes and discards held-from-previous Zone labels. Neither a named Zone
nor a connecting chord proves continuous occupancy, a traversable route or a
qualified self position. Boundary uncertainty and absolute accuracy remain
independent measurements.

## Private replay

From this checkout, with a runtime containing this package, NumPy and OpenCV:

```sh
python scripts/diagnostics/development_map_handoff.py \
  --input /absolute/private/map_plan.json \
  --output /absolute/private/new_map_result.json
```

Input is `{ "rows": [...] }`; each row supplies `image_path`, `sample`, `pool`,
`ui`, `appearance`, `geometry`, `reference_context_fingerprint`, optional
`context`, and optional `continuity`. Images must match the exact native pixel
hash. This CLI does not discover recordings, decode videos, read HUD or infer
game state. No context is the fail-closed default. Existing outputs are never
overwritten. Keep plans, images, results, positions, individual PTS, Profiles,
aliases and HTML private. Public tests use synthetic images only.

## Duplicate state inventory and integration plan

| Existing component | Handoff disposition |
| --- | --- |
| PR107 `DevelopmentSelfTimeline` life/view hypotheses | Preserve research; common owner selects/replaces state logic |
| PR112 `DevelopmentOwnerTimeline` life/camera/identity state | Preserve baseline; new Map route does not instantiate it |
| PR112 `DevelopmentOwnerTracking` image links plus local owner state | Preserve baseline; extract unchanged native feature function and reuse generic spatial kernel |
| PR112 owner binding HUD/HP/spectator gating | Preserve baseline; Map emits only joint UI/reference evidence; external producer owns semantic permission |
| PR111 owner observations and owner-map temporal state | HUD-owned, unchanged; common owner should reuse observations selectively and replace duplicate state maintenance |
| PR74 MapTimeline acquisition/coordinate/Zone history | Preserve existing behavior and isolation; do not turn it into another game-state engine |
| Generic marker associations and candidate trajectory | Remain Map-owned measurement/endpoint logic; no life/round inference |

The preserved local research commit beyond PR112 is not imported into this route.
No whole-PR merge, history rewrite, shared state-schema edit, HUD threshold
change, Production event emission, protected-source use or Full E2E is needed.

Next integration steps: agree the external adapter, supply real state evidence
and tracking invalidations, run the same native inputs in A (single frame),
B (Map temporal), C (actual common state), then validate continuous Round and
death/spectator/reentry episodes. Until then, C with no producer is deliberately
UNKNOWN and controlled injected states only test the boundary. A Map handoff
implementation does not complete the common engine's recognition Goal.

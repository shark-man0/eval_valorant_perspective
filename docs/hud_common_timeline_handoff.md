# HUD supplier handoff to the common temporal engine

## Responsibility and dependency boundary

This is HUD instruction ①, stacked on Draft PR #111 at `f94c31a`. It does not
implement instruction ③'s common state engine or take over Map instruction ②.
PR #107 remains a reference for life/view inference, PR #108 for raw Score
observations, and PR #112 remains owned by the Map task. No wholesale merge,
Production replacement, qualification, threshold/GT change or main merge occurs.

The supplier exports **what was measured**, including non-detection, unavailable
probes, contradictory/raw values and original uncalibrated scores. It does not
maintain BUY/ACTIVE/ENDED, recorder life, camera state or ownership. No output is
a formal Event/Fact. Existing production/native measurement and qualification
interfaces remain untouched.

## Input and API

`hud.development_observation_export` reuses `FrameRecord`/`SourceAcceptance` and
`freeze_native_sample`, rather than inventing a second Source/GT/time contract.

- `export_owner_ui(frame, source_id, ui, profile)` projects the existing
  `DevelopmentOwnerUI.inspect` result. Keep its exact reader/Profile fingerprint
  and original image/cache receipt. Shared HUD, agent glyphs, spectator controls,
  activated spectator alias, purchase and Report are observations, not ownership.
- `export_round_readers(frame, row, reader_fingerprint=..., profile_fingerprint=...,
  rois=...)` projects existing offline Round reader output. Score/Timer/Result
  literals, sources, scores, component Geometry and display context survive.
  A decimal Timer is never rewritten as m:ss. Low-confidence/unusable outputs
  are not accepted merely because they were transported. Native rows with
  `analysed=false` retain `NOT_ANALYSED` status and never become absence evidence.
- `validate_packet(packet)` validates the serialized binding/lineage. It does
  not reread Source bytes, qualify calibration, establish visual continuity,
  validate GT, or make a recognizer result true.
- `export_boundary_hint(kind, bracket, packets=..., producer_fingerprint=...,
  confirmation_witness=None, producer_evidence=...)` transports an **existing**
  Round start/end proposal. It does not implement new association rules. Every
  referenced native witness must match exported packets. Wrong Source, epoch,
  timebase, pixels, reversed order and promoted formal outputs are rejected.

A packet retains Source SHA/ID, native integer PTS, rational timebase, acquisition
identity, frame encoded/pixel hashes, ROI pixel rectangles, physical-match group,
registry/extraction/Exposure fingerprints, reader/Profile/adapter fingerprints,
raw measurements and continuity observations. An unavailable ROI remains null;
never reconstruct it from a presumed HUD position. Multiple ability glyph ROIs
are retained together in the corresponding measurement evidence.

`native_second_index = floor(native_pts_tick * native_time_base)` is an **address
on the native clock**. It is not video-relative zero, an event timestamp or a
continuity proof. Key it with Source and acquisition epoch. The common engine
owns any Source-origin normalization and actual one-second state aggregation.
All precise frame times remain present. Bundle order follows the archived input
groups, not a guaranteed global temporal order: the common engine must order and
validate observations within each Source/acquisition before carrying state. Missing packets/seconds do not become
negative observations, and multiple observations per second are not discarded.

The measurement list can contain correlated probes with the same semantic name;
retain the full entries and evidence rather than collapsing them into a name-keyed
dictionary or counting them as independent votes.

Statuses deliberately preserve reader meanings. `not_detected` is not a human
negative or a calibrated absence. False owner/remote support is UNKNOWN. A
spectated display alias, including the recorder's own alias string, cannot assign
recorder ownership. Return/downed/remote/death detectors that are not configured
remain unavailable/UNKNOWN; the exporter does not manufacture their values.

## Boundary timing and practical versus strict evaluation

Hints retain the before/after witnesses and native uncertainty interval. The
upper observed endpoint is the **display candidate** address, not an inferred
internal game End/Start. A separately supplied confirmation witness must be a
real exported point at or after that endpoint in the same Source/epoch/timebase.
If the legacy report did not persist a separate confirmation time, keep it null;
do not choose a midpoint, timeout, or the last convenient supporting frame.
The underlying support witnesses stay in the archive and packet set.

UNKNOWN producer candidates remain UNKNOWN. Existing Result/Score/Timer
association and buy-to-next-clock diagnostics are preserved as input producers,
not copied into a second persistent game-state machine. One-second practical
metrics belong to the common-engine comparison; they do not replace canonical
GT, the existing ±0.1-second metric, source-continuity checks or qualification.

## Reproducible private replay

The input bundle has version `hud_supplier_replay_input_v1`, `owner_frames`,
`round_frames` and `boundary_hints`. Each frame entry includes its serialized
existing FrameRecord and existing reader output. Owner entries also contain their
private Profile; Round entries provide archived reader/Profile fingerprints and
actual normalized ROI bounds. This is a private archive, never a Git fixture.

```sh
PYTHONPATH=.:src python -m scripts.diagnostics.export_hud_observations \
  --review-session /PRIVATE/registered-batch/review-session \
  --input /PRIVATE/hud-replay-input.json \
  --output /PRIVATE/new-handoff-run/observations.json
```

The output's parent must be a **new external private directory**. Existing runs
are not overwritten. The CLI reuses frozen review-session/registry validation,
requires registered accepted DEVELOPMENT/DEVELOPMENT Exposure and the same
physical-match group/manifest/allocation anchors, bounds inputs, buffers before
release, writes with existing private/exclusive I/O and appends the existing
Exposure journal. It never opens protected video files or decodes video.
Preserve original acquisition/decoder/cache receipts with the bundle: replay
checks transport, not the continued existence or semantic correctness of pixels.

## State-management overlap and migration ownership

| Existing component | Existing responsibility | Handoff / common-engine action |
| --- | --- | --- |
| `DevelopmentOwnerUI` | Current image probes | Keep as supplier; use exported measurements. |
| `DevelopmentSelfTimeline` (PR107) | Recorder life/view, death/reentry latch | Preserve as reference; common owner selects/reuses its rules. HUD adds no new transitions. |
| `DevelopmentOwnerTimeline` (PR111) | Native adjacency, carry, Report lifecycle, Round hints | Preserve for A/B baseline; transfer carry/dedup/reentry policy to the common owner. Do not run a second authoritative instance. |
| Offline `round_transition_evidence` | Native Score/Result/Timer association | Keep fixed producer reports/diagnostic reference; common owner decides pending/confirmed game state. |
| Offline `round_lifecycle_evidence` | End/Buy/next-clock chains | Export existing native brackets/witnesses, without another persistent Round FSM. |
| `HudDirectEventBuilder` / qualified lifecycle | Existing production and qualification path | Remain unchanged and isolated; this supplier cannot authorize them. |
| `DevelopmentOwnerMapPipeline` | Calls owner timeline before Map | Common/Map owners replace its owner-state source using the shared API after review; HUD does not edit Map code. |
| `SelfMarkerTracker` / local owner tracker | Appearance identity and local motion | Map-owned tracking memory stays separate from game life; consume shared context when integrated. |

Until the common owner approves its model/API, these are supplier proposal APIs,
not a declaration that the shared engine already exists or that duplicate state
has been deleted. No new instance is connected to Production or the old pipeline.

## Validation and remaining integration work

Synthetic tests cover exact native time retention, UNKNOWN/uncalibrated literals,
foreign UI/Profile/Source rejection, protected registry entries, malformed native
brackets, later confirmation, nested foreign witnesses, ROI bounds, forbidden
state fields and nonfinite scores. Synthetic tests are not real-image accuracy.

Private real replay uses existing DEVELOPMENT observations only. It must compare
all transported reader values and candidate intervals to their immutable inputs,
retain original Human evidence separately, count unique physical events rather
than repeated epochs/frames, and report unreviewed cases without accuracy claims.
No new Human review or Full E2E is needed for this transport-only handoff.

Integration-owner follow-up: approve the packet API; implement the sole shared
one-second model; resolve later evidence and confirmation; join eligible HUD/Map
observations without stitching discontinuous epochs; compare true/false/UNKNOWN,
strict versus practical timing and Map attribution on the same inputs. A complete
reviewed death→spectator→return episode is still missing. Transporting points and
existing boundary hints does not complete that phase or prove recognition gain.

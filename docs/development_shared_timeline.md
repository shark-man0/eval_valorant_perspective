# Common development game timeline

HUD and Map now have one opt-in temporal owner, `temporal.DevelopmentGameTimeline`.
Their suppliers export exact observations; the integration entry point does not
instantiate either supplier's independent life/camera/Round state machine.
Production, qualification and canonical evaluation remain isolated. This is a
Draft development API, not an approved recognizer or a main-merge proposal.

## State and evidence contract

| Domain | Values / content |
| --- | --- |
| Round | BUY, ACTIVE, ENDED, INTERMISSION, UNKNOWN |
| Recorder life | ALIVE, DEAD, DOWNED, UNKNOWN |
| Camera | SELF, SPECTATOR, REMOTE, UNKNOWN |
| Map | Unassigned marker/position/Zone hypotheses, observation presence, association evidence, UNKNOWN |

`observation()` binds Source ID/SHA, acquisition/epoch, integer native PTS,
canonical rational timebase, image/pixel hashes, dimensions, producer/Profile
fingerprints, original measurements, continuity cues and Map candidates.
Observation IDs address immutable content. The native identity helper is
selectively adapted from PR109; the image recognizer is not copied with it.
Scores retain their original meaning, including uncalibrated scores.

`DevelopmentGameTimeline.add()` validates and copies a normalized observation;
`retract()` removes a specified observation from the development ledger;
`rebuild()` deterministically projects one revision. Returned data are detached
from the internal ledger. Original observations, inferred states and the separate
`qualified_facts`/`qualified_events` collections are retained independently.
The latter are always empty: this API has no qualification issuer.

Each state contains its alternatives, reason, uncertainty, observation IDs and
origin. Transitions retain exact before/after samples. Pending Score-transition
candidates retain a stable ID, then gain actual later Result witnesses on replay.
A confirmation sample is an observed evidence time; it is not an internal game
event timestamp. Missing internal event time stays null. Revision history records
changed samples and candidate statuses. There is no silent GT writeback.

## One-second time axis

`seconds` uses one Source-native clock. Index is floor(native PTS × timebase),
without moving the clock origin or rounding event time. Each second references
all retained exact samples and all parallel acquisition views. Multiple states
within a second remain visible; a mixed second is UNKNOWN in its summary.
`acquisition_seconds` retains the original acquisition-addressed views.

Unobserved gaps between retained windows produce explicit UNKNOWN second bins.
They are not negative exposure, recovered play time, continuous movement or
fully reviewed duration. Epochs are never stitched into a state continuation.
Separate acquisitions at the same native second remain parallel evidence lanes.
Any conflicting/mixed states remain UNKNOWN. Every frame and event bracket stays
available below the one-second display index.

## Temporal rules and uncertainty

- A measured BUY-to-active-clock change creates a Round-start candidate.
- An observed Score increment can remain pending across unread intermediate
  fields. It needs later measured Result support before the shared Round state
  follows that boundary. The before witness remains the last actual Score read.
- A measured Result may project an ENDED hypothesis without establishing an
  internal Round-end timestamp. A prior ACTIVE state is not manufactured.
- An already observed active countdown can continue below the ambiguous buy-clock
  range only with compatible measured countdown and Score context.
- Current owner-HUD support is an unqualified ALIVE/SELF proposal. A bounded
  missing observation can preserve that hypothesis, with continuation uncertainty.
- Spectator UI directly supports the camera presentation. Recorder death remains
  a competing hypothesis unless direct death evidence exists. A spectated alias
  never proves recorder identity, even when its string matches the recorder.
- Observed DEAD/DOWNED latches need positive revival or observed next-Round/self
  reentry support before returning to ALIVE. DOWNED does not become DEAD because
  time passed. Remote camera and ability return remain distinct inputs.
  The BUY token must differ from the one at death/downing; a new self observation
  in that next BUY can support reentry immediately. Contradictory revival/owner
  observations cannot clear the latch, and unresolved returns retain DOWNED.
  Missing BUY UI cannot mint a new token: measured ACTIVE/ENDED/INTERMISSION
  progress is required before replacing an existing BUY token.
- Report presence alone is not death. Report plus measured shared-HUD
  non-detection can withhold stale ALIVE/SELF; positive current spectator/remote
  observations are preserved. Unconfigured detectors remain UNKNOWN.
- Conflicting current observations preserve alternatives and abstain. Later
  same-state support can reconcile a bounded missing hypothesis without
  smoothing across conflicts, source resets or observed edges.
  Later Result support can add ENDED to a conflicting current Round hypothesis;
  it cannot erase a current BUY/INTERMISSION observation.

The two-second carry and three-second future window are development association
policies. They are not qualified event tolerances, reader thresholds or proof
that the gameplay was continuous. No clock rule creates an unobserved event.

## Continuity

Source, acquisition/epoch, native timebase, dimensions, ordered PTS, decoder
failure, explicit discontinuity and producer/Profile changes constrain reuse.
A missing modality packet alone does not reset another modality's state. A
changed configuration in a returning modality does reset the shared hypotheses.

Compatible PTS only permit bounded conditional inference. Semantic continuity
stays UNKNOWN. Duplicate pixels are recorded and never themselves labelled a
cut. Confirmed content discontinuity/failed decode resets hypotheses and tracking
scope. Map coordinates are never filled for a missing current observation.

## Supplier APIs and duplication ownership

`temporal.adapters.hud_packet()` consumes HUD's
`development_hud_observations_v1`; `map_packet()` consumes Map's
`map_consumer_provisional_v1`. Archived PR111 UI and Round-reader inputs also
have explicit adapters. Original packets and geometry are retained as evidence.
The existing .90 text acceptance floor is reused, including m:ss syntax; decimal
Timer text is not rewritten as an active clock. Component Geometry remains a
separate gate. No reader/Profile/threshold is changed.

`map_context(frame_state, producer_fingerprint=..., revision=...)` produces an
exact-sample Map consumer context. It does not invent semantic continuity:
`source_continuity` stays UNKNOWN in this implementation. Map therefore abstains
when its stronger continuity/identity gate lacks evidence. Its raw unassigned
measurements remain available. Historical positions never become current points.

| Preserved component | Integration path |
| --- | --- |
| PR107 `DevelopmentSelfTimeline` | Rule reference; no second authoritative instance |
| PR111 `DevelopmentOwnerTimeline` | Frozen comparison baseline; shared engine owns life/camera/round state |
| PR112 owner-state tracking | Frozen baseline; current Map handoff consumes external context |
| HUD observation exporter | Current-frame evidence supplier only |
| Map handoff consumer / appearance memory | Map associations only; no life/camera/Round inference |
| Existing Production HUD/Map lifecycle | Unchanged qualified path; not wired to this experiment |

The new CLI bypasses the duplicate research state machines; it does not delete
those baselines or claim all legacy consumers have migrated. Review is required
before resuming separate HUD/Map recognition improvements.

## Reproduction and private admission

```sh
PYTHONPATH=.:src python -m valorant_ai_coach.temporal.replay \
  --policy /PRIVATE/policy.json \
  --hud /PRIVATE/hud-observations.json \
  --map /PRIVATE/map-native-replay.json \
  --map-plan /PRIVATE/map-cli-plan.json \
  --map-plan-output /PRIVATE/new-run/map-common-plan.json \
  --learning-split /PRIVATE/physical-match-split.json \
  --output /PRIVATE/new-run/timeline.json
```

Policy pins the existing manifest/allocation hashes, exact allowed source SHAs
and explicit protected exclusions. Every input must be an accepted DEVELOPMENT
source; HUD lineage must match the physical match and frozen admission receipt.
The CLI opens no video. It replays frozen native observations, not a new decoder
or full recognition E2E. Original acquisition/pixel receipts must be preserved.
Private outputs are exclusive, mode0600, and rejected inside Git checkouts.

The emitted Map plan supplies a shared snapshot for every exact native Map
sample. Run it with the pinned supplier's existing
`scripts.diagnostics.development_map_handoff` CLI to execute its actual consumer.
No control-state or human marker ID is injected as an automatic prediction.

Learning split JSON specifies `train_physical_matches` and
`compare_physical_matches`. They must be nonempty/disjoint. The optional study
compares next-observation ridge prediction, weak rule-label centroid prediction
and lightweight temporal reranking. Next-feature MSE and teacher agreement are
proxy metrics, not recognition accuracy. Without independently reviewed
superiority every learner remains unadopted; no default model changes.

Tests use synthetic evidence, protected-source rejection, exact native bindings,
profile/source/reset boundaries, pending revisions, modal dropout, event/life
exceptions, pixel duplicates, interval retention, physical split isolation and
exclusive private I/O. Real-video limitations and numerical results are recorded
in the comparison report rather than inferred from test counts.

## Additional bounded full-Round acquisition

The fixed archived windows mostly begin near a Round end. To exercise
start→end→next-start in one acquisition, `temporal.acquire` verifies all native
PTS in an explicitly bounded accepted DEVELOPMENT window (at most180seconds),
then retains about one native image per second. It reuses the existing native
PNG budget transport and PTS decoder checker, without modifying the Production
decoder. All decoded PTS must match the probe before any retained image is
published. Source bytes are hashed before and after; semantic continuity remains
UNKNOWN. PNGs retain original dimensions and pixel hashes.

```sh
PYTHONPATH=.:src python -m valorant_ai_coach.temporal.acquire \
  --policy /PRIVATE/policy.json --source-id DEVELOPMENT_SOURCE_ID \
  --start 0 --end 126 --output /PRIVATE/new-native-run
```

The two `scripts/diagnostics/read_shared_native_{round,owner}.py` adapters reuse
pinned supplier checkouts. Invoke them by absolute script path with `PYTHONPATH`
selecting that supplier and its `src` directory. `--help` lists explicit private
Profile/reference inputs. They reject a changed supplier HEAD or a mixed ambient
implementation. They export observations and never instantiate a supplier's
owner/Round state machine. All effective reader files and private inputs are
fingerprinted in their outputs.

For a new acquisition of the same accepted Source, the owner adapter derives an
acquisition-allowlist extension only when the original source-wide human roster
binding names that exact Source SHA and physical match. Original Profile files,
thresholds and reference pixels remain unchanged. This is development transport
of the existing source review, not a new human answer or ownership qualification.
An unobservable spectator slot remains unobservable; the common model does not
bypass that missing identity evidence.

Add the new observation archive with `--hud-supplement /PRIVATE/new-observations.json`.
Raw per-acquisition transition candidates remain available. Overlapping Round
brackets are also grouped as possibly repeated evidence on the same Source
clock; such groups are not verified physical-event identities or additional
independent test events. The exact reproduction commands and private artifacts
are retained in the local comparison deliverables.

## Fixed-input comparison CLI

```sh
PYTHONPATH=.:src python -m valorant_ai_coach.temporal.compare \
  --common /PRIVATE/timeline.json --hud /PRIVATE/hud-only.json \
  --map-only /PRIVATE/map-only.json --consumer /PRIVATE/map-common-consumer.json \
  --supplier /PRIVATE/map-supplier-observations.json \
  --legacy /PRIVATE/frozen-legacy-map140.json \
  --role-review /PRIVATE/existing-role-review.json \
  --output /PRIVATE/new-comparison.json
```

The comparison checks ordered native Map samples, raw observation/pool parity,
shared HUD state values and overlap with legacy display-candidate brackets. It
reports reviewed selection losses when all current Map outputs abstain. If
current outputs are nonempty, the old review summary lacks sufficient exact IDs
for a role join and that metric remains unmeasured. Neither ordering of review
labels nor UNKNOWN is used as invented correspondence or negative GT.
`MapState` is an exported common contract with explicit Zone candidates,
association candidates, current observation presence and UNKNOWN; an observed
empty Map measurement is distinct from receiving no Map observation.

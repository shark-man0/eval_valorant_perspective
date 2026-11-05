# Development application timeline

This is the minimum usable application layer over the existing shared timeline.
It does not add a state machine, change recognition thresholds, or adopt research
results into Production. Recognition quality, independent generalization and
detailed coaching rules are follow-up work, not prerequisites for viewing data.

## Generate, export and view

From an installed development checkout, with the repository root on PYTHONPATH:

```sh
python -m valorant_ai_coach.temporal.application generate \
  --policy /private/source-policy.json --source-id registered-development-match \
  --reader-config /private/image-reader-config.json --output /private/generated-match

python -m valorant_ai_coach.temporal.viewer \
  --bundle /private/generated-match/application/timeline_PRIVATE.json \
  --policy /private/source-policy.json
```

The generation command calls the existing whole-recording acquisition API, then
exports the application bundle, CSV and downstream review. An optional
`--observer module:Class` reuses an image-only supplier implementing the existing
`PixelObserver` interface. It receives pixels, not Source identity, time, roster,
labels or initial state. `--report-view-bridge` retains the existing opt-in
behavior. No manual Round times or match-specific initialization are required.

`--reuse-acquisition /private/completed-native-run` avoids re-decoding a completed
recording. The receipt must match the requested Source, be whole-file complete,
and bind the timeline digest. The source policy and original recording checksum
are verified again. This is reuse of measured evidence, not a fresh acquisition.

Saved results can also be connected independently:

```sh
python -m valorant_ai_coach.temporal.application export \
  --timeline /private/completed-native-run/timeline_PRIVATE.json \
  --receipt /private/completed-native-run/completion_PRIVATE.json \
  --policy /private/source-policy.json --output /private/application-bundle \
  --supplement /private/existing-map-and-zone-timeline.json
```

Supplemental shared observations are filtered to the same admitted recording and
validated by the existing engine. That engine alone rebuilds combined state;
the application layer does not infer ownership or propagate Map paths. Preserve
the original acquisition, supplemental provenance and this changed-input result
as different conditions. Optional supplements may contain sparse, previously
selected development windows; they do not establish whole-recording Map coverage.

The viewer prints a tokenized localhost URL and serves only on127.0.0.1. Open
that URL in a browser. It shows the whole recording's three state lanes, UNKNOWN
regions, Round-candidate filtering, event-candidate navigation, time selection,
HUD/Map candidates and expandable evidence. Selecting a time seeks the original
unedited recording through byte-range streaming. Media is neither cut nor
copied into a new recording. Stop the viewer with Ctrl+C when finished.

This separate development viewer avoids coupling unqualified candidates to the
existing desktop GUI's formal analysis/settings path. It is a functional
fallback, not a replacement for the desktop GUI.

## Contract and provenance

`build_application_timeline` projects one existing engine result. Recording
seconds are relative to the native acquisition origin, including a partial last
second and empty observed gaps. All original native samples, raw observations,
producer/Profile references, estimates and revision history remain in the JSON.
Mixed states within one second yield UNKNOWN with the original alternatives and
native estimates retained. A row's existence never proves successful observation.

Each row contains:

| Field | Meaning |
| --- | --- |
| timestamp / end_timestamp | Recording-relative interval |
| native_start_seconds | Exact rational native origin plus the interval start |
| observation_present / coverage | Actual sampled points versus no observation |
| round_state / round_number | Existing estimates, candidate numbers and conflicts |
| life_state / camera_state | Existing estimates, alternatives and uncertainty |
| hud_observations | Per-field candidate arrays; missing fields remain UNKNOWN |
| map_observations | All marker/position/Zone candidates and current-view associations |
| event_candidates | References to unqualified transitions or supplier candidates |
| evidence_refs / sample_refs | Original observation/sample references |
| confidence / uncertainty | No invented calibrated confidence; explicit limitations |

HUD inputs support existing raw `values`, `view_hp`, direct fields and observation
packet `measurements`. HP, Armor, Weapon, Ammo, Timer, Score and Credits have
explicit slots; additional raw fields remain available. A displayed HUD value is
not automatically the recorder's own value while spectating. Candidates retain
their observed subject limitation and original confidence, not calibrated truth.

Existing engine transitions supply Round, death, spectator and return candidates.
Suppliers can additionally place `event_candidates: [{kind: ...}]` in their
validated observation's raw payload. Those candidates use observation time,
explicitly not verified event time, and preserve their original payload and
observation reference. This supports available Spike/other event providers without
introducing another state machine. An unsupported event reader emits no candidate;
absence of a candidate is not proof that an event did not occur.

Generic Map name and continuous movement inference are not implemented here.
Unassigned marker candidates are retained even when current recorder association
is unresolved. Image coordinates are not presented as resolved Map coordinates.
No path is invented between points; missing Map output never stops generation.

Files are private and must be outside Git:

- `timeline_PRIVATE.json`: all one-second rows plus indexed original evidence.
- `timeline_1s_PRIVATE.csv`: exactly one row per recording second; nested fields
  are JSON cells, including candidates, uncertainty and references.
- `evaluation_PRIVATE.json`: downstream candidate review queue and coverage.
- `completion_PRIVATE.json`: input/output/code hashes and supplemental counts.

## Evaluation handoff

`rules.development_timeline.evaluation_package(bundle, start, end)` provides a
recording window to existing evaluation consumers. Research rows and candidate
events have explicit `development_*` channels. `deterministic_facts`, formal
`events`, qualified state snapshots and qualified frames remain empty.

`review_timeline` actually consumes every row to build a candidate-review queue,
per-field coverage and UNKNOWN summaries. It passes the package through the
existing `TemporalScopeResolver`/`scope_round_package` and deterministic rule
engine. Without qualified facts that engine returns no coaching label. This
confirms data handoff without pretending candidate recognition qualifies a score.

## Measured integration and limits

Two distinct previously acquired full DEVELOPMENT recordings pass the same
generation command with verified acquisition reuse:2443 and2523 one-second rows.
Observed HP candidates occur in1477/1723 seconds, Timer in1677/1482 and Score
in1822/1474. These are coverage counts, not correct counts. The immutable shared
state selections and existing native evidence are preserved by projection.

A third full recording connects existing Map/Zone and newer view observations
through the same export API/engine. Sparse Map/Zone candidates occupy16 display
seconds; no unobserved interval is filled or interpreted as movement. Original
historical self-role qualification/abstention limitations remain separate.

Armor/Weapon/Ammo/Credits, generic Map name, movement and additional Spike events
may remain unavailable for these particular suppliers. Their interfaces and
UNKNOWN handling are connected; new recognition is not claimed. Existing
recognition errors and special lifecycle/independent-evaluation gaps are retained
as quality follow-up work. No new accuracy percentages are derived from output
volume, review-queue size or test counts.

Native synthetic integration covers nonzero PTS origin, whole acquisition,
application export, CSV, evaluation handoff and byte-exact original-video range
delivery. Projection tests cover within-second conflict, missing seconds,
candidate preservation, malformed evidence and unavailable fields. Browser
verification additionally checks real output selection and original-media seek.
Linux/Windows CI results are recorded separately at the submitted exact head.

The initial CI run passes repository tests and Ruff but its source mypy pass
follows runtime-helper imports into unrelated legacy diagnostic CLIs. Two typed
`.pyi` boundaries expose the existing result-text/structure helper signatures;
their Python implementations, recognition bindings and thresholds stay byte
identical. `mypy.stubtest` checks both interfaces against runtime exports, and
clean source plus explicit diagnostic type checks pass locally. This is not a
blanket error ignore or a change to qualification gates. Fresh exact-head CI is
required after this typing repair; the earlier failed run remains recorded.

HUD, Map, evaluation, GUI and learning work may continue against this interface;
they need not wait for perfect recognition. Shared state remains owned solely by
`DevelopmentGameTimeline`. Main merge and Production adoption remain supervisor
decisions; private videos, labels, images, Profiles and weights stay local.

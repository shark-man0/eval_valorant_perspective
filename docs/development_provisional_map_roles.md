# Current Map role hypotheses from shared view evidence

The shared timeline can expose a separate research hypothesis that a measured
Map highlight belongs to the recorder. This does not replace the existing
`current_self_position_candidates` gate, qualify ownership, create a path, or
change Round/life/camera inference. It is disabled by default.

The failure being addressed is loss of a usable correspondence candidate: the
archived Map UI retained its highlighted marker, while the current weak SELF
view could not meet the stronger Map owner-evidence gate. Retaining only the
unassigned pool hid this plausible association from application consumers.

## Contract and evidence

Set `DevelopmentGameTimeline(provisional_map_roles=True)`. The shared engine
computes `MapState.provisional_recorder_position_hypotheses` after its existing
inference; HUD/Map suppliers do not implement another state machine.

Each proposal retains the original candidate and Map sample, Map observation ID,
current view evidence IDs, rule contract, uncertainty and competing roles:
`RECORDER_SELF`, `VIEWED_PLAYER`, `OTHER`, `UNKNOWN`. Confidence remains unset,
ownership UNKNOWN, qualified false, position authority false and temporal path
eligibility false. Strong current-self candidates remain a distinct field.

A proposal requires all of the following:

- The shared life/camera estimates are ALIVE/SELF from current observations.
  Carried states, a future anchor or report reconciliation alone cannot supply it.
- A current weak SELF pixel observation contributes to both estimates, has
  supported HUD structure and accepted positive HP, and has no owner exclusions
  or owned-death text. Existing HP acceptance is reused without tuning.
- No current spectator, remote, death, downed, revival, return, elimination,
  missing-HUD, terminal Round signal or failed decode conflicts with the view.
- Source, native PTS/timebase, decoded pixels and frame dimensions agree. Another
  epoch can contribute only through the existing exact-pixel fusion, never a
  nearby timestamp or another epoch's inferred state.
- An unchanged sealed Map packet and its sample/pool-bound UI identify a unique
  measured highlight. Ties, duplicated/out-of-range indices and missing or
  inconsistent UI bindings abstain. No historical initial index, reference
  agent, Source-specific condition or human target is read for selection.

The existing candidate generator may itself have historical Profile/reference
bindings. Reusing its pool does not establish a generic Map recognizer. Multiple
supplier proposals remain alternatives; none becomes a formal owner position.
The contract includes the Map rule source hash in engine configuration and in
the existing state reconstruction fingerprint.

## API, CLI and consumers

```python
engine = DevelopmentGameTimeline(
    fuse_exact_native_evidence=True,
    provisional_map_roles=True,
)
for original_observation in observations:
    engine.add(original_observation)
timeline = engine.rebuild()
```

Both existing native and application generation CLIs accept
`--provisional-map-roles`. For a whole-recording image observer that also supplies
Map packets, use:

```sh
PYTHONPATH=.:src python -m valorant_ai_coach.temporal.application generate \
  --policy /PRIVATE/development-policy.json --source-id REGISTERED_SOURCE \
  --reader-config /PRIVATE/reader.json --observer MODULE:ExistingObserver \
  --provisional-map-roles --output /PRIVATE/NEW-generated-match
```

The flag does not add a new pixel Map reader. Without compatible Map observations
it emits no role proposal and generation continues. A reused acquisition must
already have the requested mode, so old inference is never silently relabelled.
The existing supplement/export route can enable this mode while rebuilding
through the one shared engine, without modifying the acquisition receipt:

```sh
PYTHONPATH=.:src python -m valorant_ai_coach.temporal.application export \
  --timeline /PRIVATE/completed-acquisition/timeline_PRIVATE.json \
  --receipt /PRIVATE/completed-acquisition/completion_PRIVATE.json \
  --policy /PRIVATE/development-policy.json \
  --supplement /PRIVATE/existing-shared-Map-observations.json \
  --provisional-map-roles --output /PRIVATE/NEW-research-projection
```

Keep supplemented/reconstructed results and native acquisition receipts as
distinct conditions. The export receipt records the requested option and final
engine configuration; it does not claim a new decode or retroactively change
the native acquisition's recognizer/configuration.

`project_current_map` validates and exposes the proposals on original Map rows,
separately from strict current positions. The application places deduplicated
proposals in each second's `map_observations`, preserves them as JSON cells in
CSV, and passes them through the existing development evaluation package. The
viewer labels them as research hypotheses with recorder identity unresolved;
expand the existing state/evidence panel to inspect original candidates and IDs.
No new coaching score, deterministic Fact or Event is generated.

## Validation scope

The comparison freezes the existing eight exposed physical matches and the full
140-packet archived Map pool before replay. Human role answers are read only
after predictions are sealed. Known exact-frame role matches are reported
separately from the still-abstaining strict current-self channel. Unlabelled
proposals are not counted as correct, rejected proposals are not proof of
absence, and repeated epochs do not become independent matches.

On the four existing exact recorder-marker controls, the separate provisional
channel changes from no proposals to four matching proposals. The existing
non-recorder control receives no proposal. All five labelled controls are from
one exposed physical match; this is not multi-match role accuracy. Strict
current-self correspondence still abstains on all four recorder controls.

Replay across 15 fixed conditions covering eight exposed physical matches
preserves the frozen parent output when disabled. With the option enabled,
removing only the new configuration/Map fields restores exact parent equality:
Round/life/camera, evidence, raw pools, transitions, tokens and existing output
fields are unchanged. The augmented Map cohort retains all 140 original packets;
16 original Map samples receive hypotheses. Other proposals are unlabelled and
remain unscored. Parallel acquisition aliases are not independent successes.

The original-video application export covers 1,610 seconds and retains the four
exact reviewed associations with no proposal at the non-recorder control. Its
JSON/CSV equivalence, actual evaluation handoff and viewer display/seek were
checked. It reuses a whole acquisition plus saved supplier observations, rather
than claiming a fresh full-match decode or generic Map recognition.

Protected recordings, GT, evaluation windows, exposure splits and Production
safety gates are unchanged. Independent unseen validation, coordinates, Zone
accuracy and movement recognition remain open. This is a research candidate
connection, not completion of strict recorder identity recognition.

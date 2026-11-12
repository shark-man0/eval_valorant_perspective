# UNKNOWN diagnosis, measured ACTIVE clock chains and configured HUD values

This development change reuses the one shared state engine and the existing
configured HUD readers. It adds no alternate Round/life/camera state machine,
new weights, roster requirement, Source-specific recognition branch or formal
Fact/Event. Production defaults and qualification gates remain unchanged.

## Diagnose before changing inference

Eight exposed whole DEVELOPMENT matches were fixed before implementation.
The shared application's UNKNOWN seconds were separated into all native points
unknown, a known state mixed with unknown points, and conflicting known states.
Round had 5,979 / 120 / 37 seconds in these groups; life 4,199 / 69 / 10 and camera
3,407 / 73 / 15. These are diagnostic counts, not labelled errors.

Most uncertainty is in the original readings, rather than second aggregation.
A common Round failure has an observed ACTIVE clock, unread clock/score points,
and then accepted low clocks. The old rule needs the preceding frame to remain
ACTIVE, so a sufficiently long unread span prevents reacquisition even when
actual later countdowns and scores agree. Life/camera uncertainty also contains
unconfirmed death/return, missing HP, blocked reports, menus and classifier
abstentions. Those are retained rather than resolved from game rules alone.

## Opt-in measured clock chain

`DevelopmentGameTimeline(active_clock_bridge=True)` runs an offline Round-only
projection after existing inference. `--active-clock-bridge` is exposed by the
native CLI and application generation/export. Default is false; forward-only
mode rejects the option. Export can reconstruct existing observations with the
option while retaining the original acquisition receipt as a separate artifact.

The projection needs an original directly observed ACTIVE phase and accepted
numeric clock/score, a current accepted decreasing clock with the same score,
and a later compatible decreasing clock within the existing future horizon.
The elapsed native time and clock decrement must agree within the existing
one-second display quantization allowance. Each intervening native continuity
link must remain compatible. Source/epoch/Profile/decode breaks, contrary
BUY/result/intermission, changed/conflicting score, clock increases, ambiguous
readings, missing confirmation or a stationary clock do not establish a bridge.
A reading gap cannot outlive the last measured countdown plus quantization slack.

Only a current UNKNOWN/unobserved Round estimate can become an uncertain ACTIVE
candidate. Unread frames within the gap stay unchanged. ACTIVE/BUY/UNKNOWN
alternatives, source evidence, the original estimate, clock anchor, previous
clock and future confirmation are retained. Pause, phase and semantic continuity
remain unverified. No internal event time, lifecycle/Map authority, new transition
or Rule token is issued. Existing life/camera/Map and event candidates are equal
on all fixed inputs. Round-number summaries retain their existing uncertainty.

Across 15 frozen conditions covering eight exposed physical matches, disabled
output exactly equals frozen Draft #127. The eight whole views change Round
UNKNOWN from 6,136 to 6,015 seconds (121 current-frame candidate revisions, seven
matches changed and one unchanged). Life remains 4,278 UNKNOWN seconds and camera
3,495. These unlabelled revisions measure candidate coverage, not recognition
accuracy; repeated prefixes/epochs are not independent matches.

## Existing configured HUD readers

`ProfileHudObserver` accepts an optional `optional_hud_values: true` reader-config
field. The same existing readers may then contribute viewed-HUD candidates for
HP, Armor, Weapon, current/reserve ammo and credits when configured. No reader,
asset, Profile threshold or source initialization is invented. Numeric fields
reuse `accept_hud_value`; failures and unavailable configuration stay UNKNOWN.

The original Profile used by the eight-match study configures HP only among
these fields. Armor/Weapon remain unavailable until real readers/assets are
configured. Twenty-four preselected native frames (first, median retained point
and last per whole match) were processed identically: all original pixels and
base measurements/signals/context match, six HP candidates were obtained, and
other fields retain configuration/geometry reasons. No value accuracy labels
were created, and six candidate readings are not six verified correct readings.
The adapter also normalizes existing grouped numeric/weapon reader results into
canonical fields, instead of losing them under ROI names.

`ProfileHudObserver.inspect_values(image)` provides a value-only supplier;
attach its measurement through `frame_observations` with `value_fingerprint`.
The observation has empty state signals and retains Profile/reader/code binding.
The original HP/Armor/Weapon belongs to the viewed HUD, which may be a spectator
or remote view. Positive HP and zero HP never establish recorder life.

## Exact-native application join

```python
bundle = build_application_timeline(
    shared_timeline, source=registered_source,
    duration=native_duration, origin=native_origin,
    hud_value_observations=existing_value_only_observations,
)
```

Value-only observations join only matching Source/native PTS/timebase/pixels and
frame dimensions. Their original acquisition epochs and samples remain intact
in `observations` and `HUD_value_observation_links`. Unmatched or failed evidence
is retained without supplying a value to a nearby second. The join does not add
state frames: another epoch's UNKNOWN must not erase an existing lifecycle
estimate merely to display HP. State, events, Map and temporal continuity are
unchanged. CSV rows have a consistent optional `HUD_value_sample_refs` column.

```sh
PYTHONPATH=.:src python -m valorant_ai_coach.temporal.application export \
  --timeline /PRIVATE/completed-acquisition/timeline_PRIVATE.json \
  --receipt /PRIVATE/completed-acquisition/completion_PRIVATE.json \
  --policy /PRIVATE/development-policy.json \
  --active-clock-bridge --hud-values /PRIVATE/native-HUD-values.json \
  --output /PRIVATE/NEW-research-view
```

Both application generation and export accept repeatable `--hud-values` paths.
Policy admission, source integrity, original acquisition and supplemental
fingerprints remain separate. The native reconstruction fingerprint binds the
clock configuration; the value observer binds its own code and Profile. Old
recognizer qualification is not inherited after a fingerprint change.

The viewer labels these as viewed-HUD candidates with recorder identity
unresolved, and shows unavailable-reader, unsupported-geometry, unread and reader
error reasons. JSON/CSV and the existing development evaluation package retain
all values/evidence without generating deterministic facts or coaching scores.

## Remaining limits

The eight matches are already development-exposed. Unseen generalization is
unproved. Most remaining UNKNOWN states need better observations; this change
does not fill missing seconds or label intervals from a few frames. Internal
Round timing, strict owner restoration, exceptional DOWNED/REMOTE/revival,
Armor/Weapon model configuration, positions/Zones/paths and population false
event rates remain follow-up work. Rejected learned rerankers remain unadopted.

# Actual common API connection and resolved upstream failure

**Latest:** the authorized report reached the common owner, who confirmed that
the current engine separates the candidate lists. A new fixed-source snapshot
completes the same 140-sample round-trip, and the public Map CLI reproduces it
with 140/140 exact context joins. Actual common-state positions remain UNKNOWN;
this is connection success, not recognition improvement. The earlier failure
below is retained as historical evidence.

The integration owner's local API is now available for inspection. This updates
the earlier handoff's "producer unavailable" finding. The Map branch does not
copy or modify the common engine. A read-only source snapshot was taken with
matching before/copy/after file hashes, then used for an actual connection trial.
The integration package is still under development, so this is a source-snapshot
compatibility finding, not a qualification or a released dependency.

## Connection that was exercised

1. Current Map `make_map_observation` packets are passed to common
   `temporal.adapters.map_packet` and `DevelopmentGameTimeline.add`.
2. The unchanged HUD supplier observations are passed through common
   `hud_packet`, with its existing SourcePolicy admission checks.
3. The intended return path is `DevelopmentGameTimeline.rebuild` followed by
   common `temporal.game.map_context` into `DevelopmentMapStateConsumer`.

The fixed trial uses the same 140 admitted DEVELOPMENT Map samples as A/B/D.
Eighty HUD packets match these exact native samples and acquisition scopes.
The remaining 10,867 archived HUD packets belong to other acquisition scopes
and are not joined by approximate PTS. No video was decoded and no new human
review was requested. The common files remain untouched.

## Reproduced blocker

This section describes the initial source snapshot, not the later fixed one.

`temporal/game.py`, in `DevelopmentGameTimeline.rebuild`, uses `candidates` for
both accumulated boundary candidates and the current frame's raw Map candidates.
After the frame loop, `boundary_candidates` and revision-history
`candidate_statuses` refer to the last Map list. A raw Map candidate has no
boundary `candidate_id`/`status`, so the real trial fails with
`KeyError: 'candidate_id'` before returning the state series. If the last frame
has no Map candidates, this aliasing also prevents that list from representing
the accumulated boundary candidates.

This is also reproducible with one synthetic observation, independently of
private recordings, HUD recognition, images or threshold choices:

```python
from valorant_ai_coach.temporal.game import DevelopmentGameTimeline, observation

sample = {
    "source_id": "synthetic", "source_sha256": "a" * 64,
    "acquisition_id": "synthetic_epoch", "native_epoch": "synthetic_epoch",
    "native_pts_tick": 60, "native_time_base": "1/60",
    "frame_size_px": [128, 96],
    "acquired_frame_sha256": "b" * 64, "native_pixel_sha256": "c" * 64,
}
engine = DevelopmentGameTimeline()
engine.add(observation(
    sample=sample, producer="d" * 64, signals=[], raw={},
    map_candidates=[{
        "center_frame_px": [32, 32],
        "geometry_only_map_position_norm": [.2, .3],
        "qualification": "development_only", "ownership": "UNKNOWN",
    }],
))
engine.rebuild()  # KeyError: 'candidate_id' in the inspected source snapshot
```

The common owner should separate the boundary and per-frame Map collections and
add a nonempty-Map replay regression. Adding fake boundary IDs to Map candidates
would conceal this defect and is not an acceptable Map-side compatibility fix.
No such workaround was adopted.

## Evidence and remaining checks

The actual common-state C result is **unmeasured**, not zero correct positions:
the API did not return. Earlier C=0 figures describe the missing-context Map
consumer, and D=82 describes controlled context injection. Neither is a
successful actual common-engine run. Existing B and all fixed Map regressions
remain preserved, and the current Map-only tests pass 61/61.

The inspected `map_context` already matches the provisional Map schema. It
explicitly exports `source_continuity=UNKNOWN`; that must not be promoted to
continuous merely because a native receipt or normal PTS interval exists. After
the upstream failure is fixed, repeat the same input trial, preserve this
uncertainty, compare the returned states and reviewed selections, and report
any remaining positive-recorder-evidence or continuity-permission gaps. Actual
Round/death/spectator/reentry recognition remains the common owner's task.

## Fixed-source actual result

The common source-snapshot fingerprint is
`acb315a9e709d028e5955911f410c1ffb8f5ba7d1e649a4de65dedbeb1da85c5`.
No upstream file was modified or imported into this Draft's Git tree. The same
Map140 and exact-native HUD80 input now returns 140 frame states. Of these,
47 camera states are SPECTATOR and 93 UNKNOWN; all 140 recorder-life, Round,
recorder-correspondence and semantic-continuity values are UNKNOWN. In
particular, spectator camera evidence does not become recorder-death evidence.

The returned actual `map_context` snapshots pass unchanged through the Map
consumer. The public `--common-contexts` CLI joins all 140 by exact native
sample ID, records the sidecar hash, and reproduces the direct round-trip
records exactly. All raw geometry envelopes/candidates remain available;
current self positions, named Zones, self path segments and formal outputs are
zero. There are 28 bins covering acquired Map seconds, not continuous exposure.

Actual A/B/C Map counts are 30/81/0. C abstains at all four previously reviewed
self markers and does not select the reviewed Spike; unreviewed roles remain
UNKNOWN. This is not a false-attribution-rate improvement. Positive recorder
evidence, Round scope/reconfirmation, and semantic continuation permission are
still needed before common-state-assisted self paths can be evaluated. No
threshold, GT or UNKNOWN value was changed to obtain more positions.

The actual API trial took 9.89 seconds with peak process RSS 485.73 MiB, including
archived observation loading, the common engine, image-bound Map features and
the Map consumer. It used no new video decode or human review. This cost is
not comparable to either the earlier calibration-plus-viewer run or the
consumer-only replay. Current Map tests pass 66/66; Ruff and mypy pass.

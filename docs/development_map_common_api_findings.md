# Actual common API connection: upstream failure

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

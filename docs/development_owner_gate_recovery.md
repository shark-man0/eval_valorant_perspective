# Development owner-observation gate recovery

This opt-in follow-up depends on the shared timeline Draft #115. It changes
current-frame observation assembly only; `DevelopmentGameTimeline` remains the
sole Round/life/camera owner. Existing readers, templates, thresholds, default
recognizers, GT and fixed evaluation windows are unchanged.

## Problem and behavior

The archived owner supplier required a redundant spectator veto to report
`not_detected` even when that optional detector was intentionally unconfigured.
Consequently a configured dedicated slot's actual `checked=True,
panel_present=False` measurements were discarded. It also omitted positive
`spectator_controls` measurements when assembling the camera flag.

`temporal.owner_evidence.recover_owner_item` retains the entire original UI and
raw measurements, verifies their exact native pixels/profile/Source/epoch, and
assigns a new implementation fingerprint. It accepts a dedicated checked absence
when the redundant detector is intentionally absent. A configured but unavailable
detector still blocks eligibility. Missing/ambiguous dedicated slots and template
non-detection alone never prove absence. Positive spectator controls veto own-HUD
support even if another measurement says the icon is absent.

An existing Source-bound human recorder-roster binding and current matching agent
and first-person HUD support are still required for an unqualified own-HUD
proposal. Missing recorder binding does not prevent a camera observation; it
never creates ownership. Report presence never becomes a death signal. The
module has no temporal carry, Round definition, state machine or qualification
issuer. Reapplying recovery is rejected, and callers cannot mutate its input.

## Fixed DEVELOPMENT replay

The comparison uses the same three previously exposed physical matches, native
samples, original measurements and common engine for baseline and recovery.
No new video decoding or human labels were introduced. The original archived
export and its raw input give identical baseline Round/life/camera values at all
11,402 acquisition-frame states. Recovery retains all 11,609 observations,
11,308 physical native points and 1,170 common second rows.

| Measure | Baseline | Recovery | Meaning |
| --- | --- | --- | --- |
| Direct owner-HUD support in the bounded 127-point cycle | 0 | 6 | Gate recovery, not independently proven ownership accuracy |
| ALIVE frame estimates in that cycle | 0 | 12 | Includes bounded conditional carry |
| Camera UNKNOWN frame estimates in that cycle | 106 | 91 | Current positive controls also reach the camera observation |
| Full timeline UNKNOWN life second bins | 1170 | 1160 | Parallel acquisition disagreement remains UNKNOWN |
| Full timeline UNKNOWN camera second bins | 1152 | 1139 | Includes missing bins; not observed duration |
| Round state-value changes at shared frames | 0 | 0 | Existing Round results retained |
| Map native inputs | 140 | 140 | Exact sample/epoch HUD joins only |
| Map sample life | UNKNOWN140 | UNKNOWN140 | This change does not solve Map ownership |
| Map sample spectator camera proposals | 47 | 50 | Additional observations require independent correctness review |

All changed frame-domain values were previously UNKNOWN: 12 life proposals,
12 SELF camera proposals and 6 SPECTATOR camera proposals. Existing known state
values were not lost. The original Map selection coverage regression (81 to 0,
including four previously reviewed self-role selections) is not repaired by this
change. Independent Round truth/false counts, internal timing error and general
ownership/position/Zone accuracy remain unmeasured. Complete recorder
death→spectator→return recovery remains **UNMET**. Formal Facts/Events stay empty;
neither proposal counts nor tests are recognition accuracy improvements.

## Reproduction

```sh
PYTHONPATH=.:src python -m valorant_ai_coach.temporal.owner_evidence \
  --policy /PRIVATE/policy.json --input /PRIVATE/frozen-owner-round-input.json \
  --output /PRIVATE/new-run/recovered-owner-round-input.json

PYTHONPATH=.:src python -m valorant_ai_coach.temporal.replay \
  --policy /PRIVATE/policy.json --hud /PRIVATE/new-run/recovered-owner-round-input.json \
  --hud-supplement /PRIVATE/new-run/recovered-cycle-input.json \
  --map /PRIVATE/frozen-map-observations.json \
  --map-plan /PRIVATE/frozen-map-plan.json \
  --map-plan-output /PRIVATE/new-run/common-map-plan.json \
  --output /PRIVATE/new-run/timeline.json
```

Recover the supplemental cycle through the same first command. Both input forms
are `hud_supplier_replay_input_v1`, with their original frame contracts, Profiles
and reader receipts retained. The policy must admit accepted DEVELOPMENT only.
Outputs are exclusive private artifacts outside Git; no private references are
committed. Run the actual Map consumer from the same pinned supplier used in the
baseline. A consumer receiving UNKNOWN must not invent semantic continuity.

Regression tests cover configured detector failure, unconfigured optional
detectors, absent versus unread slots, conflicting positive spectator controls,
unbound recorder identity, Report non-death, exact pixel/Source/epoch/profile/match
binding, immutable input and double application. These remain development tests.

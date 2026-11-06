# BUY clock context experiment on existing DEVELOPMENT recordings

This opt-in extension to the existing shared state engine addresses an observed
failure: an unreadable phase/timer frame inherited BUY after the purchase phase
had ended. It is a development hypothesis, not a new state machine, event
detector, calibrated confidence or Production adoption.

The user chose to continue improvement/regression comparisons on the existing
eight authorized DEVELOPMENT matches and defer unused-recording verification.
These matches are already development-exposed; no result here establishes unseen
generalization. Protected/FINAL/UNKNOWN_EXPOSURE recordings remain excluded.

## Rule and authority

`DevelopmentGameTimeline(buy_clock_expiry=True)` adds an offline projection after
lifecycle/Map inference. It requires two accepted decreasing BUY clock displays
with the same valid score and bounded acquisition continuity. The expected clock
expiry includes one second of display quantization slack. The latest clock's age
is bounded by the existing carry plus future horizons; direct ACTIVE with the
same score must subsequently be observed within the existing future horizon.
Source/epoch/decoder/Profile breaks, contrary BUY/result/intermission, conflicting
phase or score, missing/nondecreasing clocks and weak-only ACTIVE do not supply
confirmation. Direct observed BUY is never replaced.

Only a carried BUY estimate may become an explicitly unqualified ACTIVE
candidate. BUY and UNKNOWN remain alternatives, because native elapsed time does
not prove that the game clock progressed without a pause. The estimate records
its former value, both clock samples, later ACTIVE evidence and uncertainty.
It assigns no exact Round-start time. Life/camera, tokens, Map candidates,
ownership, transitions and boundary candidates are not modified by this pass.
Round-number summaries retain their existing candidate/uncertainty rules.

This option defaults to false and is incompatible with forward-only inference.
No observer thresholds, weights, assets, Profiles, GT, evaluation windows or
Production safety gates change. The engine source hash intentionally changes the
coupled research fingerprint; old qualification evidence is not inherited.

## Same-input DEVELOPMENT results

Before changing the rule, the parent engine from Draft #125 (`aa6b472`) and the
input conditions were retained privately. Twelve saved acquisition conditions
cover eight distinct physical matches: six whole-recording acquisitions, five
uniform prefixes and a separate wide-context cohort. The prefixes/wide contexts
repeat some of those matches and are never counted as additional independent
matches. The two other physical matches initially have prefix evidence only.

All 21,551 retained native points are replayed through the frozen parent, the
current default and the opt-in candidate. Current-default results exactly equal
the frozen parent in all twelve conditions. The candidate preserves all raw
observations, life/camera, Map, tokens, transition and boundary candidates. Nine
Round estimates change from carried BUY to uncertain ACTIVE across these
conditions; most revised points have no Round label and remain unscored.

| Fixed cohort | Before | Opt-in candidate | Previously correct lost |
| --- | --- | --- | ---: |
| Ten exact Round displays in five uniform prefixes | 9 correct / 1 wrong | 10 correct / 0 wrong | 0 |
| Original three whole-match Round controls | 13 / 13 correct | 13 / 13 correct | 0 |
| Original three whole-match life/camera controls, per domain | 12 / 12 correct | 12 / 12 correct | 0 |
| Additional three whole-match Round controls | 6 / 6 correct | 6 / 6 correct | 0 |
| Nine wide-context life/camera controls, per domain | 7 correct / 2 abstained | 7 correct / 2 abstained | 0 |

The five-match selected-point Round micro and mean per-match agreement are both
90% -> 100%; the formerly worst match is 1/2 -> 2/2. These labels describe exact
frames only, not whole seconds, intervals, internal event timing, unlabelled
changes, or full-match recognition accuracy. Repeated-condition labels are not
pooled into a larger independent denominator. No human labels were used as
inference/initialization inputs; no new labels or fitted models were created.

All 36 saved prediction files reproduce byte-for-byte in a separate output tree.
Fresh worker compute times and Python peak memory are retained per condition.
They include input/result serialization scope and exclude child processes;
overlapping local tests mean no isolated speed or memory improvement is claimed.

A new paired 60-second real DEVELOPMENT prefix acquisition reproduces the known
BUY-carry failure and the candidate revision with identical native pixels and
whole pixel measurements between modes. The original 60 coarse measurements
also agree under the declared state-coupled shape-producer correspondence.
All non-Round state fields and event candidates match after explicit acquisition
alias normalization. This is a prefix transport check, not another full match
or an independent success. The earlier verifier's literal comparison of fresh
epoch identities failed and is retained privately; correcting that verifier did
not alter runtime recognition or require re-decoding.

## Generate and inspect

Use the existing automatic API with one image-only observer/configuration:

```python
run_match(
    policy_path=policy,
    source_id=registered_development_source,
    reader_config=shared_config,
    output=new_private_directory,
    observer_factory=ExistingImageOnlyObserver,
    report_view_bridge=True,
    buy_clock_expiry=True,
)
```

The native CLI exposes `--buy-clock-expiry`. The application generation route
also forwards it, retaining whole-file acquisition, JSON/CSV, native provenance,
original-video viewer and actual evaluation handoff:

```sh
PYTHONPATH=.:src python -m valorant_ai_coach.temporal.application generate \
  --policy /PRIVATE/development-policy.json --source-id REGISTERED_SOURCE \
  --reader-config /PRIVATE/shared-reader.json \
  --observer EXISTING_IMAGE_ONLY_MODULE:ExistingObserver \
  --report-view-bridge --buy-clock-expiry --output /PRIVATE/NEW-generated-match
```

No roster, agent/map initialization, known boundary time or audit sample is an
input. Source identity is used only for admission/provenance. A reused acquisition
must already contain the requested clock mode; the CLI rejects a request that
would silently label an older acquisition as using the new inference. Existing
supplement export retains the option when rebuilding shared observations.

The candidate remains a development option. Map's historical four self-role
abstentions, special lifecycle/remote/pause cases, population false events and
independent unseen validation remain open in #124. Existing rejected C/D models
stay unadopted. Development continues without waiting for new recordings.

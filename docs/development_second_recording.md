# Second DEVELOPMENT recording workflow

This opt-in work builds on Draft #136. The shared `DevelopmentGameTimeline`
continues to own Round, life and camera state. Suppliers read pixels only;
none can issue qualified ownership, Facts or Events.

`ExpandedDevelopmentObserver` composes the existing HUD/value/credits pipeline,
current menu-grid geometry and generic minimap observations. Its private config
has `menu_config` and `map_config` paths. The menu config names the existing parent
observer/config and normalized HUD layout. The Map config accepts only `layout`.
No recording identity, timestamp, roster, agent or initial state is an input to
these additional readers. Their sampling hints request bounded extra inspection;
menu geometry alone is not a BUY or recorder-ownership observation.

`current_menu_return_candidate` is disabled by default. With the existing offline
return projection enabled, it can support an ALIVE/SELF research candidate when
current menu pixels hide HP, a current weak SELF hypothesis exists, and a later
same-epoch next-Round owner view brackets the return. Direct spectator, remote,
death, downed and revival evidence blocks it. It retains alternatives, original
observations, forward estimates and unresolved event time. It does not qualify
identity or enable a Map path.

Generic Map proposals use the existing normalized minimap ROI and bundled map
registry/calibrator. Unsupported geometry remains UNKNOWN. Shape extraction can
run when map name or calibration is unavailable. A candidate pool, weak display
structure, map-name alignment and Zone candidates are separate from recorder
correspondence. The bundled production registry currently has only a limited
reference; running it does not establish broad VALORANT map coverage. Unowned
candidates never enter `current_self_position_candidates` merely because the HUD
suggests SELF. Existing exact-native Map pools and role hypotheses remain intact.
`map_shape_ranking` is a diagnostic white-arrow ranking experiment; its top result
is never automatically a recorder position.

## Freeze before opening the second recording

1. Preserve the nine-match baseline, first recording's initial prediction,
   fixed controls, sampling conditions and Source/Exposure allocation.
2. Finish old-development comparisons and record adopted/rejected methods.
3. Commit the runtime, then use `temporal.validation.freeze_protocol`. Freeze
   every sampling/feature flag, including both current HP/menu return options.
4. Save a private assessment with `phase_1_to_4_complete: true`,
   `second_content_accesses: 0`, `protected_content_accesses: 0`,
   `protocol_sha256`, and `evidence_sha256s` mapping all comparison paths to hashes.
5. Activate only the second previously reserved DEVELOPMENT source:

```sh
python -m valorant_ai_coach.temporal.second_validation activate \
  --batch PRIVATE_BATCH --protocol PRIVATE_PROTOCOL \
  --assessment PRIVATE_ASSESSMENT --allocation-sha256 ALLOCATION_SHA
python -m valorant_ai_coach.temporal.second_validation run \
  --stage PRIVATE_BATCH/second_development --phase pilot \
  --pilot-seconds 120 --output PRIVATE_PILOT_OUTPUT
```

Activation never rewrites the original allocation or first-use policy and does
not read recording content. The other DEVELOPMENT recording is excluded from
this new policy, and the two QUALIFICATION/two FINAL_HOLDOUT recordings remain
protected. A first attempt, including failure, is preserved and cannot be retried
under the same first-prediction name. No tuning is permitted between initial
content inspection and the initial full prediction.

Inspect the pilot's acquisition receipt, native observations and application
JSON/CSV/evaluation handoff. Record a same-Source structural check bound to the
preserved pilot receipt, then:

```sh
python -m valorant_ai_coach.temporal.second_validation confirm \
  --stage PRIVATE_BATCH/second_development --check PRIVATE_PILOT_CHECK
python -m valorant_ai_coach.temporal.second_validation run \
  --stage PRIVATE_BATCH/second_development --phase full \
  --output PRIVATE_FULL_OUTPUT
```

Use the existing `temporal.application export`, `temporal.validation.check_output`
and local comparison viewer to check JSON/CSV, full duration, original-video seek
and evaluation consumption. Structural success is separate from recognition
accuracy. Unlabelled recording intervals have no accuracy denominator.

## Learning reproduction

`python -m valorant_ai_coach.temporal.view_ranking_experiment --manifest
PRIVATE_MANIFEST --output PRIVATE_NEW_RESULT` replays a fixed pseudo-label ranking
experiment. The private manifest has `records`, each containing `physical_match`,
`native_timeline`, and `native_sha256`. It uses disjoint physical-match folds,
current/adjacent weak-view margins and a separate repeated-HP diagnostic. Pseudo
agreement is not human accuracy; the model does not change timeline state.
Weights, frame labels, native PTS, media and private configuration stay outside Git.

## Prior-development results

On the same saved native observations from nine exposed matches, menu-assisted
return candidates changed the fixed observed control score from 67 correct,
zero incorrect, two abstentions to 69 correct, zero incorrect, zero abstentions.
Fourteen known attributes were not observed and remain excluded. The gain is two
attributes of one already reviewed frame in one physical match. Three seconds
changed; this does not label the other changed frames or establish unseen-match
accuracy. Round control results were unchanged. Menu structure is an additional
HUD measurement; numeric OCR recognition and strict boundary-time accuracy were
not improved by this change.

A separate generic Map layer retained spatial proposals near all four known
recorder highlights, but white-arrow ranking retrieved none at rank one and two
in the top five. This is approximate historical-footprint retrieval, not exact
coordinate ground truth or qualified recorder correspondence. Ranking was not
adopted. Existing Map pools, provisional roles and strict abstention were retained.
See `development_view_reranker.md` for the non-adopted learning experiment.

All changes remain development opt-ins. Main integration, Production adoption,
qualification and evaluation-contract changes require separate review.

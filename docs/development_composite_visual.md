# Composite visual evidence in the shared development timeline

This extends Draft #137, rather than adding another game-state engine. All
recognition remains opt-in and unqualified. Production Fact/Event gates, GT,
evaluation windows, original predictions and protected recordings are unchanged.

## Image observations and identity

`temporal.composite_view.CompositeViewObserver` wraps an existing native observer.
Its explicit private JSON configuration contains `parent_observer` and
`parent_config`, with optional `agent_catalog` and `visibility_tessdata` paths.
No Source, agent initialization, roster or recording time is a recognition input.

The supplier measures four ordered ability glyphs and the lower-left viewed
portrait. Charge bars, key labels and ultimate counters lie outside the glyph
ROIs. An explicitly versioned reference catalog supplies agent/ability candidates;
asset hashes are bound to the recognizer. Weak or ambiguous template matches stay
UNKNOWN. Portrait candidates describe the viewed actor, not the recorder.

The existing combat-report UI measurement is transported as a dependency of the
old reader, not a second independent vote. Combat report, killfeed and broadcast
chat remain distinct. A persistent report is not a new death. Optional existing
HUD visibility OCR supplies BUY_MENU/Tracker candidates through the native stream.

`DevelopmentGameTimeline` attaches the composite observations to its existing
Life/Camera estimates. A recorder signature anchor needs a current SELF/ALIVE
estimate, explicit current owner-HUD support and readable glyphs; the first video
frame is never assumed SELF. The anchor resets on Source/epoch or confirmed
content discontinuity. Same-agent appearance only establishes compatibility: it
does not change state, prove the viewed actor is the recorder, authorize Map
ownership, or create Facts/Events. Current state estimates, anchor provenance,
viewed-agent candidates, ability similarity, contradictions and UNKNOWN remain
separate. This first implementation is an advisory visual slice, not a qualified
player-identity recognizer.

Application JSON/CSV add `viewed_identity_observations` for runs that supply these
pixels. The existing viewer displays candidates and raw native evidence.

## Bounded additional observation

`--refinement-policy evidence` is an opt-in alternative to the old balanced policy.
It prioritizes newly observed owned-victim report wording whose independent
display attributes are unread, including the associated spectator switch. It
requests only nearby frames, reserves at most half the bounded window budget,
and keeps stratified coverage for other changes. Defaults remain 1-second coarse,
one-fifth-second dense, at most 40 windows and 240 dense seconds. A selected
window is an acquisition request, never a death event or a correct label.

Compare the same retained native pixels separately from changed observation
density. Neither source identity nor known event times enter selection. Existing
chronological and balanced behavior remains available.

## Round, Map and recovery

The opt-in application path attaches `round_visual_candidates` from measured
purchase-to-active or positively supported purchase absence, result onset and
one-point score increments. Persistent result/score support is folded. No extra
semantic score-update timestamp or subsecond qualification is required. See
`round_visual_candidate_integration.md` for missing/occlusion and continuity rules.

Map ordering experiments remain alternatives: the amber marker-context cue does
not replace existing pools or confer ownership. The public catalog metadata and
coordinate scalars are not a solved rotated-minimap calibration or Zone system.
See `development_map_context.md`. Assets are not included in this repository.

`temporal.application generate --checkpoint-dir PRIVATE_CACHE` forwards to the
same acquisition engine as `temporal.match`. Reuse requires matching Source,
runtime, observer, decoder and settings. It replays measurements from the start,
not a half-restored game state. Retained-image output and observation checkpoints
are separate modes. Use a new output directory when resuming; do not overwrite
initial predictions. See `native_observation_checkpoint.md` for crash limits.

## Reproduction outline

1. Register only admitted DEVELOPMENT sources and preserve existing comparisons.
2. Freeze the observer configuration, asset versions and before/after conditions.
3. Run `python -m valorant_ai_coach.temporal.application generate --policy
   PRIVATE_POLICY --source-id REGISTERED_SOURCE --reader-config PRIVATE_CONFIG
   --observer valorant_ai_coach.temporal.composite_view:CompositeViewObserver
   --refinement-policy evidence --checkpoint-dir PRIVATE_CACHE --output NEW_OUTPUT`.
   Supply the existing explicit state-reconciliation opt-ins used by the comparison.
4. Verify native acquisition receipts, JSON/CSV equality and evaluation consumption;
   open `temporal.viewer` or `temporal.comparison_viewer` with the same private policy.
5. Score only explicitly reviewed native frames. Record per-match failures,
   abstentions, NOT_OBSERVED and unlabelled state changes separately.

Private media, native PTS, review labels, profiles and model weights stay outside
Git. Public reporting contains implementation, synthetic tests and anonymized
aggregates only. Main integration and Production adoption require separate review.

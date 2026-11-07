# Staged integration plan for the development timeline

Audit basis: GitHub main `ef4eec3`, Draft #115–#134 latest heads through
`4ae23d7` (#134), checked again on 2026-11-07. All eighteen Draft head and
base SHAs remained unchanged, open and Draft; #121 and #124 are Issues. A local
merge-tree of current main and #134 is clean. This does not validate semantic
behavior on a future integration commit. Preserve the Draft histories and do
not merge main yet.

## Function map and dependencies

| Function | Drafts | Proposed treatment |
| --- | --- | --- |
| A. Shared timeline structure | #115, #120 | Bring the native observation identity, single `DevelopmentGameTimeline`, uncertainty, and observed transition-witness contract into the foundation slice. |
| B. Native acquisition and output | #122, #129, #130 | Bring source-blind intake, Source/PTS/pixel receipts and bounded sampling; keep wider padding and pixel-cache experiments opt-in. |
| C. Application, desktop and review | #123, #125, #134 | Bring JSON/CSV, validated localhost viewer, frozen transfer checks, candidate-only evaluation handoff and comparison/GUI entry; split #134's advisory provider additions. |
| D. Round/life/camera research | #116, #117, #126, part of #128, #132, part of #134 | Retain owner/episode and clock-context candidate methods behind development flags; do not adopt blanket death demotion or Round-gap marking from #134. |
| E. Map/HUD research | #118, #119, #127, part of #128, #131, #133, part of #134 | Keep strict current ownership separate from provisional Map roles, and displayed HUD values separate from held weapon or recorder facts. |
| F. Verification and comparison | #122, #125, #129, #130, #132, #134 | Retain source-binding validation, replay controls, cross-match review and decision history with each responsible slice. |

The parent chain is
`#115 → #116 → #117 → #118 → #119 → #120 → #122 → #123 → #125 → #126 → #127 → #128 → #129 → #130 → #131 → #132 → #133 → #134`.
Every listed base SHA equals its predecessor's head SHA. Directly merging an
upper Draft includes all lower Drafts. Function grouping therefore requires
selective integration commits on a new branch, not an out-of-order PR merge.

## Proposed slices

1. **Freeze the interface and baselines.** Record main, #134, source and
   recognizer fingerprints, the eight existing application receipts, formal
   Fact/Event zero, and the frozen one-second versus six-second padding results.
   Save a rollback commit before selective integration.
2. **Core development state.** Extract #115's native observation contract and
   one shared engine, plus #120's measured lower-witness behavior. Keep
   qualification and Production imports unchanged. `observation()` and
   `DevelopmentGameTimeline.add/rebuild` must retain Source/epoch/native PTS,
   original measurements, candidate alternatives and UNKNOWN.
3. **Source-bound acquisition.** Extract #122's whole-file intake and native
   output, then add #129's bounded sampling controls and #130's pixel cache as
   optional helpers. Source admission, original-video hashing, exact native PTS,
   dimensions, pixel hash, decoder fingerprints and separate audit sidecars
   remain mandatory. One-second defaults and prior receipts stay readable. A
   new short-window `1/5`-second cadence has been exercised on five admitted
   physical matches: 195 retained native points with byte/pixel checks and
   exact-cache payload parity. It is a targeted evidence route, not a new
   full-match accuracy claim or a replacement default.
4. **Application and review.** Extract #123's application/CSV/evaluation
   handoff and viewer, #125's transfer validation, then #134's cross-match
   comparison and desktop launcher. The comparison consumer must use the same
   application bundles and validated original-media route. Formal engine input
   remains empty; unqualified rows live only in `development_*` channels.
5. **Research add-ons.** Integrate owner/life/camera, clock, Map and HUD
   suppliers in small opt-in commits after the core contracts pass. Split
   #128's clock rule from HUD value transport and #134's comparison GUI from
   Ammo/Credits/Zone projections. #127 provisional Map roles, #130 wider
   context, #131 visibility and #133/#134 inventory/location values must not
   imply owner, current weapon or movement. Rejected #134 state experiments
   remain recorded but unadopted.

The opt-in controls that require explicit review include `buy_clock_expiry`,
`active_clock_bridge`, `provisional_map_roles`, `optional_hud_values`,
`report_view_bridge`, `refinement_padding_seconds` and
`refinement_selection_policy`. A new merge must not quietly turn these into
the application default. Keep the sealed one-second and six-second acquisition
conditions distinct; the latter changes some previously known state values
that have not been adjudicated at whole-match scale.

## Compatibility and verification gates

- `DevelopmentGameTimeline` owns development Round/life/camera state once.
  `rules.DeterministicRuleEngine` is the existing formal consumer; it must not
  receive unqualified candidates as Facts/Events. No new state engine belongs in
  acquisition, Map/HUD suppliers, application or GUI.
- Check `SourcePolicy` and `freeze_native_sample` at every intake. Preserve
  `development_game_timeline_v2`, `development_application_timeline_v1` and
  comparison-manifest version handling or supply explicit migrations. A stored
  bundle with an unknown or mismatched fingerprint must fail closed.
- Run tests for native PTS/pixel/epoch identity, protected/foreign Source
  rejection, exact JSON/CSV row agreement, original-video seek, same-second
  conflict, missing observation, Map packet retention, candidate-only evaluation
  and desktop viewer shutdown. Compare all eight saved application outputs at
  matching configuration and common native points. Report newly changed known
  values separately from UNKNOWN and candidate counts.
- At the final integration SHA, run Linux and Windows tests, static/Text I/O
  checks, Windows PyInstaller and packaged smoke. Historical #115–#134 checks
  do not qualify the new SHA. #122's Linux mypy failure was repaired by #123's
  typed diagnostic boundaries; retain that regression control.
- Use the integration branch for a merge rehearsal and a complete diff review.
  Revert the last slice on failure. Retain original Drafts and immutable private
  receipts so another slice can be retried without replaying exposures. Main
  merge needs a separate decision after exact-head validation.

## Related Issues

- [#121](https://github.com/shark-man0/eval_valorant_perspective/issues/121)
  owns the minimum usable development flow; the working foundation is not a
  recognition qualification.
- [#124](https://github.com/shark-man0/eval_valorant_perspective/issues/124)
  tracks recognition quality and independent generalization.
- [#16](https://github.com/shark-man0/eval_valorant_perspective/issues/16)
  requires separate current-main Round-boundary qualification before formal
  lifecycle adoption.
- [#21](https://github.com/shark-man0/eval_valorant_perspective/issues/21)
  requires separate player-owner Fact qualification. Candidate owner recovery
  in this stack does not close it.
- [#97](https://github.com/shark-man0/eval_valorant_perspective/issues/97)
  and [#105](https://github.com/shark-man0/eval_valorant_perspective/issues/105)
  call for candidate generation, ranking and a governed learning loop; the
  current opt-in candidate experiments do not demonstrate those endpoints.

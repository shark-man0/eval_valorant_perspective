# Current owned HP fact propagation review

## Evidence and decision

KEEP CURRENT OWNED VALUE FACTS. The opt-in HP reader already produced 130 player-owned HP observations and 130 HP snapshots, but zero HP deterministic facts. FactBuilder omits HP, and snapshots have no field-specific reader confidence. Generic `player_hp_armor` ROI scores exceed .90 in 2,291 observations without an owned HP value; those scores alone cannot authorize a player fact.

## Contract

Reserve `quality.roi_confidence.hp_value` for the actual accepted current HP reader result after normalized integer validation, calibration and existing ownership clearing. Armor-only, malformed, rejected, uncalibrated and non-owned outputs produce zero. Existing generic ROI confidence cannot fill this reserved signal. A cross-checked .80 reader result can remain an observation under the existing value contract but cannot become a new HP fact.

Seed source-`hud` point facts only when current primary state is `live_first_person`, `player_specific_hud_valid` is exactly true, calibration notes are present without `calibration_required`, HP is an integer 0..100, timestamp is finite/nonnegative, and reserved reader confidence is .90..1.0. IDs use `HH`, separate from `HT` timer facts. Exact timestamp/value duplicates are deduplicated; enrichment preserves original current-reader confidence. World-view eligibility remains separate: owned HUD values can be valid through smoke or world-detail ambiguity. No interpolation, stale HP, damage, HP-loss or death inference is added.

## Clean reproducibility

Analyzer commit `3e9df3dab16d6dce83f3973f0386638d11286c0c`; Clean E2E `20261004T130701Z-bb7e94b4`; `git_is_dirty=false`. Video SHA256 `71d58558559d6f578433ce9f234bf176f76fd5a86657dbfe3eba1e7d36136b06`. Private profile asset fingerprint `e7987bf758eb2dca8211149b6fde9bddcb04a07997f1fb66cb38e8c677580e57`; sidecar SHA `8e764d6eb2b7a6a8ce6a5f144300bdf809f16f9dcf2b689ac659333c2265b615`; HUD layout SHA `a3678bcd9df35d0932ae0e69495eb5b87a3ab40e9c988560d502a9507d59eef1`. Numeric references and detailed frame evidence remain private.

## Actual pipeline result

All 4,081 observations are identical to the immediately preceding HP-reader run after removing only the new reserved confidence. States remain live 166, spectator 335, remote 33, buy menu one, UNKNOWN 3,546. All 130 HP facts match a current owned observation and its reader confidence (.971359.. .995249); false HP authorizations zero. The 1,477 Timer facts are exactly unchanged. Events, all 535 snapshots, round window, round metadata, aggregate quality, frame records and trace are unchanged. Fact IDs are unique; package/enrichment schema validation and enrichment idempotency pass.

E2E remains 22 passed / 56 failed / 4 not evaluated; negative assertions remain 20 passed / 0 failed. This improves fact availability without claiming the event/ownership/map failures are solved. Compared with the earlier no-HP reader, the existing HP-sensitive state-change tuple generated 15 additional `state_snapshot` updates; no death or damage events were invented. This fact-propagation phase makes no additional event change.

## Verification and next work

Pytest 830 passed / two existing environment skips; Ruff `src tests scripts` passed; mypy passed over 86 source files; diff check passed. New tests independently attack primary-state and exact-ownership gates, malformed values/confidence/timestamps/calibration notes, geometry-only scores, armor-only/missing reader outputs, current-frame clearing, cross-checked sub-.90 rejection, owned HUD with ambiguous world view, mixed Timer/HP seed preservation and enrichment idempotency. The separately executed real-video clean run supplies the runtime verification omitted by the environment-dependent raw-video unit fixture.

Continue with the largest concrete downstream blockers: configured score values and phase-title context are absent, and Map marker segmentation was never configured. Score recognition needs whole-field completeness and current header context; a matching isolated numeral cannot establish either. Map geometry recovery and unique self-marker ownership require separate evidence. Do not weaken identity or negative safety to enable either path.

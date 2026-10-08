# Global round start evidence: contract and implementation

## Original diagnostic proposal (before authorization)

The following proposal records the pre-authorization investigation. The user subsequently authorized a qualified independent global system-event path and assertion-fixed timer/score development. Current implementation and remaining gates are below; the historical hypothesis is still not adopted as a recognizer profile.

## Problem and exact scope

Current production start detection requires `live_first_person` and HUD confidence >=0.65 at the candidate and later confirmation. Even after independent semantic phase confidence reaches `pre_round`, a globally visible round transition cannot start when player identity remains unknown. Missing accepted timer values also immediately invalidate production pending starts.

This investigation does **not** change either condition, generate production events, convert unknown state or adopt a recognizer profile. A diagnostic-only hypothesis tests whether independently qualified global phase/timer evidence could support a system event. It has no GT windows, round IDs, evaluation pack or labels as inputs. The exact targets are `GT-R1-ROUND-START`, `GT-R2-ROUND-START`, `event_count_constraints-000` and `event_count_constraints-004`; their production assertions are not declared passing.

## Hypothesis and safeguards

The proposal requires prior confirmed semantic purchase phase (source-supported text ROI confidence >=0.90), accepted prior/current shared timer-value scores >=0.90, a timer reset >3 seconds and a separate later strong timer observation over at least 0.05 seconds. The current state must be unknown or live with no blocking flags; menu, spectator, renewed phase, accepted contradictory/increasing timer, weak accepted timer or explicit discontinuity reject pending evidence. Missing timer readings are neutral only within a one-second candidate deadline and continuous observations. Nothing fills their numeric values. Confirmation preserves the first candidate PTS and all neutral PTS as provenance. A latch prevents repeated proposals until a new corroborated purchase sequence. It does not produce end proposals.

These rules are an **experimental evidence contract**, not a claim that existing production safety policy can be removed. The experiment exists only in `scripts/diagnostics/global_round_start_hypothesis.py`; production `RoundLifecycle` and `HudDirectEventBuilder` do not import or use it. Sixteen synthetic tests cover missing evidence, weak confidence, jitter/contradiction, gaps, deadline, explicit cut, menu/spectator interruptions and two preparations. They also verify that production emits no events from the same unknown-state inputs and that diagnostic processing does not mutate those inputs.

## Source replay

Every archived native PTS was freshly processed in 3.8–4.3 seconds (13 frames) and 111.25–111.6 seconds (six frames), with three genuine calibration prefix frames per window. The structural phase profile supplies geometry/identity/phase. Only the existing timer reader from rejected profile16 is reused through the analyzer's normal reader interface for this diagnostic; timer ROI equality and both profiles' fingerprints are verified. No profile file, reference, reader algorithm or recognition threshold was changed. Source video and completed archive hashes are checked before and after; reader assets are checked within and across windows.

| Source window | Prior phase/timer PTS | Candidate PTS | Confirmation PTS | Timer evidence | Confidence |
| --- | ---: | ---: | ---: | --- | ---: |
| R1 start vicinity | 4.086003 | 4.152669 | 4.252669 | 0:00 → 1:39 → 1:39 | 0.963303 |
| R2 start vicinity | 111.402669 | 111.436003 | 111.519336 | 0:00 → 1:40 → 1:39 | 0.953142 |

Those six images were manually reviewed **after predictions** and visibly show the listed displays and purchase text disappearing after the prior frame. This is diagnostic image provenance, not new validation GT or independent numeric holdout qualification. Reader acceptance totals 15/19; six accepted readings were reviewed, nine accepted readings remain numerically unreviewed, and four readings were unknown. Profile16's three known false timers elsewhere remain disqualifying. None of this permits adopting that profile.

Neutral unknown timer PTS are 4.169336/4.202669 for the first candidate and 111.502669 for the second. All 19 primary states remain unknown with player ownership invalid. The proposal does not fix identity or infer owned values. The two candidate timestamps lie inside the existing acceptance windows when compared **after prediction**; the predictor does not know those windows. Production still emits zero starts and ends; the native builder correctly rejects both all-unknown windows. Proposals are not fed into native packages, trace or canonical evaluation.

Runtime: **59.966 seconds**. No comparable previous combined-input hypothesis replay exists; runtime delta is unmeasured. Machine-readable hashes, source/proposal records and verification are in [global start diagnostics](../e2e_reports/match_001/global_start_contract_diagnostics.json). Canonical historical counts remain23/55/4, current full counts and delta are unmeasured. No full E2E was run.

## What this changes in the diagnosis

The next problem is not only missing numeric configuration: global event detection also depends on player-live classification and immediate timer availability. Completing only an OCR profile does not necessarily resolve either start. The source observations support investigating a system-event-specific global evidence path while maintaining all identity and ownership requirements for player outputs.

Before production adoption, that contract needs a safe, independently qualified timer source, broader continuous positive/negative validation, real discontinuity handling and qualified R1 end evidence. The short windows do not replace required 3–6 /72–77 /109–114 validation. This proposal does not resolve R1 end, package scope or any of the29 assertions. Windows runtime remains unverified.

Related verification after diagnostic wiring: **85 tests passed in24.68 seconds**, with the existing external validation pack explicitly configured. Ruff passes for src/tests/E2E/diagnostics; mypy passes for98 source files; `git diff --check` passes. Production acceptance has not been changed by this follow-up. The saved proposal was presented for contract clarification because the Goal explicitly identifies “複数の設計案がありproduction仕様が大きく変わる” as a reason to confirm direction. Adding unknown-state system events and bounded neutral timer readings changes boundary admission; it must not be disguised as a confidence-only fix. That decision is pending, independent of qualifying a safe numeric profile.

## Authorized production implementation

The user authorized identity-independent `round_start` / `round_end` as system events, conditional on qualification of global inputs, negative controls and continuity. Numeric development may use source frames, with training/holdout separated and assertions unchanged. Validation expected values, windows and IDs never enter production or candidate selection. Player identity, ownership and HP/weapon/death/shot policy remain independent.

`hud/global_lifecycle.py` implements the opt-in contract. `RealHudAnalyzer` discovers `<layout-stem>.global_qualification.json` (or an explicitly provided path). The report must match the layout/template/assets base fingerprint and the shared HUD source fingerprint. The aggregate analyzer fingerprint includes report bytes; injected readers cannot inherit profile qualification. Missing/malformed/mismatched qualification never activates the global path. Legacy profiles keep the existing boundary path.

The report has exactly `schema_version`, `profile_fingerprint`, `recognizer_fingerprint`, and `components`. Required components are `timer`, `purchase_phase`, `continuity`; optional `score` and `round_result` are both required for end detection. Each component records distinct training/holdout/negative hashes, reviewed correct/unknown/wrong counts, negative false-positive count and review provenance. Training/holdout/control splits must be disjoint both within and across components. The loader's support floor is three distinct cases per split with at least three reviewed correct holdout cases, zero wrong and zero false positives. This floor is a consistency gate, not a claim that three cases suffice for real safety qualification; broad independent review and final canonical full remain mandatory. There is no real accepted report yet. Synthetic unit reports are not copied into runtime profiles.

### Runtime and state contract

Every participating frame needs `global_continuity` attestation with a nonempty source segment, confidence >=0.90, exact source PTS and matching qualification-report hash. A gap, explicit cut, changed segment, absent/weak/stale attestation resets the lifecycle. Missing cut markers alone never authorize continuity. There is currently no qualified runtime continuity producer, so real activation remains blocked on evidence development, not user permission.

Two confirmed preparation observations arm the start path. A qualified phase plus accepted prior/current timer confidence >=0.90 and reset >3 seconds stages the actual candidate PTS. A distinct later accepted timer over >=0.05 seconds must consistently count down. Missing timer stays unknown and is neutral only within the one-second deadline and positively attested continuous observations; weak/contradictory accepted values, phase/menu/spectator interruptions or timeout discard it. Confirmation retains the first candidate PTS, confidence minimum, neutral observations, segment and source/profile/report/code fingerprints.

An active round ends only with a qualified semantic result and distinct-frame accepted ally/enemy scores, each with reserved value confidence >=0.90, showing exactly one side incrementing by one in the same segment. Generic ROI scores never substitute for reader-value confidence. This initial end route does not solve the transient R1 banner/after-cut score case; it does not backdate or join across cuts. No banner alone, death inference, timer disappearance alone or missing R2 end creates an end.

The event builder selects one boundary path for an opted-in profile, avoiding parallel legacy/global duplicate events or fallback on missing global inputs. Other player events continue through existing safety gates. System events enter native packages and trace with actor/time/type/provenance intact. Neither the lifecycle nor event builder writes player identity or assigns self ownership. Existing package rules associate preparation with the subsequent detected round; synthetic integration covers two separate packages with unknown identity and no self ownership.

### Verification and remaining gates

Related unit/integration/trace suite: **159 passed in27.15s**. Ruff passes; mypy passes for99 source files. Coverage includes duplicate suppression, two rounds with only one end, cut/segment/gap/timeout/weak/stale evidence rejection, qualification split/code/profile failures, injected-reader rejection and native-to-trace propagation. [Machine-readable implementation evidence](../e2e_reports/match_001/global_lifecycle_implementation_diagnostics.json).

No real profile is enabled, no new numeric candidate has yet been qualified, and no fresh targeted/sampled/full result or canonical PASS gain is claimed for this branch. Last full baseline remains23/55/4; new current/delta are unmeasured. Next develop safe timer/score and runtime continuity inputs with independent frozen splits, then continuous boundary/negative validation, sampled/regression and canonical full. Thresholds, validation pack and sampler remain unchanged. Windows Python uses the same code/profile shape; runtime and bundled availability of source files used in qualification fingerprinting remain unverified.
# Composite source producer follow-up

The qualified analyzer now obtains continuity internally from `CompositeSourceContinuity` rather than externally supplied signal tokens. Accepted prior/current timer physics (or prior confirmed purchase phase plus reset) and distributed nonflat camera-grid NCC evidence are jointly required; missing evidence breaks the segment. This implementation is opt-in through the existing code/profile-bound qualification loader. No real qualification report has been created. Training-only source simulation is not independent holdout or boundary acceptance. The producer never promotes player-owned facts. See [current implementation, tests and qualification blockers](round_lifecycle_implementation.md#opt-in-composite-source-continuity-producer).

## Producer binding and preparation duration follow-up

Qualified analyzers ignore externally supplied global, semantic phase and phase/result-template signals. Final supplemental merging cannot replace internal continuity or measured reader confidence. Explicit content-cut notices still interrupt the route. The start consumer counts actual phase observations in the currently attested segment: at least two distinct observations must span the existing0.05sec minimum. Earlier semantic text-confirmation PTS are not a substitute for segment-local preparation. Preparation endpoints/count and minimum phase confidence enter event provenance without changing player ownership.

Before-fix controls reproduce external-proof overwrites in4/4 synthetic analyzer cases and a start from a10ms phase pair in one synthetic duration case; fixed controls reject them while a three-source-point0.05sec preparation control still starts. Current related183 tests pass; Ruff/mypy100 pass. Saved-source optimistic replay remains0starts over263frames, so safe initialization is still an input/continuity blocker. No real report or candidate is adopted; current code binding invalidates older freezes. [Detailed scope and measurements](../e2e_reports/match_001/global_source_contract_diagnostics.json).

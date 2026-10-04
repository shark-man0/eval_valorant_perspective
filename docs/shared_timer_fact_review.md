# Shared timer fact confidence review

## Evidence and diagnosis

Clean analyzer 0d99b1d produces 1,587 accepted timer observations; 1,386 occur with UNKNOWN primary state. Only 201 timer snapshots survive aggregate state-confidence filtering. The RoundPackage contains zero seeded deterministic facts and aggregate HUD confidence zero. FactBuilder would inherit that aggregate confidence for snapshot-derived timer facts. This couples a shared observable value to incomplete actor classification.

## Bounded contract

Preserve a shared current-frame timer as a HUD DeterministicFact with its accepted value-reader confidence. Keep every identity gate, primary state, flag, ownership rule, snapshot filter, round window and event rule intact. Facts refer only to observations already inside the existing round window; they do not infer round starts, round identity, timer continuity or player state.

The analyzer publishes reserved quality.roi_confidence.round_timer_value from an actually accepted current timer reader result, or zero when absent. Generic round_timer ROI confidence can describe geometry/features and cannot authorize a value fact. The reserved key fits the existing numeric confidence-map schema. A crosschecked .80 reader result remains .80 and cannot seed a .90 fact. Uncalibrated input never reads values; calibration_required also rejects seeding.

The consumer requires nonboolean finite numeric value, timestamp and confidence, nonnegative value/time, and confidence .90..1. It seeds only round_time_remaining_sec with source hud and the exact observed time. No temporal interpolation or stale value is added. Exact time/value duplicates are removed; distinct observed times remain distinct. HT IDs are separate from map MZ and FactBuilder FB IDs. Existing exact-key/value/time dedup preserves direct confidence during enrichment.

## Diagnostic replay and safety

Private replay of already source-accepted values predicts 1,477 timer point facts within the unchanged existing window, including 1,276 UNKNOWN points. All survive FactBuilder enrichment with confidence 0.900061..0.993196 and schema validation. This is diagnostic-only prediction, not new-analyzer Clean E2E confirmation. No player-specific values, ownership or events are promoted.

Tests exercise UNKNOWN actor preservation, weak/malformed confidence, null/invalid values, geometry-only confidence, uncalibrated input, current-frame acceptance, crosscheck .80, exact dedup, ID uniqueness, schema validity and equality of events/snapshots/windows/aggregate quality. The normal pipeline trusts its typed analyzer observations; arbitrary caller-forged metadata is outside that existing producer contract.

## Decision

IMPLEMENT SHARED TIMER VALUE FACT PROVENANCE; verify full tests/static checks, then committed-source clean E2E. This does not resolve overall E2E failures or change actor identity.

## Integration verification

Full pytest: 793 passed / 2 existing environment skips. Ruff src/tests/scripts passed; mypy 85 source files passed; diff check passed. Independent read-only review found no concrete safety gap. Clean E2E confirmation follows this source commit; diagnostic replay above remains labeled as prediction.

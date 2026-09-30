# Integration notes for Codex

- v3 supersedes the v2 E2E pack.
- Runtime must not read `ground_truth/`, `assets/`, `tests/generated/`, or fixture expected values.
- Emit a trace matching `schemas/e2e_output_trace_schema_v1.json` and run `tests/evaluate_trace.py`.
- Use Map/Zone v3 plus the observed-Japanese-label overlay; do not convert spectator raw labels into target-player position.
- Instrument temporal features that carry durations/lead times so the discontinuity guard can verify they do not cross `DISC-001`.
- Preserve all source audio tracks in generated evidence clips; semantic audio remains disabled.
- Synthetic fixtures test contracts/consumer logic and must not be treated as substitutes for real perception regression videos.

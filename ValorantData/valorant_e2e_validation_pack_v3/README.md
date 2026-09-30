# valorant_e2e_validation_pack_v3

Independent E2E validation corpus for the exact 171.019336s source clip `Valorant_09-25-2026_0-37-29-379.mp4`.

v3 supersedes v2. It keeps the source-grounded philosophy of v2, then closes the remaining harness defects that could be fixed without inventing new footage.

## Canonical files

- `E2E_VALIDATION_SPEC.md` — semantics and integration contract
- `ground_truth/timeline_ground_truth_v3.json` — canonical observed facts
- `ground_truth/negative_assertions_v3.json` — must-not-happen controls
- `ground_truth/sync_anchors_v3.json` — PTS/game-clock/score anchors
- `ground_truth/frame_pts_sidecar_v3.json` — exact presentation PTS nearest every reference frame
- `ground_truth/coverage_matrix_v3.json` — what this fixture does and does not prove
- `inputs/e2e_inputs_v3.json` — runtime-visible inputs only
- `tests/generated/e2e_assertions_v3.json` — generated from canonical GT, never hand-maintained
- `tests/evaluate_trace.py` — evaluate a Codex/runtime trace against the oracle
- `tests/validate_pack.py` — full corpus validation
- `fixtures/` — synthetic contract fixtures for shot granularity, temporal consumers, and Map/Zone resolver mechanics
- `fixture_requirements/real_video_gap_manifest_v1.json` — real recordings still required for perception-level coverage

## Quick validation

```bash
python tests/build_assertions.py
python tests/test_meta_evaluator.py
python tests/validate_pack.py --source-video /path/to/Valorant_09-25-2026_0-37-29-379.mp4
```

To evaluate an actual analyzer trace:

```bash
python tests/evaluate_trace.py --trace /path/to/e2e_trace.json
```

The source MP4 is intentionally not duplicated in this ZIP.

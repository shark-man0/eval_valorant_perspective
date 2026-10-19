# Round-boundary source preflight (independent integration candidate)

A qualification report can be stale or a targeted source window can have gaps even when an earlier experiment succeeded. `scripts/e2e/preflight_round_source.py` provides a read-only preflight before recognition: verify source SHA256 and the unedited-input contract, inventory original integer PTS/timebase, and optionally check current loader admission and explicitly requested short native windows.

This extraction is independent of PR #42's reader changes, geometry-reference transport, private assets and historical research reports. It changes no production recognizer, default sampling, event timestamp, GT window, ownership or qualification policy. It does not implement the sampled prefix in PR #51, the evaluator policy in PR #48 or the decoder endpoint fix in PR #54.

## Behavior

- Source SHA mismatch rejects before launching the probe or loading the contract.
- Preserve nonzero PTS origins, exact source timebase, frame order and variable cadence. A uniform cadence does not prove capture-loss absence or scene continuity.
- Window summaries re-read encoded/pixel hashes, reject mixed source/decoder epochs/timebases/geometry, and report adjacent repeated rasters without deleting them.
- Optional layout/template/bundle parameters invoke the existing current-code admission path. Admission is explicitly separate from independent temporal qualification.
- There is no Validation Pack argument, reader replay, event output, new bundle generation or production installation.
- Missing private profile/bundle produces an explicit blocker, never fabricated qualification.

The script has a source-only metadata probe, which can enumerate the complete video's PTS. This is not Full E2E or recognition. Native PNG decoding occurs only for explicitly supplied `--window START END` arguments, under the declared output budget.

## Invocation

```bash
python scripts/e2e/preflight_round_source.py --help
```

Provide a private source file, its expected SHA256 and an unedited-input contract. Keep all source/profile/bundle paths and generated detailed reports private. `--template-profile` requires both the layout profile and qualification path. The command's output is an audit report, never permission to release a boundary.

## Extraction validation

Base main: `7e480c2f2f7f49aea73e1541d065d78881d2f11c`.

The script and its 15 source-preflight tests are extracted byte-for-byte from PR #42. On this main-based checkout, source-preflight, native input/replay, assured Start and unchanged End contract tests pass: 174 PASS. These tests use synthetic source images and contracts, not private videos, labels, bundles or independent real-data qualification.

The broader PR #42 audit separately reproduces four spectator test failures on both main and PR #42 under the same local macOS/Python/OpenCV environment (46 PASS / 4 FAIL in the two modules). That comparison does not authorize changing spectator thresholds or treating unrelated failures as formally resolved. Linux/Windows and packaged-smoke status must be checked on this candidate's own HEAD.

Refs #16. Historical real-source measurements remain in PR #42 and do not become fresh evidence through this extraction. No main merge is performed.

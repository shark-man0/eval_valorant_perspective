# Observability architecture

This layer observes runtime behavior without changing Analyzer policy. It must not alter detector thresholds, sampling, confidence/UNKNOWN policy, rule semantics, AI prompts, clip criteria, or evaluation labels.

## Logging

`src/valorant_ai_coach/logging_setup.py` remains the application logging entrypoint and keeps the existing UTF-8 `RotatingFileHandler`. A `ContextVar`-backed filter adds `run_id`, `match_id`, `round_no`, and `phase` to each record. Context is task/thread safe because no mutable process-global run identifier is used.

Rendered log lines are redacted for API-key/token patterns and user-home paths. Do not log request headers, full prompts, raw API responses, keyring contents, or environment dumps. INFO is for major phase/completion/recoverable outcomes, DEBUG for detail, WARNING for degraded optional facilities, and ERROR/EXCEPTION for execution failures.

## Profiling

`PerformanceRecorder` uses `time.perf_counter()` for elapsed durations and `time.process_time()` for process CPU time. `scripts/diagnostics/profile_pipeline.py` is an opt-in runner that wraps existing object methods and delegates the exact arguments/results unchanged. No parallelism, cache, sampling, batching, detector disabling, or threshold adjustment is introduced.

The runner records these phases when present:

- `total`
- `video_probe`
- `frame_extraction`
- `hud_observation_processing`
- `round_analysis`
- `rule_coach_processing`
- `clip_generation`
- `persistence_report_generation`

Some phases are nested, so phase durations are not additive. For example, frame extraction occurs inside HUD processing, and rule/coach processing occurs inside round analysis.

Example:

```bash
python -m scripts.diagnostics.profile_pipeline /path/to/video.mp4
```

Artifacts are written below `outputs/diagnostics/<run-id>/`, which is already covered by the repository's `outputs/` ignore rule.

## Performance report

`performance.json` schema version `1.0` includes:

- run ID and UTC timestamp
- repository commit SHA and dirty state when Git is available
- Python implementation/version
- OS/release/architecture
- per-phase duration, call count, and failure count
- total elapsed time
- process CPU time
- peak memory when the standard library exposes it
- resident memory on Linux when `/proc/self/statm` is available
- active thread count
- optional Raspberry Pi temperature/throttling state
- FFmpeg/ffprobe versions for the executables selected by the profiled run
- NumPy/OpenCV distribution versions
- success/failure status and diagnostic failure category

Unavailable resource metrics are `null`; they do not fail profiling. Peak RSS is obtained with the standard `resource` module on POSIX and is intentionally unavailable on Windows rather than adding a mandatory monitoring dependency.

## Error taxonomy

Diagnostics classify failures without changing exception types or control flow:

`environment`, `dependency`, `input`, `ffmpeg`, `video_probe`, `frame_extraction`, `hud`, `visual`, `map`, `round_analysis`, `ai`, `clip`, `storage`, `cancelled`, or `internal`.

The classifier is metadata only. The original exception is still raised by the Analyzer path.

## Diagnostic bundle

Generate a bundle with:

```bash
python -m scripts.diagnostics.create_bundle <run-id> --log /path/to/valorant-ai-coach.log
```

The ZIP is allowlist-only. It may contain `manifest.json`, sanitized `performance.json`, sanitized `dependency_snapshot.json`, and a bounded/redacted recent log tail. It never recursively archives a directory.

Explicitly excluded by policy: raw video, screenshots, HUD crops, Validation Pack files, databases, full environment dumps, API credentials, raw API responses, private profile images, and arbitrary user files. JSON inputs are size-bounded, malformed JSON becomes a small error record, and the log tail is bounded by bytes, lines, and final character count.

## Privacy boundaries

Machine-identifying data is intentionally omitted from shared artifacts: hostname, username, home path, MAC/IP address, serial number, and full environment variables. Local paths are sanitized before a shared report or bundle is written. Local application operation may still use private paths internally; they are not copied verbatim into shared diagnostics.

## Existing E2E relationship

The E2E runner already owns dataset/source identity, pack identity, settings fingerprints, and allowlisted shared reports. Observability does not recompute or redefine those E2E contracts. The new snapshot/report is for runtime comparison and troubleshooting; it must not be used as an accuracy gate.

## CI handoff

No `.github/workflows/` files are changed here. The CI owner may add these commands after merge:

```bash
python -m pytest tests/unit/test_observability.py
python -m scripts.diagnostics.doctor
python -m scripts.diagnostics.snapshot --output outputs/diagnostics/ci/dependency_snapshot.json
```

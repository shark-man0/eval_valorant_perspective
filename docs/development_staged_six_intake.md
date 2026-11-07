# Six-source staged intake (development only)

`temporal.staged_validation` reserves six newly supplied full-match Sources with
format/stream metadata only. It does not open media bytes, run ffprobe, copy the
files, decode packets or frames, perform recognition, or create GT. The caller
must separately measure each file's SHA-256 before and after a format/stream-only
probe, confirm stable size, and obtain the user's permission, unused history,
physical-match separation from each other **and all prior recordings**, and
unedited full-match declaration. Unknown prior physical overlap blocks intake.
Pass every prior private registry root; canonical repository manifests are read
automatically. The prior registry is read only.

The private declaration has this shape. The six `source_id` values end in
`_001` through `_006` in filename sort order. All paths, hashes and metadata
below are placeholders. `video_codec` comes from the one video stream in the
format/stream probe; no packet or frame listing is accepted.

```json
{
  "version": "development_staged_six_metadata_v1",
  "seed": "staged-six-20261108-v1",
  "content_kind": "VALORANT_FULL_MATCH",
  "declarations": {
    "permission": true,
    "unused_for_development": true,
    "distinct_physical_matches": true,
    "distinct_from_prior_physical_matches": true,
    "unedited_full_matches": true,
    "hash_verified_before_after_probe": true,
    "probe_format_stream_only": true
  },
  "records": [
    {
      "path": "/PRIVATE/example-001.mp4",
      "filename": "example-001.mp4",
      "source_id": "example_001",
      "size_bytes": 123456,
      "source_sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
      "duration_sec": "2400",
      "width": 1920,
      "height": 1080,
      "fps": "60/1",
      "native_time_base": "1/15360",
      "video_codec": "h264",
      "physical_match_id": "physical_001"
    }
  ],
  "run_flags": {
    "coarse_seconds": "1",
    "dense_seconds": "1/5",
    "max_refinement_windows": 40,
    "refinement_selection_policy": "balanced",
    "refinement_padding_seconds": "1",
    "report_view_bridge": true,
    "buy_clock_expiry": true,
    "provisional_map_roles": true,
    "active_clock_bridge": true,
    "return_display_tail": true,
    "buy_clock_tail": true,
    "retain_frames": false,
    "audit_sample_plan": null
  }
}
```

The real declaration has exactly six records and every run flag. Run flags
must match **all** corresponding settings in the previously frozen protocol.
That protocol binds code SHA, observer fingerprint, configuration, models,
profiles, thresholds, runtime and binary hashes. The staging runner also
compares every active temporal runtime file against the frozen file hashes,
so adding this wrapper does not silently change the old recognizer. Do not
modify `validation.enroll_sources`: it copies and fully decodes every source
and assigns every source to DEVELOPMENT.

```python
from pathlib import Path
from valorant_ai_coach.temporal.staged_validation import (
    activate_first_development, confirm_pilot, register_six, run_first,
)
from valorant_ai_coach.temporal.replay import file_sha

registry = Path("/PRIVATE/new-staged-registry")
batch = registry / "six-20261108"
allocation = register_six(
    declaration=Path("/PRIVATE/staged-declaration.json"),
    protocol=Path("/PRIVATE/frozen-old-recognizer-protocol.json"),
    registry=registry,
    batch_id="six-20261108",
    prior_registries=[Path("/PRIVATE/all-prior-registry-roots")],
)
policy = activate_first_development(batch)
source_id = allocation["first_development_source_id"]
pilot = run_first(batch=batch, source_id=source_id,
                  output=Path("/PRIVATE/first-pilot"), phase="pilot", pilot_seconds=20)

# Inspect the pilot's source binding, native acquisition/completion, candidate
# outputs and short timeline before deciding whether full processing is sound.
pilot_receipt = batch / "first_pilot_prediction_receipt_PRIVATE.json"
confirm_pilot(
    batch=batch, pilot_receipt_sha256=file_sha(pilot_receipt),
    pilot_check=Path("/PRIVATE/pilot-structural-check.json"),
    review={"input_integrity_checked": True, "candidate_output_checked": True,
            "pilot_timeline_checked": True, "proceed_to_full": True},
)
full = run_first(batch=batch, source_id=source_id,
                 output=Path("/PRIVATE/first-full"), phase="full")
```

The `allocation.json` is append-only private reservation evidence. Deterministic
`sha256(seed + source_sha256)` order allocates two DEVELOPMENT, two
QUALIFICATION, and two FINAL_HOLDOUT Sources; the first ranked DEVELOPMENT
Source is the only activation candidate. The activation manifest admits only
that one Source through the unchanged DEVELOPMENT-only `SourcePolicy`; the
other five hashes are protected. No qualification/holdout run path is exposed.
Further use requires a separate later decision and implementation. The
`future_five_order` field is advisory only.

An attempt is appended before recognition starts. A failure remains in the
journal and cannot be rerun as a new first attempt. Pilot and full outputs use
new private paths; the first prediction receipts bind the actual timeline and
completion SHA-256 and cannot overwrite prior results. A full run requires a
completed informative pilot, a saved `check_output` structural/evaluation
handoff report, and a separate affirmative pilot review. Pilot output is a
short development observation, never a whole-match claim. The caller must
build any pilot preview with an explicit `PILOT_ONLY` scope; the existing
whole-file application export gate remains unchanged. Actual source bytes are
checked by the existing `run_match` source-hash admission at first use.

No stage output establishes recognition accuracy, formal Facts/Events,
qualification, Production readiness, or independence from previous physical
matches without the explicit prior-match declaration. Keep real paths,
metadata, predictions, media, labels and exposure receipts outside Git.

Synthetic contract tests:

```sh
PYTHONPATH=.:src python -m pytest -q tests/unit/test_staged_six_validation.py
```

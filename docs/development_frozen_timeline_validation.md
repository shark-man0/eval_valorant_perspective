# Frozen full-match transfer validation

This development harness extends the application route in Draft #123. It calls
the existing image-only observer, `run_match`, application export and evaluation
handoff. It adds no recognition rules, model, state machine, formal Fact/Event or
Production adoption. Detailed accuracy work remains in issue #124.

## Current evidence and missing input

The available private inventory contains no authorized unused match. The user
cannot supply new recordings immediately. Existing exposed matches and generated
test containers do not satisfy the requirement for two unused physical matches.
Status: **validation infrastructure complete; unseen real-video validation
incomplete**. Accuracy and unseen generalization remain unmeasured. Do not replace
missing inputs with protected, FINAL_HOLDOUT or UNKNOWN_EXPOSURE recordings.

Existing full application outputs were rechecked: 2443, 2523 and 1610 consecutive
one-second rows, resolvable native samples, a correct partial final second,
JSON/CSV content equality and actual evaluation handoff. These are cached
DEVELOPMENT evidence checks, not new unseen acquisitions. The third condition
includes previously acquired sparse Map/Zone supplements.

| Exposed baseline | Rows | Round UNKNOWN | Life UNKNOWN | Camera UNKNOWN | HP | Timer | Score | Map positions / Zones |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| A | 2443 | 793 | 601 | 459 | 1477 | 1677 | 1822 | 0 / 0 |
| B | 2523 | 926 | 543 | 455 | 1723 | 1482 | 1474 | 0 / 0 |
| C, with supplements | 1610 | 627 | 405 | 304 | 963 | 903 | 933 | 16 / 6 |

All coverage figures are counts of bins containing candidates or estimates,
never accuracy or continuously observed duration. Generic Map-name reading,
continuous paths, Armor and Weapon are still unsupported in this reader route.
An unsupported field remains UNKNOWN; a supplementary Map candidate does not
establish current recorder ownership. No new semantic labels were requested.

## Freeze before opening a new recording

Use the repository checkout and installed development environment. Keep private
configuration, weights, recordings, protocols, declarations and outputs outside
Git. Commit the harness before freezing; dirty checkouts are rejected.

```sh
PYTHONPATH=.:src python -m valorant_ai_coach.temporal.validation freeze \
  --reader-config /PRIVATE/shared-reader.json \
  --observer EXISTING_IMAGE_ONLY_MODULE:ExistingObserver \
  --runtime-file /PRIVATE/EXISTING_IMAGE_ONLY_MODULE.py \
  --output /PRIVATE/frozen-protocol.json
```

Supply every external wrapper code file with repeated `--runtime-file`. The
existing observer must bind all actual weights, assets, extraction settings and
thresholds in its fingerprint/bindings. Without `--observer`, the existing
`ProfileHudObserver` is used. Do not substitute an unbound supplier. The protocol
records the commit, temporal/export/evaluation code hashes, complete observer
bindings, configuration hash, interpreter/dependency versions and decoder/probe
paths/hashes. Every run checks these again before and after processing. Repeating
a changed protocol after seeing a recording is a development comparison, not a
fresh independent success on that recording.

Settings are shared for every match: coarse 1 second, dense 1/5 second,
chronological adaptive refinement, maximum 40 windows and the existing 240-second
refinement budget. The existing report-view bridge is on; use
`--no-report-view-bridge` only when fixing a different shared protocol *before*
viewing any new inputs. There are no roster, labels, initial state, known boundary
times, Source-dependent recognition or manual observation-window inputs.

## Register genuinely new authorized recordings

Create a private declaration only after the human has attested permission,
unused development history, different physical matches and unedited full matches.
Example metadata shape (placeholders, not evidence):

```json
{
  "purpose": "frozen_timeline_comparison",
  "content_kind": "VALORANT_FULL_MATCH",
  "declarations": {
    "permission": true,
    "unused_for_development": true,
    "distinct_physical_matches": true,
    "unedited_full_matches": true
  },
  "records": [
    {"path": "/PRIVATE/new-a.mp4", "source_id": "new-a", "physical_match_id": "physical-a"},
    {"path": "/PRIVATE/new-b.mp4", "source_id": "new-b", "physical_match_id": "physical-b"}
  ]
}
```

```sh
PYTHONPATH=.:src python -m valorant_ai_coach.temporal.validation enroll \
  --declaration /PRIVATE/authorized-new-sources.json \
  --protocol /PRIVATE/frozen-protocol.json \
  --registry /PRIVATE/new-transfer-registry --batch-id comparison-001 \
  --prior-registry /PRIVATE/ALL-EXISTING-REGISTRIES
```

Supply **all** previous private registry roots using repeated `--prior-registry`.
The current new registry is always included. Canonical repository manifests are
also consulted. This is metadata-only exclusion: existing reservations, including
rejected/pending ones, cannot be reused. Known paths are rejected before media
hashing, duplicate bytes before probing/decoding, and duplicate Source/physical
IDs before registration. Alternative encodings of one physical match cannot be
proved distinct automatically; the explicit human declaration remains necessary.
Missing registry history cannot be reconstructed by the tool and is not proof of
independence. Never pass an existing protected source with a new identity.

The new experiment registry supports any positive count without changing the
existing nine-source schema, allocations, GT, splits or safety gates. It records
purpose, protocol, declarations and original/managed Source hashes before any
recognition. The new Sources are research DEVELOPMENT/DEVELOPMENT; the separate
initial-unused attestation describes first-use history, not formal holdout
qualification. Existing protected records are never reclassified. Accepted
sources use the unchanged `SourcePolicy` admission path. Original files remain
untouched; managed copies are read-only. Full video/audio null-sink decoding is an
integrity check, not recognition, proof of editing history or gameplay continuity.
Failed entries remain visible in the manifest and comparison.

## Generate, check, view and use

```sh
PYTHONPATH=.:src python -m valorant_ai_coach.temporal.validation run \
  --protocol /PRIVATE/frozen-protocol.json \
  --batch /PRIVATE/new-transfer-registry/comparison-001 \
  --output /PRIVATE/NEW-comparison-output

PYTHONPATH=.:src python -m valorant_ai_coach.temporal.validation check \
  --application /PRIVATE/NEW-comparison-output/new-a/application \
  --output /PRIVATE/new-a-structural-check.json

PYTHONPATH=.:src python -m valorant_ai_coach.temporal.viewer \
  --bundle /PRIVATE/NEW-comparison-output/new-a/application/timeline_PRIVATE.json \
  --policy /PRIVATE/new-transfer-registry/comparison-001/policy_PRIVATE.json
```

Each accepted Source runs in a fresh process, without a pilot limit, audit samples
or manual initialization. The append-only journal marks an attempt **before**
the worker starts. Failed attempts and repeats cannot become a second first-use
success. A worker failure retains its log and any partial acquisition, records
the cause, and allows the next Source to run. Logged decoder PTS describe decoding
progress only, not the last recognized frame or actual event time. If no verified
position exists it is null. Interrupted runs do not receive completion receipts.

Registry and batch runs use exclusive directory locks. After a crash, inspect the
journal and partial output before manually removing the corresponding stale lock.
Do not delete or replace failed reservations or first-attempt journal entries.

`comparison_PRIVATE.json` and `matches_PRIVATE.csv` retain every attempted or
registration-rejected Source. Per-match fields include dimensions, FPS, duration,
codec, Source hash, row/observation/missing counts, Round/Life/Camera values and
status distributions, HUD/Map field coverage, event kinds/counts, elapsed time,
Python peak RSS and output hashes. RSS excludes decoder/OCR child processes and
is null where the platform's existing measurement API is unavailable. Selected
state/HUD signatures permit limited reproducibility comparisons; they do not
assert byte equality across different acquisition epochs.

`check_output` checks the full grid, last partial second, origin/native bin
assignment, native PTS order within each acquisition, sample retention and
evidence/event references. It compares every CSV field with the JSON and checks
that all seconds actually reached the existing scope/evaluation consumers.
Evidence-rich CSV cells above the stdlib 128 KiB default are supported up to a
64 MiB field limit. All-UNKNOWN/no-information output is structurally complete but
`COMPLETE_UNINFORMATIVE`, never a practical recognition success. Missing bins and
unread observations remain distinct; raw native evidence is retained.

The structure check deliberately reports viewer/seek as unverified. For each
new real Source, open the printed localhost URL, inspect whole/Round views,
UNKNOWN spans and candidates, and select several times including near the end to
verify original-video seeking. Record those UI checks separately; do not infer
them from a passing JSON check. Existing GUI/evaluation regression tests continue
to run. Development candidates stay separate from formal evaluation facts/events.

## Reproduce the harness tests

```sh
PYTHONPATH=.:src python -m pytest -q \
  tests/unit/test_frozen_timeline_validation.py \
  tests/integration/test_frozen_timeline_transfer.py
```

The integration test generates two tiny synthetic containers plus an invalid
container. It exercises registration, real native decoding, CLI/worker dispatch,
full partial-final-second export, JSON/CSV validation, downstream evaluation,
repeat exposure accounting and continuation after source failure. Its pixel
supplier is explicitly synthetic and its real-match count is always zero. It is
transport evidence only. No private recording, image, label or model is committed.

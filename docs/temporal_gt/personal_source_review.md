# Private DEVELOPMENT source review

This workflow prepares evidence for a human. It does not run a recognizer, qualify
Round End or Self Death, or enroll a Source-only recording into formal E2E.
Keep the registry, sessions, frames, human responses, PTS and player information
outside Git in access-restricted private storage. Never upload generated HTML.
POSIX output directories/files use 0700/0600; Windows callers must verify private
NTFS ACLs separately, because chmod does not establish equivalent Windows ACLs.

## Preserve the existing registry

Run `scripts.diagnostics.register_private_sources verify` with independently saved
manifest/allocation SHA-256 anchors before review. It checks every accepted
original, managed copy and intake report. Keep `manifest.json`, `allocation.json`
and existing Exposure linkage immutable. New `exposure_journal.jsonl` entries are
hash chained and point to immutable private evidence; they supplement that history.
They do not replace a historical `UNKNOWN_EXPOSURE` or certify independence.

Backup is a separate decision from integrity. A same-disk copy is not an
independent backup. Record backup/restore as unperformed if media is unavailable
or the owner chooses no backup. Do not upload to cloud without approval. If backup
is later requested, freeze a new private file inventory including originals,
managed sources, intake, allocations, contracts, anchors, journals and future GT;
use an encrypted independent failure domain with restricted access, verify every
file SHA, restore to a separate validation location and verify SHA again. Record
results in new receipts rather than modifying the frozen Source-only inventory.
No backup or restore operation is implemented or claimed by this review CLI.

## Prediction-blind planning and evidence acquisition

Examples use environment variables for **private paths and anchors**, never
publish their actual values. Use `PYTHONPATH=.:src` when running from a checkout.

```sh
python -m scripts.temporal_gt.review_session create \
  --batch "$PRIVATE_BATCH" --output "$PRIVATE_SESSION" \
  --trusted-inventory-sha256 "$INVENTORY_SHA" \
  --trusted-allocation-sha256 "$ALLOCATION_SHA"
python -m scripts.temporal_gt.review_session acquire \
  --session "$PRIVATE_SESSION" --acquisition-id pilot_001 --start 0 --end 1
```

Creation selects the first accepted DEVELOPMENT ID before inspecting content.
The source must already have DEVELOPMENT exposure and explicit unedited user
attestation. Other allocations, failed sources and unknown exposure are rejected
before decoding. The frozen plan partitions the whole duration into consecutive
60-second windows, including the tail. It never uses predictions to select windows.
A duration-derived window endpoint is a plan, not a witnessed event PTS.

The private HTML includes a player for **this DEVELOPMENT source only** and a
frame stepper. The human reviews the whole timeline in order, including the
interiors of scheduled windows, to discover missed events and natural controls.
A sparse set of endpoints cannot prove no event occurred. Review progress is not
automatically inferred from playback or frame acquisition. Until a complete window
has an explicit reviewed artifact, its schedule status stays UNREVIEWED.

For a discovered event, acquire a bounded window around its visible transition.
Each call is at most 2 seconds / 180 frames / 256 MiB of PNGs. The session permits
512 MiB total; acquisition can fail earlier for complex native images. Reduce the
requested interval rather than bypassing the limit. Failed requests preserve their
request and exposure record, without accepted GT. The original video is unchanged.
Do not extract the entire match into images. Plan any larger collection as a
separate bounded session, preserving global physical event identities.

Acquisition reuses `decode_native_window` and preflight's `summarize_pixels`.
Every retained image has a verified source SHA, native integer PTS, rational
timebase, real acquisition epoch, encoded and decoded pixel hashes. A second
acquisition has a different epoch: never relabel epochs to join its witnesses.
When Start → End → Next does not fit the evidence, retain missing fields and
UNKNOWN context. Do not invent a midpoint, interpolate evidence, or assert the
complete trajectory from disconnected acquisitions. Wider single-epoch evidence
requires a separately bounded plan under the existing decoder contract.

Optional DEVELOPMENT-only source preflight reuses
`scripts/e2e/preflight_round_source.py` with no profile/qualification arguments.
Save `source_preflight.json` in the session; export links it if present. Do not run
it on evaluation sources for development. `assemble_source_review_plan.py` and
`prepare_boundary_review.py` remain useful for overview planning, but their
float-second overview markers are not substitutes for native GT witnesses.

## Human observations and import

The default page asks plain Japanese observation questions and offers “unknown”
with explicit human-selected reasons. PTS, epoch and hash fields are recorded by
the tool, not entered by the reviewer. Technical observation fields are optional
advanced controls; confirming uncertainty needs no expertise in those parameters.
The human opens `review.html` locally, steps through the acquired interval, fills
observations, explicitly confirms source review and no prediction use, then saves
JSON. None of these confirmations is preselected. Unknown is the default.

Round observations include Active/Start and next-round witnesses when available,
old/new score and clock, last partial/first complete caption, literal round result,
source discontinuity and context. Use positive only with a witnessed transition
bracket. Use negative only after the complete interval is reviewed, with an
existing natural-negative class (buy/menu/spectator, score/clock-only, stale or
partial caption, etc.). Record false End contexts without treating a prediction
as truth. Missing transition/context evidence remains UNKNOWN.

Self Death observations distinguish self control, self/nonself Killer and Victim,
spectator, first/persistent/redisplayed Combat Report, respawn, menu/unknown and
source discontinuity. Positive requires confirmed self identity plus a strictly
ordered `last_confirmed_alive_tick` / `first_confirmed_dead_tick` bracket whose
witnesses exist in the same acquisition. Report presence alone cannot establish
self death. Use a stable physical event key; aliases and overlapping positive
brackets cannot create extra Deaths. Contextual controls may be negative only
after interval review; a report, spectator or menu does not establish a new Death.

```sh
python -m scripts.temporal_gt.review_session record \
  --session "$PRIVATE_SESSION" --acquisition-id pilot_001 --response "$HUMAN_JSON"
python -m scripts.temporal_gt.review_session export --session "$PRIVATE_SESSION"
python -m scripts.temporal_gt.review_session validate \
  --snapshot "$PRIVATE_SNAPSHOT" --trusted-freeze-sha256 "$ROUND_FREEZE_SHA" \
  --trusted-death-sha256 "$DEATH_FILE_SHA"
```

Import retains exact raw human bytes and normalized JSON with hashes, then records
GT creation separately from source viewing. A reported prediction exposure is
journaled and rejected from this source-independent workflow. Accepted receipts
appear only after the complete combined export passes validation. A failed import
retains pending evidence for audit; it must not be silently overwritten. An
amendment needs explicit curator review, a new artifact and preserved history.

Round data uses the unchanged Temporal GT v1 schema, validator and freeze CLI.
Self Death adds only labels in `self_death_source_annotations_v1.json`, bound to
the canonical SHA of the same Temporal source/event/frame/exposure backbone.
`historical_source_review` is the existing development-review status: this does
not certify an independent curator. Every actor here has `independent: false`.
Anonymous output contains counts, blockers and hashes only. It stays readiness
BLOCKED because development curation does not establish independent qualification.
Unreviewed windows are never negative. GT counts are human-confirmed annotations,
not frame counts or detector candidates; unresolved identity remains provisional.

## PTS and pilot limitations

`packet_timing.classify_packets` examines packet metadata only. It distinguishes
cadence jitter within two ticks, possible missing-frame/container artifacts,
missing/duplicate PTS or nonmonotonic DTS, and insufficient data. Presentation PTS
reordering in decode order is not itself a discontinuity. Tail-only diagnostics
must not be generalized to the entire source. A gap neither proves an edit nor
visual corruption. Visual continuity remains UNVERIFIED without human review.
Evaluation candidates receive no development image extraction or predictions.

A pilot checks usability and bindings; it does not complete annotation of a match.
Record actual human counts separately from synthetic tests, unreviewed intervals,
source continuity checks and qualification. Before recognizer work, the human
still needs whole-timeline source review, positive brackets, natural negatives,
UNKNOWN reasons, physical-identity deduplication and appropriate exposure records.

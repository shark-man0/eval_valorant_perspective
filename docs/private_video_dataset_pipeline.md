# Private source intake and allocation

This workflow accepts nine original recordings for later Round End and Self Death
research. The original 5/2/2 allocation remains the default for compatibility;
the opt-in development-all mode uses 9/0/0 for the new, separate batch. It does not change readers, thresholds, canonical GT, qualification,
Validation Packs or existing `match_001` / `match_002` registration. Related work:
#62 (storage), #16 (Round lifecycle), #19 (independent evaluation), #21 (ownership).

## Three separate artifacts

- The original recording stays at the user-selected location, byte-for-byte.
- An external private registry holds a read-only managed copy, the frozen
  allocation, per-source intake/result records and a final private inventory.
  `datasets/private_source_inventory.schema.json` validates this inventory. It
  deliberately cannot substitute for `datasets/manifest.schema.json`: E2E
  registration still requires a matching independently annotated Validation Pack.
- `public_summary.json` is rebuilt from fixed anonymous fields only. Only that
  summary and this procedure belong in Git. No paths, original filenames, account
  names, audio, images, detailed PTS, source hashes or raw exposure rows are public.
  An aggregate inventory/allocation SHA is an integrity anchor, not a source hash.

## New nine-recording development-only batch (opt-in)

For the user's newly acquired nine recordings, **do not use the legacy
5/2/2 invocation**. After mounting the nine private original files and
selecting a new batch ID in the authoritative external registry, execute:

```sh
python -m scripts.diagnostics.register_private_sources register \
  --source-dir "$NEW_RECORDINGS_DIR" --registry "$PRIVATE_REGISTRY" \
  --batch-id new_development_batch --allocation-mode development-all
```

Omit both attestation flags unless independently and explicitly confirmed;
`--user-confirmed-unused-and-distinct` is **rejected** in development-all
mode because it must not serve as a future holdout claim. Do not assert
unedited, unused, different-match, continuous-play or unexposed status on
the basis of the user's statement that nine files have been acquired.

The new explicit allocation rule
`source_sha256_lexical_development_all_before_content` freezes nine
`DEVELOPMENT` slots, zero `QUALIFICATION_CANDIDATE`, and zero
`FINAL_HOLDOUT_CANDIDATE` before decoding or probing. Exposure is
`UNKNOWN_EXPOSURE` for **all nine** until actual prior/current usage is
documented. Assignment to DEVELOPMENT is a reservation, **not** proof
that training, prediction review or annotation already occurred.
`physical_match_verification=unverified` marks the provisional IDs;
a unique SHA or candidate ID does not prove distinct physical matches
when the video was cropped or re-encoded.

A private, exclusively created `exposure_history.json` freezes one
development-reservation event per video with prior exposure marked
`not_verified`. The journal SHA-256 is bound into both private allocation
and final manifest. `verify` checks the journal, all nine frozen events,
source/copy hashes, and intake hashes. This initial event is **not** a
fabricated complete historical Exposure log: any earlier use must be
reviewed, and all later human views, GT, tuning, prediction reads and
opening decisions must be chronologically logged in the existing private
Temporal GT Exposure journal.

The legacy default remains unchanged: `--allocation-mode legacy-5-2-2`
(or omission) preserves the previous 5 DEVELOPMENT / 2 qualification
candidate / 2 final candidate reservations and previous manifest rule.
Existing frozen assignments, protected recordings, and `match_001` /
`match_002` are never reclassified.

For a non-mutating, anonymous check of an already frozen batch, use:

```sh
python -m scripts.diagnostics.register_private_sources inspect-existing \
  --batch "$PRIVATE_REGISTRY/new_development_batch"
```

This reads the private allocation, final manifest if present, and frozen
initial exposure journal. It does **not** read original or managed video
bytes, expose paths or source hashes, or treat locally computed anchors as
external trust. An incomplete registration reports
`state=incomplete_manual_review`; accepted/rejected totals are not
fabricated. Follow up with `verify` and separately trusted SHA anchors
before claiming end-to-end source integrity.

If nine files were already registered, **do not run a second registration
to repair the allocation**. The CLI refuses case-insensitive batch ID reuse,
and identical prior source hashes are refused even under a different name.
Read the existing private allocation, manifest, prior exposure records
and externally stored trusted SHA anchors; report a conflict and preserve
the frozen data and partial results. Differences in SHA do **not** rule
out alternate encodes or excerpts of the same physical match: those need
manual, private provenance review. No protected seven-video group is
accessed by this procedure.

Actual verification requires the source files and the user's external,
private registry. GitHub code/CI have no access to those local bytes;
a report must therefore distinguish *unreceived* source files from
rejected files. Never pretend that counts, file sizes, hashes, decode
checks, match independence, or backup were verified from GitHub alone.

Backup status must remain `pending_operator_action` until an independent
encrypted copy (separate failure domain) and a restoration/hash test
are confirmed. Neither the private managed videos nor the private journal,
source SHA, PTS, screenshots or personal paths may be committed or
uploaded to Git LFS. This source-only operation performs no training,
recognition, E2E qualification, or production accuracy assessment.

For future independent evaluation, accept **other newly captured videos**
only after freezing recognizer implementation, Profile, reference assets,
evaluation policy, and intended acquisition rules. Allocate independent
material **before** viewing its contents or predictions; never return
these nine development sources to an independent qualification/final
holdout. Do not claim generalization until genuinely new blind evidence
passes the independent criteria.

## Intake

Run from a checkout with the existing Python 3.12 development dependencies and
FFmpeg/ffprobe. The registry must be outside Git checkouts. Real recordings are
never downloaded in CI and no LFS command is invoked.

```sh
python -m scripts.diagnostics.register_private_sources register \
  --source-dir "$RECORDING_DIR" --registry "$PRIVATE_REGISTRY" \
  --batch-id personal_batch \
  --user-confirmed-unedited --user-confirmed-unused-and-distinct
```

Use declaration flags only after explicit confirmation. The second flag means
all nine physical matches are distinct from each other and the existing sources,
and have no previous development, prediction/result review or annotation use.
If that cannot be confirmed, omit it: all sources retain `UNKNOWN_EXPOSURE`,
including reserved evaluation candidates. A user attestation is provenance;
metadata and SHA matching cannot independently establish semantic independence.

Before inspecting metadata or decoding, the tool hashes all sources and compares
against the two existing E2E manifests and every allocation in this registry,
including failed/interrupted reservations. Duplicate bytes or IDs reject the
batch; differently encoded clips of the same match require honest user/history
identification and must never be admitted under separate physical-match IDs.
Nine files must be present. Unexpected files and symlinks reject intake.

Unique batch-prefixed IDs avoid renumbering existing matches. In **legacy**
mode, lexically sorted SHA order fixes five DEVELOPMENT, two
QUALIFICATION_CANDIDATE and two FINAL_HOLDOUT_CANDIDATE reservations.
Explicit development-all mode instead freezes nine DEVELOPMENT sources. The order uses no visual content, outcome,
recognizer output or success filtering. It is deterministic, not a claim of
population-random sampling. Failed files keep their reservation; no replacements
are selected. A per-registry exclusive directory lock prevents concurrent writes.
An interrupted run retains its allocation and partial results; inspect it before
recovering a stale lock. Never delete reservations to make an exposed file fresh.
Use this one authoritative registry for future batches; separate registries do
not coordinate uniqueness.

The existing `intake_recording.inspect_recording` supplies size, SHA before/after
probe, duration, raster size, FPS, codec, all audio tracks and packet PTS summary.
It now retains exact rational native timebase/frame rate and the first native
integer packet PTS. Sorted presentation gaps are container diagnostics. They do
not prove visual continuity, an absence of cuts, or an unedited full match.
Explicit user confirmation is stored separately. No new recognizer runs here.

FFmpeg decodes the full video and all audio to a null sink with error rejection,
a six-hour per-source limit and two video decoder threads. No images, waveform,
transcript, recognition output or human preview are produced. Probe errors,
invalid metadata, failed copy/source SHA or decode errors quarantine the source.
A successful decode only means this decoder encountered no reported errors;
semantic completeness, dropped events and continuous play still need review.

The registry/batch directories use mode 0700, JSON mode 0600, managed video mode
0400 on POSIX. These permissions limit accidental access/writes, not the owner's
ability to change them. On Windows apply an owner-only NTFS ACL to the registry;
Python chmod alone does not provide that ACL. Do not enable cloud sync or share
this registry without a separate privacy decision. Original permissions are not
changed by intake.

## Reverification and backup

Keep the final inventory and allocation SHA anchors separately from the private
registry, using the approved public aggregate report or an independent trusted
record. Recheck the complete original and managed copies plus intake report bytes:

```sh
python -m scripts.diagnostics.register_private_sources verify \
  --batch "$PRIVATE_REGISTRY/personal_batch" \
  --trusted-manifest-sha256 "$TRUSTED_MANIFEST_SHA256" \
  --trusted-allocation-sha256 "$TRUSTED_ALLOCATION_SHA256"
```

For a metadata/decoder recheck, run the existing source-only intake CLI against
the managed copy into a **new private output**, compare its SHA, duration, rational
timebase, FPS, codec and audio with the retained intake, and repeat the null-sink
decode. Never rewrite the frozen allocation or a prior intake. Later annotation
uses actual source ticks and a real acquisition epoch; packet PTS seconds are not
substituted for exact frame witnesses.

Both original and managed copies are retained and hash-checked. Copies on the
same volume are **not a disaster-recovery backup**. An operator must copy the
private batch, originals and trusted anchors to a separate encrypted disk or
approved nonpublic storage, verify every copied file with SHA-256, restrict access,
and test restoring a copy before calling backup complete. The manifest explicitly
leaves a separate-failure-domain backup pending. No external upload is automatic.

## Exposure and evaluation opening

For confirmed unused sources, the development reservation is DEVELOPMENT and
four evaluation reservations are PROSPECTIVE_HELD_OUT candidates. This is not
recognizer qualification. Existing historical sources remain exposed; matching
new recordings cannot reset that exposure. The retained prior-inventory and
Temporal GT contract anchors link this intake to the existing exposure baseline.

Metadata/hash/null-sink decoding is recorded as machine integrity work, without
visual review or predictions. Future actual source viewing, GT creation, tuning,
prediction and result opening must be appended in chronological order to the
private Temporal GT exposure journal using its existing exposure types. Opening
source for annotation differs from opening predictions. Never label a developer's
viewed source as whole-model blind merely because predictions were not opened.
Freeze the method/profile/assets/code, source/contract hashes, allocation and
opening authorization before independent qualification or final evaluation. Do
not use evaluation material to tune, backdate opening, or reallocate consumed
holdout. Different clips of one match and duplicate physical events stay in one
split. `UNKNOWN_EXPOSURE` never establishes independent qualification.

## Next human review, without automatic GT

Use `docs/temporal_gt/annotation_contract_v1.md`, its existing schema, and
`scripts/temporal_gt/validate_dataset.py` for Round annotations/freezes. Reuse
PR55 `scripts/e2e/preflight_round_source.py`, bounded source acquisition and
`scripts/diagnostics/assemble_source_review_plan.py` for candidate preparation.
The plan is explicitly NOT GT. Do not run the overview extractor on evaluation
reservations as a development exploration. Source curation must follow a frozen
acquisition budget and be independent of prediction selection.

| Task | Source evidence requiring human confirmation |
| --- | --- |
| Round lifecycle | Actual active Start, observable End evidence, next Round transition and continuity in the same real segment |
| Score / clock / caption | Readable before/after score witnesses; clock type/literal changes; last partial and first complete caption; uncertainty retained |
| Natural controls | Reviewed countdown, score-only/clock-only, Spike/decimal, partial/stale caption, buy/menu, spectator, repeated raster, gaps and source discontinuity |
| Self Death | Explicit Self Victim versus Nonself Victim, Self Killer, killfeed Killer/Victim and ownership; never infer identity from a spectator target |
| Combat Report | First appearance separately from persistence, occlusion and redisplay; Report presence alone cannot certify death |
| Death timing/context | Last confirmed alive / first confirmed dead native onset bracket, Spectator, Respawn and source breaks; do not substitute candidate acceptance time |

Each future label must bind original SHA, integer native ticks plus rational
timebase and acquisition epoch, encoded/pixel hashes of actual evidence frames,
physical event identity, reviewer, chronology and uncertainty. Human review must
not consult candidate predictions when deciding source truth. Reader outputs and
AI transcriptions remain unconfirmed candidates until independently reviewed.
No interpolation, midpoint truth, absent-witness fabrication or unannotated
negative intervals are permitted. Existing Round GT stays unchanged. Self Death
needs a separately reviewed compatible annotation contract before formal labels;
this inventory introduces no Death GT schema or production acceptance.

Completing all nine manual annotations is not an intake requirement. Intake
success, E2E registration, temporal readiness, independent qualification and
production adoption are separate gates.

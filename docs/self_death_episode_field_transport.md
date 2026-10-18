# Self Death episode field transport

Status: implemented candidate-field association, with exposed source-backed
regression measurement. **No independent qualification, formal Death release,
canonical PASS increase or Goal completion is claimed.**

Work started at `53a95c95aea267197f51b9c415f2d78e8ac31c5d` on
`codex/self-death-positive-recognition`. Fetch confirmed main at
`7e480c2f2f7f49aea73e1541d065d78881d2f11c`. This extends PR #53's experimental
session; it does not modify the separate Round-boundary work or merge main.

## Problem and actual evidence

An image prediction has an original onset and a later confirmation. The R2
confirmation frame lacks an accepted victim name, although preceding native
frames inside the same episode have accepted readings. The separate existing
Report reader also supplies damage and portrait candidates at one of those
physical frames. Requiring every attribute at confirmation would discard actual
evidence; copying earlier values into the confirmation frame would invent its
observations and provenance.

The prior session returned only the latest image reading and an optional formal
Event. It did not return an episode-associated collection of these observations.
The new collector fills that transport gap without interpreting a portrait class
as a killer or certifying the experimental subject recognizer.

## Implemented contract

`DeathEpisodeFieldCollector` retains a bounded native-frame history. At an
existing image prediction, it associates only original observations between its
onset and confirmation. Each contributing frame needs its own accepted marker,
victim separator and Report evidence. A missing name stays absent at that frame.
Both weapon and ability measurements retain their original methods; absent
legacy plate measurements are not invented. The collector does not assign a
numeric score to the geometry-only role method.

Report fields use the existing HUD candidate validator, including its field
confidence floor and provenance requirements. Different image and Report
producers may have different fingerprints, but video SHA, native PTS, time base,
source segment and pixel SHA must match exactly at the field's frame. Both
producer bindings survive. A producer change midway through an episode cannot
inherit the earlier producer's fields.

Each `EpisodeField` retains the original value/display, field confidence, pixel
ROI, methods, source binding and original current-image witness. Association
support is a separate conservative minimum; field confidence is not overwritten
by that support. Conflicting accepted values suppress the whole conflicting
field. There is no highest-score vote, name correction, default numeric value,
GT lookup or later-frame backfill.

Source breaks, non-native adjacency, repeated pixels and mismatched physical
bindings poison the collector until explicit qualified rearm. Candidate fields
remain separate from the Event: no public HUD, Event, Package, Fact or SQLite
schema changes. The existing release consumer does not read these fields.
Its implementation fingerprint includes the new session dependency, so a prior
release certificate cannot silently authorize changed orchestration.

`NumericDeathImageSession` now accepts an optional Report provider and returns
`episode_fields` separately from `event`. The provider runs the existing reader
on the actual frame and supplies its original producer binding. No provider or
qualification is installed in the application. Names can still be retained from
the image reader without a Report provider. A missing release qualification
does not erase candidate observations and does not enable an Event.

## Source-backed replay

The recognizer, assets and OCR code were unchanged. Reuse therefore operates on
their archived outputs, with their original fingerprints, rather than declaring
them newly recognized under the transport code. The portable diagnostic verifies
the original input, profile/asset, reader-source and dependency-file hashes,
native cache encoded hashes and actual decoded pixel hashes. It checks terminal
hashes again. It does not rehash/decode the entire video or claim new semantic
continuity qualification.

171 native frames in five already exposed windows were replayed. R1 appears in
two overlapping diagnostic windows: those are two views of **one** episode,
not two independently detected deaths. Original onset/confirmation PTS remain
unchanged. No new frame, template, threshold or video transfer was needed.

| Candidate episode field observations | Previous session | Current session | Delta |
| --- | ---: | ---: | ---: |
| R1 long window: victim-name observations retained | 0 | 4 | +4 |
| R1 long window: damage / portrait observations retained | 0 / 0 | 1 / 1 | +1 / +1 |
| R2: victim-name observations retained | 0 | 3 | +3 |
| R2: damage / portrait observations retained | 0 / 0 | 2 / 2 | +2 / +2 |
| Persistent-Report / spectator control episodes | 0 / 0 | 0 / 0 | 0 / 0 |
| Formal real-source Death events | 0 | 0 | 0 |

The first R2 name/Report association uses original tick 2269225; confirmation
remains tick 2269993. These are original 1/15360-second PTS coordinates, not
timestamps derived from GT or rounded to an acceptance window. The name is
absent at confirmation and is still absent in that frame's image reading.

The short R1 window retains four name observations but does not borrow the
Report measurements acquired under the long window's different source epoch.
The longer native window has the original matching Report bindings. Identical
pixels are insufficient permission to overwrite a component's source epoch.

Visual review of the actual R1 confirmation and the R2 first-name frame found
the observed name, portrait class and damage displays consistent with the
retained values. This is a review of exposed development frames, not a blind
holdout, an independent false-positive estimate or killer-role qualification.
The raw names, images, values and profiles remain private.

## Tests and reproduction

156 related unit tests passed in 61.88 seconds. Tests cover names absent at
confirmation, separate producer fingerprints, original ROI/PTS retention,
conflicting names/damage, source/segment/pixel/time-base mismatch, mid-episode
producer changes, cadence gaps, duplicates, discontinuities, current-frame
role/Report/marker failures, invalid confidence, pre-onset and post-confirmation
exclusion, persistent Report, and session operation without qualification.
Existing numeric-release, session, image-recognition and witness tests pass.
These are synthetic contract checks and are not real recognition qualification.

Ruff passed for `src tests scripts/e2e` and the new diagnostic. Mypy passed for
the 146 source/diagnostic files checked. Linux/Windows CI for
this change is pending push; previous CI at `6eafb85` belongs to earlier code.

Run the low-cost replay with original private artifacts:

```bash
PYTHONPATH=src python scripts/diagnostics/replay_death_episode_fields.py \
  --image-replay IMAGE_REPLAY.json \
  --report-replay REPORT_FIELDS_REPLAY.json \
  --cache-manifest VERIFIED_NATIVE_CACHE.json \
  --image-plan ORIGINAL_IMAGE_CODE_HASH_PLAN.json \
  --output PRIVATE_NEW_OUTPUT.json
```

The first measurement, `episode-field-association-replay-v1.json`, took 51.173
seconds including cache/artifact verification. Final
`episode-field-association-replay-v3.json` took 37.743 seconds, with 0.087 seconds
in the association itself, and produced 175,004 bytes. It uses streaming file
hashing and retained exactly the same episode results as v2. The observed process
peak remains 613,060,608 bytes in both v2 and v3; no peak-memory reduction is
claimed. Timing is a single-run observation, not a controlled speed benchmark.
These are not new Full E2E results, and the output contains private observations.

## Remaining work and baseline separation

Adopted Full remains 23/55/4. Archived unadopted Strict remains 28/50/4. The
separate timing-policy comparison remains 30/49/3. Current canonical targeted,
sampled and Full are **not measured**; no new PASS is attributed to transport.
Full was not run because formal recognizer qualification/release is still
incomplete and repeating recognition would not test this transport change.

The next implementation must bind the Report's semantic subject/row and killer
role to the episode using actual image evidence, then connect only independently
qualified attributes to formal release. Presence of the Report, a portrait or
damage alone remains insufficient, including the persistent-Report controls.
Source-2's unsupported damage and portrait class remain absent under the
unchanged reader. No fields are fabricated to complete either episode.

Additional video transfer is unavailable because of device capacity. It is not
a prerequisite for all remaining implementation. Work proceeds using the local
sources and existing cache, while exposure history and independent qualification
limitations remain explicit. This transport milestone is not completion of the
Self Death recognizer or the Strict FAIL-reduction Goal.

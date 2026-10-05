# Fixed regression replay

## Contract

Lane A executes frozen source-frame populations through the production service
factory, `HudVideoProcessor.process_frames`, `RealHudAnalyzer.observe_frames`, and
the existing Visual / Map / fusion / package stages. Lane B retains production
adaptive Pass A / Pass B / micro sampling. No thresholds, identity gates,
classifier decisions, ownership rules or temporal decisions change here.

Two versioned sets are kept separately:

* **canonical uniform**: nearest native display PTS to exact rational 6 Hz targets
  starting at the first presentation timestamp; equal-distance ties choose the
  earlier frame. Selection receives native metadata only, never a detector result,
  classifier state, GT, expected event or assertion failure.
* **frozen production coverage**: every observation locator from clean analyzer
  `f291ded6140a802aec9098c22ea96ef6d7b29e2a`, run population 4,038. The population is
  coverage, not truth. The full set is frozen once; a new version must preserve
  previous versions rather than select a better-looking subset.

Manifest v1 contains source SHA-256, stream index, reduced native time base,
integer PTS, display-order source-frame ordinal and decoded BGR pixel SHA-256.
Coverage also binds the clean analyzer commit and run artifact hash. No local
paths, GT labels, expected state, detector values, raw images or private assets
are allowed. Native metadata is checked against the actual source before replay.
Exclusive creation prevents silent overwrite. Validation rejects source drift,
duplicates, unordered populations, unknown fields and decoded-input drift.

## Execution and comparison

`scripts/fixed_replay_manifest.py` generates native-metadata manifests. Coverage
requires an explicit complete frozen locator list. `scripts/fixed_regression_replay.py`
seals pixel hashes and runs the same production services with remote semantics
disabled, matching the clean mock-AI E2E contract. Private directories hold all
extracted images and per-frame replay JSON. Shared JSON reports contain only
aggregates, manifest/source/profile fingerprints and provenance.

The passive HUD sink receives deep copies of actual augmented signals, current
accepted reader values, geometry validity, classified state and live identity
reason before ownership clearing. Sink mutation cannot alter the detector. The
normal disabled sink retains no trace. Structural presence and accepted scores
are recorded from runtime; a rejected template whose raw score is not exposed by
the current runtime is reported as null, never an invented zero. The 0.90 value
in the snapshot is the unchanged identity-gate floor. ROI confidence remains
separate from identity scores and value-reader provenance.

Replay snapshots record published and pre-ownership accepted reader values,
HP/Ability/Weapon gates, checked Spectator exclusion, Report/Buy/Map/Remote
signals, ownership, world trust, actual Visual eligibility and actual Map marker
and zone results. Previous snapshots are observations, not correctness labels.

`scripts/compare_regression_replays.py BASELINE CURRENT --lane fixed --output SUMMARY`
requires identical source, manifest and frame keys. It reports unchanged,
known-state to UNKNOWN, UNKNOWN to known-state, class transitions, confidence-only
changes, reader gains/losses/changes, ownership/world changes and reason
transitions. Zero and false are concrete values; null/absent reader outputs are
unavailable. Interpretation defaults to unresolved and requires explicit evidence.

The adaptive lane allows population differences and separately reports common,
removed and added frames. Only common frames support a paired behavior claim.
Value gains/losses in removed/added populations are sampling effects, not proof of
reader improvement/regression. Downstream published fact records should additionally
be matched by semantic content, excluding generated identifiers, as in the Remote
checkpoint review; per-frame value counters alone do not establish final fact counts.

## Verification and ongoing workflow

Unit tests cover deterministic selection, exact rational ties, strict source and
manifest validation, immutable writes, path-free aggregate output, comparison
accounting and drift rejection. Integration tests compare the shared production
postprocessing paths on identical frames and prove the fixed path never extracts
or adapts. Actual analyzer tests prove trace/no-trace observations and events agree
and a mutating diagnostic consumer cannot affect production evidence.

Real-source population binding and repeat-replay measurements are recorded in a
separate aggregate evidence update after execution; implementation tests alone do
not establish full-video replay stability.

For future production changes: targeted checks, full pytest/Ruff/mypy/diff checks,
Lane A replay and paired comparison, production commit, clean Lane B E2E,
adaptive population comparison, then a separate report-only commit. Clean E2E
requires empty `git status --porcelain` and `git_is_dirty=false`. Diagnostic-only
changes do not require a new adaptive E2E; production-path refactors still require
parity evidence. No detector changes are adopted to improve a comparison number.

The preceding Remote phase remains `NEED MORE EVIDENCE` for positive Remote UI
recognition. Its qualified UNKNOWN safety correction is shared; generic HOG and
palette do not establish independent geometry. This infrastructure is the next
priority requested by the user, before any Buy production change.
## Initial frozen input evidence

Source SHA-256: `71d58558559d6f578433ce9f234bf176f76fd5a86657dbfe3eba1e7d36136b06`.
Native stream 0 has 10,259 display-order frames and time base 1/15360. Integer
best-effort timestamps agree with the actual VideoService presentation-time table.
All 4,038 coverage observations bind uniquely to native source frames; re-extraction
with production native-resolution JPEG quality 92 matches every original JPEG
byte-for-byte and every decoded BGR pixel hash. Unresolved bindings: 0.

| Set | Count | Manifest SHA-256 |
| --- | ---: | --- |
| canonical uniform 6 Hz v1 | 1,026 | `f8267c437f95cb534c06d80a459961409323688f9b7a76a728b719b0350e74f1` |
| frozen production f291 v1 | 4,038 | `e90453cd5ab962101c350ec734ea7a5434b4f368fc1b15ac9cceb72f86edcd8e` |

Manifests are in `config/fixed_replay/`. The native-table private artifact hash is
`8dee2dda9274908ed3965c2fe1e8beaea8bb9927fae6f53f0a7cd0e6c5948abc`;
the exact coverage image-binding artifact hash is
`a4ca3c1aa8a9ca3ef00a6e221bf73aa66e63a9e60a51ff2acb053328475f7ad1`.
Those artifacts contain private paths and are not committed.

Implementation verification: **905 passed, 2 skipped** in the full test suite;
Ruff across src/tests/scripts, mypy across 86 source files, and diff checks pass.
The two skips are the existing optional trace-pack and real-recording-anchor tests;
no skipped test is claimed as accuracy validation. Four adapter tests were rerun
after the final script-only published-value filtering adjustment and passed.
Repeat full-video replay output measurements are pending execution at this checkpoint.

## Adapter correction before output baseline freezing

The first output-baseline attempt was aborted before publication because schema
review found that Remote subtype resides under `view_context`, not the root HUD
observation. The adapter now reads that actual field. Structural score availability
is named `score_exposed`; it is not an observability verdict. A null rejected score
must never imply unobservable structure. Detector outputs and source-frame manifests
were not changed. Eleven focused adapter/comparison tests passed after correction.

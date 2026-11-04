# Automatic DEVELOPMENT match timelines

This Draft extends #115–#120. `temporal.game.DevelopmentGameTimeline` remains
the only Round/life/camera state owner. The automatic route is an experiment;
it is not adopted in Production and does not replace the archived comparison.
The tracking issue is [#121](https://github.com/shark-man0/eval_valorant_perspective/issues/121).
Measured results and remaining regressions are recorded in
[the development comparison](development_full_match_comparison.md).

## One pixel observer, multiple registered matches

`temporal.match.run_match` verifies the existing registry/allocation and explicit
DEVELOPMENT allowlist before opening a video. It never discovers arbitrary
videos. Match IDs and hashes bind provenance and physical-match partitions;
they are not provided to `ProfileHudObserver.inspect(image)`. The observer does
not receive native time, previous state, labels, a recorder roster or an initial
state. Use exactly the same reader configuration for every comparison match.

The private reader configuration contains `layout` and `profile` paths. Optional
`structural_bank` and `result_method` paths opt into the same existing offline
Round component gates used by the bounded supplier replay. Source-conditioned
reader settings and human initialization are rejected. Asset training provenance
may be retained as metadata. A shared configuration does not imply unseen
generalization: its calibration/training exposure must still be reported.

Whole-HUD calibration and component-specific Round support remain separate.
The opt-in Round scope measures all three fixed top-HUD tiles at the existing
0.90 threshold, with no alignment, expected score or Source/time lookup. It
cannot authorize recorder identity, full HUD geometry or ownership. The
historical unsupported Score foreground name is replaced only in the private
runtime configuration by the explicit `white200_rowcontrast_v1` mode already
used by the older diagnostic CLI. Parent Profile bytes and class thresholds
remain unchanged. The raw digits, geometry rejection, identity rejection and
OCR text are retained even when the shared state is UNKNOWN.

The additional boolean `clock_prefix` (default `false`) opts into independent
clock components. It retains the original timer segmentation, all ten classes,
0.90 acceptance and 0.04 competitor margin. An independently accepted minute
of at least one can support the existing ACTIVE clock-range rule when the
complete clock is unread, current Round geometry is supported, and neither
BUY nor Result is observed. Confident invalid seconds syntax rejects this
support. The full numeric clock remains unknown; missing seconds and exact
event times are never supplied. Raw per-digit alternatives and acceptance
are retained, and the option/module are bound to the observer fingerprint.
The original full timer reader and Production qualification stay unchanged.

Two helper changes are selectively reused from the pinned earlier HUD supplier:
`hud_scope_structure.py` and the compatible `EdgeReference` addition to
`geometry_edge_similarity.py`. They contain pixel structure measurement and
reference precomputation; they do not add another lifecycle state machine.
No supplier branch is merged wholesale. Every asset, Profile, observer module,
OCR binary/model and native decoder binary is fingerprinted in private outputs.

## Acquisition and adaptive refinement

`run_match(..., observer_factory=...)` also accepts a development `PixelObserver`
factory. It receives the reader configuration path, and `inspect(image)` receives
only native BGR pixels. A factory's deterministic fingerprint/bindings are
rechecked after processing; changed observer, engine, decoder or Source bytes
prevent a completion receipt. Native pixel identity is captured before a
supplier's in-place preprocessing. Factories remain responsible for binding
their actual code, assets and model weights.

A composite returns `supplier_observations`, each with its own
`producer_fingerprint`, `signals`, `context`, `raw` and optional `map_candidates`.
Declare their fingerprints in `bindings.supplier_producer_fingerprints`.
Suppliers cannot replace native sample identity or continuity, and duplicates
are rejected. The top-level signal summary drives adaptive sampling only;
it is not counted as another observation. The single shared engine receives
each supplier claim once at the verified native sample.

Optional `bindings.baseline_producer_fingerprints` writes a separate
`baseline_timeline_PRIVATE.json` from exactly those suppliers at the same native
points. A missing declared baseline supplier is an error. This compares methods
using one state definition; it does not create HUD/Map lifecycle implementations.

The CLI streams native PNGs through a bounded frame buffer and verifies each
selected PNG's correspondence with FFmpeg's integer native PTS. It normally
observes about once per second. Changes in measured display signals, score,
timer jump, camera cues or marker availability request additional observations
at a 0.2-second cadence. Refinement defaults to at most 40 merged windows and
240 seconds per match. Deferred windows are explicitly counted. Selection is
chronological and budget-limited; it is not exhaustive boundary recall.

The beginning/end are obtained from the native stream, including a nonzero PTS
origin. Native seconds remain in the rich timeline. The CSV uses recording
seconds relative to that origin. An unobserved bin stays UNKNOWN. A measured
frame with unread HUD, an inferred state and a video observation gap are
different records. Sampling is not continuous semantic exposure. Normal PTS or
duplicate images do not prove gameplay continuity. All decoded native-frame PTS
are **not** audited by this sparse transport; the selected points are audited.

The Source is hashed before and after processing. Nonzero decoder exit,
truncated/oversized PNG framing, geometry/PTS mismatch or changed source bytes
prevent a completion receipt. A failed/partial directory is retained without a
success marker. A pilot is explicitly partial; it cannot report full-match
completion. PNG retention is optional and off for whole-match runs.

Pilot end time is exclusive, including native timestamps and the recording-second
CSV grid. The CSV also retains per-domain hypotheses/uncertainty and an explicit
development-only qualification column; the rich JSON keeps original evidence.

Run from the development checkout (the optional diagnostic helpers require the
checkout's `scripts` package):

```sh
PYTHONPATH=.:src python -m valorant_ai_coach.temporal.match \
  --policy /ABSOLUTE/PRIVATE/policy.json \
  --source-id REGISTERED_DEVELOPMENT_ID \
  --reader-config /ABSOLUTE/PRIVATE/shared_reader.json \
  --output /ABSOLUTE/NEW/PRIVATE/match_run
```

Use `--pilot-seconds 60 --max-refinement-windows 1 --retain-frames` for a bounded
prefix transport check before a long run. Outputs include original observations,
native and one-second state views, CSV, decoder logs and a hash-bound completion
receipt. The elapsed time includes intake hashing, decoding, observer execution
and state rebuilding. Reported peak RSS is Python's peak only; it is not total
simultaneous Python/FFmpeg/OCR memory.

`--audit-sample-plan /ABSOLUTE/PRIVATE/native_audit.json` optionally adds frozen
exact native comparison points. The strict `development_native_audit_v1` plan
contains only `schema` and `samples`; each sample contains only the existing
native identity fields. Labels/initialization are rejected. Every referenced
Source must pass the allowlist, and target stream timebase/size/PTS/pixels must
match. Other admitted Sources are ignored for this run; references beyond a
pilot limit are deferred explicitly. The observer never receives the plan.

Audit points already sampled are checked without an extra observation. Missing
points are decoded with bounded balanced PTS filters. The alias ledger retains
original and new acquisition epochs and marks exact pixels as **not independent
confirmation**. Missing/changed points fail rather than invent a GT counterpart.
Audit metadata selects evaluation acquisition only, not recognition conditions,
event time or initial state. The plan hash is frozen for the run.

## Same-observation temporal controls

```sh
PYTHONPATH=.:src python -m valorant_ai_coach.temporal.compare_modes \
  --policy /ABSOLUTE/PRIVATE/policy.json \
  --input /ABSOLUTE/PRIVATE/match_run/observations_PRIVATE.json \
  --review /ABSOLUTE/PRIVATE/exact_display_reviews.json \
  --output /ABSOLUTE/NEW/PRIVATE/mode_comparison
```

The input may also be a pre-existing shared timeline with its original
`observations` collection. All three predictions are saved before review labels
are read. Duplicate reviews cannot multiply denominators; contradictory answers
are rejected. Unavailable/UNKNOWN points stay outside scored denominators.

- `legacy_offline`: the previous default with bounded future confirmation.
- `forward`: disable later-frame Score/Result confirmation, future DOWNED
  evidence for elimination hypotheses, and backward filling.
- `offline_transition_brackets`: retain an unread carried Round estimate as
  competing before/after states within a measured transition bracket. Save its
  original forward estimate; do not choose an event time or overwrite a direct
  state observation. Life/camera estimates and transition candidates are retained.

The defaults of the existing engine are unchanged. The known carried-BUY error
can become an abstention with BUY/ACTIVE alternatives. That is more explicit
uncertainty, not an additional correct recognition. Report correctness,
abstention, boundary width and losses separately.

## Evaluation and current limitations

Research view observations can set `context.unqualified_view_model = true`.
The shared engine retains ALIVE/UNKNOWN and SELF/REMOTE/UNKNOWN alternatives
for such owner claims, including during carry/reconciliation. They cannot
sponsor current Map owner evidence or recorder correspondence. A stronger
independent current owner observation retains its existing behavior. The flag
does not relax `hud.identity`, authorize Production ownership, or add a second
lifecycle state machine.

A weak `recorder_elimination_display` observation additionally needs
`context.elimination_display_signature`, a SHA256 of independently read display
attributes, to support a fresh elimination hypothesis. Omit the field when
unread; `None` and malformed values are rejected. The engine remembers observed
signatures across Round changes and unread gaps, including displays first seen
while SELF. A repeated signature cannot by itself create another death candidate.
Source/epoch changes or confirmed breaks reinitialize that history. Existing
owned-alive, Round and spectator conditions still apply; a hash alone never
establishes death. This is display identity, **not physical-event identity**:
different deaths with identical cards may remain unresolved. Legacy suppliers
without the research flag retain their old unqualified behavior.

Freeze physical matches, Profile assets and A/B/C/D conditions before tuning.
Known development cross-validation is not untouched final evaluation. New
recordings require predeclared use/split and independent physical-match IDs;
reject overlap between fitting and evaluation. Do not move old comparison-only
labels into fitting. Learning proxies and candidate growth do not establish
recognition improvement, and rejected models remain rejected.

Exact labels can score only their exact points. No unlabeled event window is a
negative. Event recall, false events, internal boundary error and Map-role
accuracy remain null when their independent labels/readers are unavailable.
Report each match, macro/micro results with denominators, the worst labeled
match, the recording duration, observed/inferred/UNKNOWN bins, previous correct
losses, and performance scope. Never label a match with no reviews the best or
worst by an invented zero accuracy.

The generic observer currently lacks a source-independent recorder identity
bootstrap. The old four confirmed Map-role outputs remain abstentions in the
shared path; their raw marker pools are retained in the archived route. The
automatic full-video observer's Map reader is UNCONFIGURED, not an observation
of no markers. Generic full-recording life/death/spectator/return recognition and full Match
Map/Zone integration remain required work. Round-number candidates are not yet
provided by this first automatic route. No qualified Fact/Event is produced.

Keep protected recordings, canonical GT, fixed evaluation windows, schemas and
Production gates unchanged. All resulting PRs remain Draft; main merging and
HUD/Map task redistribution require separate coordination approval.

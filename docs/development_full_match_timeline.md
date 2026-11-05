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

## Round-number candidates

HUD and Map consume `frames[].round_number` and `seconds[].round_number` from
the same shared engine. The additive `development_round_number_v1` contract
contains a nullable numeric `value`, competing integer `candidates`, status,
reason, uncertainty, evidence IDs and `unknown_possible=true`. Native estimates
also retain the original displayed scores, producer and exact original samples,
including another acquisition's exact-pixel provenance. No qualified number
Fact or internal event time is issued.

A single valid current score pair plus a direct current BUY/ACTIVE observation
supports score sum + 1 as an unqualified candidate. A carried or future-filled
phase cannot select the number. ENDED/INTERMISSION/UNKNOWN, competing phases
or score conflicts keep score sum / sum + 1 alternatives, excluding zero.
Even one remaining alternative does not resolve an unknown phase. Opposite
score pairs with the same sum still conflict. Invalid scores are retained as
ineligible observations. Missing scores never reuse a previous score or count
Round-start candidates; Source/epoch changes need no number initialization.

One-second aggregation preserves unknown native samples and parallel acquisition
uncertainty. A known number at one sampled instant cannot resolve another unread
instant in that bin. Missing bins have no number candidates. The full CLI appends
`round_number`, `round_number_candidates` and `round_number_uncertainty` to its
existing CSV columns; precise score evidence stays in rich JSON. Synthetic
nonzero-PTS codec tests verify the numeric and UNKNOWN CSV paths. Candidate
coverage is not number accuracy; independent display/number review is separate.

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
Native composite archives replay each original supplier envelope, using the same
transport adapter as `run_match`. The adaptive-sampling summary is not another
state observation and cannot replace a supplier's spectator/owner claim.

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

Research Round-shape observations can set `context.unqualified_round_model=true`.
This permits only an `active` display claim or no signal, with no score/timer
context or Map candidates. The original ledger retains each claim and native
sample. Before lifecycle inference these rows are removed from the entire Rule
evidence graph, including future-result helpers. They cannot advance Round
tokens, death/return context or Map ownership.

After the Rule/reconciliation pass, a current weak ACTIVE claim can project an
otherwise unobserved UNKNOWN Round into an ACTIVE/UNKNOWN candidate. Existing
estimates and conflicts remain intact. Frames retain `round_model_hypotheses`
and the original `rule_estimate`; `round_model_projection_history` records
before/after estimates and precise samples. This is an estimate revision, not
a Round-start or spike event. Weak claims are not carried/backfilled and cannot
select a Round number from a score. A one-second view remains UNKNOWN when its
sampled estimates conflict. Untagged frozen outputs remain unchanged.

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

The default generic observer lacks a source-independent recorder identity
bootstrap. An optional private image-only composite now completes full recordings
through the same API and improves the fixed reviewed life/camera points; its
unqualified weights, full-match safety and unseen generalization remain unadopted.
The old four confirmed Map-role outputs remain abstentions. An exact archived
Map-supplier replay retains pools at 22 matching native points in the new full
timeline; unmatched points and acquisition lanes are not interpolated or collapsed.
The automatic full-video observer's Map reader is UNCONFIGURED, not an observation
of no markers. Reliable generic life/death/down/remote/return recognition, full
Map/Zone integration and independent Round-number validation remain required
work. No qualified Fact/Event is produced.

Keep protected recordings, canonical GT, fixed evaluation windows, schemas and
Production gates unchanged. All resulting PRs remain Draft; main merging and
HUD/Map task redistribution require separate coordination approval.

## Primary-only intake and additional DEVELOPMENT comparisons

A new registered source does not require an audit file, roster, known map/agent,
initial state or known Round times. Use `run_match` with the same frozen
image-only observer factory and a primary-only configuration; omit
`audit_sample_plan`. Physical Source identity remains an intake/provenance key,
not an argument to `inspect(image)`. Cross-validation sidecars belong to the
separate comparison workflow and are not required for inference.

The private reproducible CLI `run_general_timeline.py` exposes policy, source,
configuration and new output directory, with optional audit/pilot bounds. It
uses the existing shared `run_match` API and state engine. A ten-second native
smoke without audit references verified the same primary recognizer fingerprint,
Source/output integrity and lifecycle-evidence parity. Five additional admitted
DEVELOPMENT recordings then completed sixty-second pilots with that recipe.
These checks verify intake and transport; they do not qualify recognition.

The current three-match full comparison and forward/offline controls are
reported in `development_full_match_comparison.md`. All exact-frame human
responses keep their original scope. Repeated acquisitions at one physical
native frame must agree for a selected evaluation value; conflicting views are
an abstention, never resolved by dictionary insertion order. Interrupted outputs
remain separate from later completed runs.

Existing DEVELOPMENT exposure is not erased by creating a new comparison
policy. Freeze source selection and input/configuration hashes before new pixel
access, retain old registry/split/GT policies, exclude all protected or
exposure-unknown material, and report parameter exclusion separately from
whole-model independence. New private policies do not change Production gates
or authorize holdout reuse.

`valorant_ai_coach.temporal.current_view_claims.project_purchase_self_claim`
provides the opt-in report-overlay observation projection. It takes current
supplier measurements, returns a derived copy and a changed-claim count, and
keeps original constraints and a new producer fingerprint. It stores no game
state or history. Reapplying it is idempotent. Current BUY alone, spectated HP100,
missing HP, an owned-death relation and competing view cues do not restore SELF.

The private primary-only CLI exposes `--purchase-self-report` for experimental
acquisition. It preserves the unmodified parent supplier rows and separately
replays their timeline for comparison. Its ordinary baseline excludes only the
shape supplier; that lifecycle parity check is distinct from comparison against
the unmodified parent view model. A native smoke and the 45-point contextual
study verify the same derived recognizer fingerprint. The new pipeline is not
covered by the historical full-video runtime receipt; keep the frozen parent
full acquisitions and the new cached/native bounded evidence separate.

The opt-in pipeline subsequently completed one additional registered full
match, with its own frozen-code/source/output receipts and exact native audit.
The known ALIVE/SELF miss remains unresolved. Five uniform adaptive prefixes
also reproduce all 300 coarse native pixels/base measurements and add 995
observations. Sparse human Round-display comparison improves 9/10 to 10/10;
future-only correct gain is zero. These metrics do not qualify unseen matches,
continuous intervals, internal event times, actor identity or Map paths.

Refinement is bounded to 40 windows and 240 seconds by default. The current
chronological selection can exhaust that budget near the beginning of a full
recording, leaving later changes unrefined. Completion of coarse acquisition
does not mean all important transitions received dense observations. Report
deferred windows explicitly; do not solve this with Source or known-time cases.

`refinement_windows(..., selection_policy="balanced")` and
`run_match(..., refinement_selection_policy="balanced")` expose an opt-in
distributed acquisition policy. The development CLI accepts
`--refinement-policy balanced`; omission preserves chronological selection.
Receipts bind the selected policy and deferred-count unit. Candidate selection
uses current observation changes and temporal strata only, without labels,
known Round times, Source conditions or a separate game-state model. Window
coverage remains distinct from correct state/event recognition.

Native audit references are grouped by at most512 points and six native
seconds per decode batch. This preserves exact PTS/pixel verification without
decoding minutes of intervening footage for two sparse references. Receipts
record batch count and limits. These audit references remain optional and
cannot carry expected states or initialize recognition.

In `development_full_match_v2`, automatic coarse/dense records alone feed both
state engines, the main observation archive and one-second output. Additional
off-grid audit observations go to `audit_observations_PRIVATE.json`; aliases
retain the original reference and actual acquisition identity. An audit frame
already acquired automatically is reused and marked as such. Receipt counts
separate `observed_native_points`, `audit_only_native_points` and
`total_decoded_native_points`. All audit suppliers and pixel bindings are still
validated. Inspector results are copied when captured, so a reused mutable
return buffer cannot rewrite earlier observations.

Historical v1 clarification: additional audit frames were inserted into the
main engine despite the receipt's `recognition_or_initialization_input=false`.
That statement was incorrect when additional frames existed. Preserve those
archives as audit-augmented sampling conditions and their same-input method
comparisons; do not describe them as autonomous sampling without review times.
The current implementation isolates these references and has a native regression
where an off-grid red frame emits death/spectator evidence while automatic blue
frames remain unchanged with or without the audit.

`DevelopmentGameTimeline(report_view_bridge=True)` optionally reconciles a
report-blocked current SELF candidate between two directly observed ALIVE/SELF
anchors in the same observed Round token, within ten native seconds. A frame
is revised only with compatible current SELF/HUD and accepted current HP.
Missing HP stays unfilled. Explicit
spectator/remote/death/downed/revival/elimination/phase evidence, score change,
or source/epoch/fingerprint/decode break rejects the span. Life-edge evidence at
the future anchor also prevents rewriting the preceding gap.

The option defaults off and requires offline inference. Revisions retain the
previous estimate, competing DEAD/UNKNOWN and SPECTATOR/REMOTE/UNKNOWN
hypotheses, current evidence and both native anchors in
`report_view_projection_history`. They do not advance rule tokens, lifecycle
events, Map authority or qualification. Updating/retracting future observations
rebuilds these hypotheses in the same shared engine.

Version `development_report_view_bridge_v2` distinguishes explicit contrary
evidence from an explicit abstention by both view classifiers. With current HUD
structure, only the report blocker and no owned-death relation, that abstention
can preserve context for at most the existing `max_carry_seconds` (default two
native seconds) since a current SELF measurement. The unreadable frame's own
estimate is retained without revision. Missing/malformed/conflicting classifier
results and accepted invalid HP reject the span. The ten-second overall bound,
same-Round anchors and all source/life/view/phase barriers remain unchanged.
Configuration records `max_abstaining_view_gap_seconds`; projection history
links `abstaining_view_samples` as exact native samples. This does not add
current SELF evidence to the unreadable frame or produce a lifecycle event.

The acquisition API and CLI expose `report_view_bridge=True` and
`--report-view-bridge`. Receipts bind engine configuration and a
`state_reconstruction_fingerprint` over observer fingerprint, engine source and
configuration, independent of acquisition epoch. The existing observer binding
also hashes shared-state code, so fresh-acquisition primary fingerprints change
even when pixel model weights do not. Keep the archived observation producer
fingerprints; do not replace old fingerprints or reuse qualification evidence.

Source and artifact checksums use complete SHA-256 with bounded 1 MiB binary
reads. This avoids allocating an entire full-match recording solely to verify
its identity. Source admission still requires the same exact registered digest
before and after acquisition; bounded hashing does not sample or weaken it.

For fixed learned-model comparisons, retain the existing model, feature schema,
physical training groups and transition weights before applying it to additional
matches. Verify original heldout prediction parity and seal transferred
predictions before reading scoped comparison labels. Missing teacher classes
mean an unavailable domain model, not permission to manufacture labels. Keep
each sampling/review cohort separate; an unsampled exact-native reference and
a mixed one-second display bin are different evaluation outcomes. Clip-level
episode-presence confirmation does not create frame or event-time truth.

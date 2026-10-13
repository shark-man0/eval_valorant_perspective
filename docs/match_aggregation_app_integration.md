# MatchAggregator → Pipeline / SQLite / GUI / JSON report

Refs #30. Depends on the verified #17 branch (`codex/l5-save-display-separation`).

## Read model

`aggregate_saved_match(repository, match_id)` derives the existing
`match_aggregation.v1` JSON view from version-1 SQLite Round Packages and
**complete canonical** evaluation rows. It constructs an AI output **envelope**
for the existing `RoundInput` contract in exactly the same shape as
`MatchAnalysisPipeline._restore_round`. It never guesses or manufactures
an evaluation, output confidence, rule decision, missing Round Package or
expected Round number.

The Match aggregator validates every reconstructed input against canonical
schemas. A corrupt Round Package is excluded with an incomplete status.
An evaluation whose package is missing causes a hard fail-closed error.
Round numbers recorded as failed but missing their package are explicitly
listed in `storage_provenance.missing_failed_round_packages` and the Match
remains incomplete. A saved-but-unevaluated or Practical/unknown boundary Round
is reported as `not_evaluated`, with 0 scored evaluations. The Match is never
`verified_complete` when `expected_round_numbers` is unknown.

Stored v1 rows do not retain candidate selections or analysis scopes; the
recomputed view does not recreate them. `storage_provenance.candidate_scopes_restored`
is false. Some context checks may consequently be less informative than during
live analysis; Fact/Event provenance remains sourced from the saved Package.

## Persistence and backward compatibility

- **No new SQLite tables, columns, migrations or schema version.** Recompute
  on demand to ensure history/relaunch gives the same view and avoids stale
  separately persisted aggregate snapshots.
- New pipeline checkpoints mark `canonical_evaluation_set=full_post_dedup_v1`
  after canonical saves. Older data are labeled `legacy_or_unverified`,
  not upgraded by inference. Resuming old jobs conservatively preserves
  that uncertainty.
- Pipeline `analysis.json`, UI result view, and JSON report expose the same
  computation. JSON report `export_format_version` stays 1 with new additive
  `match_aggregation` and `match_aggregation_error` keys. Existing CSV and
  HTML fields remain unchanged.
- UI displays Round/label counts, rule counts, incomplete reasons,
  missing context and evaluation evidence references, without new match
  grading, weights, confidence aggregation, or LLM output.
- The JSON Match view contains structured evaluation references and time
  ranges, **not** video bytes, original video locations, API credentials,
  or private ground truth. Report fields pass through existing redaction.

## Verification

Synthetic tests exercise stored/live count agreement, Round Fact/Event refs,
SQLite restart, old DBs, missing/failed/corrupt Packages, incomplete Practical
Rounds, JSON report, and read-only GUI view. No real footage or API.

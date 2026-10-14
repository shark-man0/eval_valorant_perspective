# L-5: canonical evaluations, UI sampling and clip budgets

Implementation baseline: main `c11ec6d333957cccb270417bc95a8a57f433e6ad`. Refs #17.

## Compatibility and migration

- `EvaluationAggregator.aggregate()` performs existing same-rule and same-scene
  deduplication **without** applying `max_display_exemplars_per_match`.
  The full post-deduplication set is saved by `MatchAnalysisPipeline` via the
  existing `save_analysis_result` transaction. Confidence is floored before and
  after grouping as before (D-1/D-1b). No new labels, rule policies, or GT data.
- `SQLiteRepository` remains **schema version 1**, without a new table or
  migration. `evaluations.payload_json`, `round_no`, `clip_id`, confidence
  and provenance continue to round-trip unchanged. `NonVideoFeatures` search,
  statistics, history and reports already read all stored rows; these counts now
  include every post-deduplication item.
- Older databases remain readable and are **not backfilled**: previously excluded
  exemplars cannot be recovered from an old analysis. The old displayed counts
  can be a lower bound on the actual match; callers must not claim completeness
  from those counts alone. Reanalysis uses the current policy when safe to run.
- UI sampling is a derived, ephemeral `display_evaluations` view. The
  `MatchResultView.evaluations` API remains the **complete** stored set, with
  its full counts. The UI selects the sample, and reports the displayed and
  stored counts separately. Higher-priority IMPROVE, GOOD then UNSCORED and
  higher confidence win the per-rule budget; chronology is preserved in output.
  `max_display_exemplars_per_match` remains a per-rule display limit.
- Clip generation selects an independent budget of at most **three scored
  exemplars per primary rule**, with an optional selector limit for callers.
  UNSCORED never gets a clip. Nonselected scored records still persist with
  their original `clip_id` and no associated file; the UI distinguishes
  absent clips using existing link behavior. No API inference is added.

## Operational impact

More evaluations occupy SQLite and the exported JSON/CSV/HTML, proportional to
the post-deduplication set. No additional LLM calls or video reads are made;
clip generation remains bounded by a separate policy. Old JSON export
`export_format_version=1` and database `schema_version=1` are unchanged.

## Regression scenarios

Synthetic checks cover late IMPROVE after three GOOD items, D-1b demotion,
UNSCORED exhausting a former cap, label mixtures, duplicate union with minimum
confidence, multi-round scopes, SQLite reopening, limited GUI cards with full
counts, independent clip cap, legacy truncated data, empty matches, and an
unscored Practical round. Dataset fixtures and evaluation rules are untouched.

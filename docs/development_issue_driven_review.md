# Issue-driven timeline review (development only)

This builds on the existing shared engine, whole-recording application bundle,
comparison viewer and candidate evaluation handoff. It introduces no second
state machine and does not change Production qualification, GT or fixed windows.

## Frozen inputs before tuning

Create a comparison manifest with one primary result per physical match and
explicit acquisition conditions. Each result binds its bundle and Source policy
by SHA256; the adjacent completion receipt is verified. Keep density/configuration
variants as separate versions with `compare_to`, never count them as new matches.
Use only explicitly admitted DEVELOPMENT Sources. Keep media, profiles, labels,
PTS ledgers and generated outputs outside Git.

```sh
python -m valorant_ai_coach.temporal.comparison \
  --manifest /private/comparison_manifest.json --output /private/catalog-new
python -m valorant_ai_coach.temporal.issue_analysis \
  --manifest /private/comparison_manifest.json \
  --catalog /private/catalog-new/comparison_PRIVATE.json \
  --output /private/issue-analysis-new.json
```

The classifier assigns multiple **cause hypotheses**, never error labels. A1
requires missing observations or an explicit barrier; ordinary PTS spacing does
not prove semantic continuity. A6 requires a current unassigned marker pool; a
missing Map analysis is not a negative observation. A8 describes competing native
values hidden by a second summary; native information remains intact. A9 uses
separate density-cohort evidence and does not prove which cause changed a state.
A5 reason-token matching remains a heuristic rather than a verified causal chain.

Priority combines domain impact, physical-match prevalence, capped log duration,
context tension, available evidence, generic algorithm opportunity and downstream
impact. Representative selection caps per-match/domain/cluster allocation and
suppresses overlapping inspection windows. It may return fewer than its budget
when no eligible diverse window remains. No labels are read for selection.

The frozen development run classified all 7,644 original intervals across eight
already exposed matches and selected 24 representatives: eight Round, eight HUD
and eight Life/Camera. The input catalog contained no Map review intervals;
A6=0 does not mean Map correspondence is solved. Native Map evidence is compared
in its separate 140-packet cohort.

## Conditional state projections

`DevelopmentGameTimeline(return_display_tail=True, buy_clock_tail=True)` and
application/match CLI flags `--return-display-tail --buy-clock-tail` are explicit
offline opt-ins. Defaults preserve the earlier engine. See
[conditional state tails](development_conditional_state_tails.md),
[targeted acquisition](development_targeted_native_acquisition.md) and
[Map/HUD candidates](development_issue_driven_map_hud.md).

They preserve previous estimates, native evidence and candidate brackets. They
cannot assert an exact return/boundary time, grant Map ownership or generate
qualified events. Reusing an acquisition in `application generate` checks that
requested state options are present; `application export` can explicitly replay
its immutable observation ledger with these options without decoding again.

## Existing viewer, optional bound sidecars

Add these optional fields to a new comparison manifest (retain the baseline
result IDs and their immutable bundles in `results`):

```json
{
  "issue_analysis": {"path": "/private/issue-analysis-new.json", "sha256": "..."},
  "improvement_history": {"path": "/private/history-new.json", "sha256": "..."}
}
```

The analysis binds its original manifest, result bundle/policy hashes and original
conditions/compare-to links. Additional before/after versions and a changed current
primary selection are allowed: the cause panel explicitly describes the frozen
baseline cohort, rather than the current primary results. Changed baseline files
or acquisition conditions fail closed. Sidecar
files themselves must match their declared digest. History schema is
`development_timeline_improvement_history_v1`, `formal_outputs: 0`, with `records`
containing `id`, `problem`, `cause_hypothesis`, `change`, `inputs`,
`gained_controls`, `lost_controls`, `unverified_changes`, `decision`, and `next`.
Use null/unmeasured where needed; counts are not automatically accuracy metrics.

```sh
python -m valorant_ai_coach.temporal.comparison_viewer \
  --manifest /private/comparison-with-sidecars.json --port 0
```

The existing desktop comparison-manifest action uses the same server factory.
Cause filters and bounded pages expose prioritized representatives. Selecting a
problem selects its native inspection anchor. The context button shows five
seconds of before/after state estimates, competing hypotheses, UNKNOWN reasons,
configuration, immutable native samples and observations. The existing original
video/native button opens the registered unedited source at that recording time.
Different Source clocks cannot be compared through this endpoint.

`/api/catalog` omits large unused issue reference arrays for the presentation;
`/download.json` retains the full original catalog and evidence references.
`/api/issues` paginates at most 100 issue summaries, `/api/context` verifies both
result receipts, and `/api/history` exposes the bound experiment record. These
are tokenized localhost development endpoints, not a public service.

Map views expose same-appearance competing pool indices without choosing a
recorder. Credits values retain `unqualified_fixed_profile` geometry and viewed
actor ownership UNKNOWN. The downstream review includes every present HUD field,
including Ammo and Credits, while deterministic facts/events stay empty and the
coaching decision remains null. Candidate gains, abstentions, verified controls
and unseen-data accuracy must be reported separately.

## Verification and integration

Tests cover cause semantics and missing-analysis negatives, diverse selection,
sidecar tamper rejection, context range checks, HTTP/GUI compatibility, bounded
sampling, conditional state barriers, value ownership and Map competition. Keep
Linux/Windows tests, Ruff, mypy, Text I/O and packaged GUI smoke green at the exact
new SHA. See [staged integration](development_staged_timeline_integration.md) for
feature slices, dependencies, exclusions, integration tests and rollback. Nothing
in this workflow authorizes a main merge.

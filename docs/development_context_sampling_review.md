# Development context sampling and bounded display review

The shared engine, pixel models, thresholds and default sampling behavior are
unchanged. Wider before/after acquisition is an explicit development option;
it does not turn missing pixels into observations or create qualified outputs.

## Acquisition API and CLI

`temporal.match.run_match` accepts
`refinement_padding_seconds: Fraction = Fraction(1)`. The existing
`refinement_windows(..., padding=...)` selector receives this value. Exact
fractions in `[0, 10]` seconds are accepted. Windows still arise from measured
display/score/clock/marker changes, without Source-specific recognition rules,
known Round times, roster input or initial-state seeds.

Both the native match CLI and application `generate` accept
`--refinement-padding-seconds`. The application also exposes the existing
`--refinement-policy chronological|balanced` selection. For example, with an
already authorized private DEVELOPMENT registry and existing image observer:

```sh
python -m valorant_ai_coach.temporal.application generate \
  --policy /private/work/policy.json --source-id REGISTERED_SOURCE \
  --reader-config /private/work/reader.json --observer supplier:PixelObserver \
  --refinement-policy balanced --refinement-padding-seconds 6 \
  --report-view-bridge --buy-clock-expiry --active-clock-bridge \
  --output /private/work/new-context-run
```

The shared Profile/observer must be configured independently of the Source.
Original native samples, raw observations, epochs and recognizer identities
remain in the acquisition and application outputs. Source admission, exposure
journaling and private-output rules still apply. No protected media is required.

The dense acquisition budget remains 240 seconds. Balanced proposals retain the
old six-second cap with default padding, and use a cap of
`max(6, 2*padding+2)` seconds when widened. The extra two seconds cover the maximum
coarse gap. Temporal strata and the global budget remain enforced; larger
contexts can reduce the number of selected changes. Widening does not guarantee
that every uncertain point is selected or recognized. Missing decoder frames
are not filled. The default one-second padding remains unchanged.

The acquisition receipt records `sampling.refinement_padding_seconds`,
`sampling.balanced_proposal_seconds` and the existing selection/budget fields.
On `application generate --reuse-acquisition`, explicitly requested padding or
selection must agree with the recorded settings. Historical receipts without
the padding field represent the old one-second default. Reuse exports existing
evidence; it never claims to have acquired a newly requested wider context.

## Fixed existing-recording experiment

Selection was sealed before decoding or reviewing new evidence. The prior
clock-chain rule revised 121 whole-match points in seven development-exposed
matches. The first and last revision in each affected match formed 14 fixed
native review centers, each with two seconds of before/after display context.
AI visual inspection supported ACTIVE at all 14 centers, with no contradicted
or undecidable center. This is an AI inspection, **not human-verified accuracy**;
the remaining 107 revisions are unscored. No Source/time-specific exception or
Round rule change was justified or introduced.

For lifecycle context, one uncertain run per each of eight exposed matches was
fixed from sealed predictions: prefer a DEAD/SPECTATOR-to-ALIVE/SELF bracket,
otherwise its inverse; longest same-epoch gap at most ten seconds, earliest
tie, nearest retained native midpoint. These predicted brackets select where
to look; they do not establish that a death or return occurred.

The unchanged observer acquired 25 original frames per context at half-second
cadence, within six seconds on either side. Short contexts use the five common
frames within one second. Each fresh context has its own acquisition epoch;
no old inferred state is copied across epochs. Short/wide and
forward/offline/report-bridge outputs use the **same existing shared engine**.
Offline Round-only projections are disabled in the forward variant. Plain
offline and report-bridge comparisons keep their other settings identical.

At the eight original native centers, short contexts abstained on life/camera.
Wide forward and plain offline contexts yielded one ALIVE/SELF candidate and
one further SPECTATOR camera candidate. The existing offline report bridge
added another ALIVE/SELF center: two life and three camera candidates overall.
The corresponding queried one-second views show the same gains. These query
bins contain only sampled observations, not labels for all frames in a second.

Forty native frames are common to short/wide comparisons. Ten life and fifteen
camera UNKNOWN values gain candidates there; no previously non-UNKNOWN
prediction changes. This invariant is not a correctness or population
false-attribution measurement. Three newly revised camera centers agree with
scoped human display review. The two ALIVE candidate centers have no separately
scored life labels. Neighboring display review remains exact-frame evidence and
does not label the intervening interval or precise event times.

The remaining centers retain abstentions: tracker/menu overlays obscure local
HUD geometry; result/round-transition views lack an eligible current self
witness; report presence alone does not establish recorder death. Wider
context does not resolve all these recognition failures, so the new padding
remains opt-in. This bounded experiment does not rerun or replace the eight
whole-match archives, measure full-match event false positives, prove unseen
generalization, or restore strict Map ownership.

## Validation and scope

Sampling tests cover default equivalence, wide balanced windows, the global
budget, nonzero origin and identity invariance, invalid widths and real native
CLI generation/reuse with JSON/CSV output. Existing shared-engine/transport/
application tests remain applicable. The inference model, state definitions,
GT/windows/splits, Production gates, weights and formal Fact/Event channels are
unchanged. Per-frame reviews and private media stay outside Git.

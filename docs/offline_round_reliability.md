# Offline purchase Score recovery and evaluation readiness

Bright scene content can cause a configured Score crop to reject a digit even
when the top HUD structure is supported. Structure support alone is neither
text correctness nor player ownership. The original configured subregion must
be retained: applying the digit reader to its outer layout ROI is a different,
invalid comparison.

## Explicit reader alternative

The existing Score preflight has a disabled-by-default offline option:

```python
readers, binding = score_readers(
    private_profile_path,
    foreground="white200_rowcontrast_v1",
    background_fallback=True,
)
```

`RejectedScoreBackgroundReader` returns a successful baseline read unchanged.
After rejection only, it applies the existing native-pixel border-background
separation before enlargement, then the existing white200/Gaussian Score reader.
Both stages keep all ten digit competitors and the original 0.90 threshold and
0.04 class margin. There is no expected Score, temporal filling, confidence
winner or alternative chosen by predicted Round outcome. Missing or occluded
glyphs can remain unread. The original Profile subregion, parent bytes and digit
asset hashes are preserved; the explicit recovery flag is included in the
returned binding. Rebuild pixel/output-bound component receipts with the new
effective reader binding before temporal analysis.

This alternative is an offline observation method. It is not installed in
production, and a recovered numeral is not independent proof of a correct
Score. A stable wrong reading remains possible. Compare exact inputs and retain
baseline rejection reasons, recovered readings and private image witnesses.

A fixed four-condition development experiment separated rejected-Score recovery
from a proposed punctuation-checked Timer crop. Score-only recovery was selected
for further development. The Timer proposal added readings without improving
the tested Lifecycle outcomes and was not adopted. The existing Timer format
implementation and purchase/End association rules remain unchanged. Future
comparisons must distinguish additional context from a reader change.

## Reuse for additional recordings

Use the existing private registration/allocation/Exposure workflow before any
new recording is opened. The HUD workflow consumes approved DEVELOPMENT entries;
it does not register data, change allocations or open protected evaluation data.
Freeze input windows and the baseline method before predictions. Preserve failed
and ambiguous outcomes. Run the fixed baseline first and the explicit alternative
on the same pixels, then report text changes, geometry support, separate End and
purchase-to-clock hypotheses, UNKNOWN reasons, runtime and memory. Do not count
extra frames or overlapping context as extra physical transitions.

Use the existing failure index and fixed-window review contract. Reviewed End NO
and Start NO have separate denominators; YES, UNKNOWN and unreviewed windows do
not enter either negative denominator. A two-second purchase-only window can
remain UNKNOWN because its next clock is outside the observed interval. An
already-visible Result without an observed onset is display context, not a
confirmed End transition or a negative. No population accuracy is inferred.

## Independent qualification gate

The governing contract remains [Temporal source annotation v1](temporal_gt/annotation_contract_v1.md)
and its existing schema/validator, not a new HUD GT system. Development success
and passing software tests do not satisfy this gate.

Before any separately authorized qualification run, retain the following private
evidence and validate it against the existing contracts:

- Video/physical-match independence, duplicate/clip grouping, frozen allocation
  and chronological Exposure provenance. Previously observed DEVELOPMENT sources
  cannot be relabelled as independent holdout. Unknown prior use stays unknown.
- Independently reviewed source labels and complete review scope selected without
  predictions, including missed events. Stable physical event IDs, positive,
  negative and UNKNOWN labels must be distinct. Unreviewed time is unscored.
- Frozen recognizer code, Profile/layout, all assets/references, preprocessing,
  thresholds, decoder fingerprints and temporal policy before predictions.
- Source SHA, integer PTS, rational timebase, actual frame hashes, acquisition
  epochs and reviewed visual continuity. Regular container cadence does not prove
  continuous visual content. Gaps, duplicate PTS and different epochs are barriers.
- Separate last Active, partial/complete Result, Score change, purchase evidence
  and next-clock brackets. Wider observed brackets remain wider; no midpoint,
  interpolation or video-only internal game End/Start truth is generated.
- Natural threat coverage: normal play/countdown, buy, death/spectator, menus and
  overlays, Score-only changes, partial/stale Result, Timer-format changes,
  crop/scale mismatch and source discontinuities. Record reviewed episode counts
  and missing classes, not just frame totals.
- Predeclared matching/deduplication and UNKNOWN handling. A supported hypothesis
  in a reviewed negative scope is a false hypothesis; an independently labelled
  observable event without a match is a miss. UNKNOWN and out-of-scope boundaries
  must remain visible rather than being silently dropped from totals.

These conditions are not established by the current development experiment.
Qualification and formal End/Start publication remain closed. Software suitable
for later integration is limited to the explicit offline reader, binding checks,
regression tests and documentation. Production Profile/Matcher changes, reference
assets, private data and event release require their separate qualification.

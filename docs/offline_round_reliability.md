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

## Explicit offline purchase text structure

`PhaseStructureReference` reuses the frozen Profile's source-supported semantic
text groups at their original position. It measures bidirectional edge coverage
within a symmetric one-pixel raster neighbourhood. Every group needs at least
32 observed/reference edges, positive foreground/background polarity, and both
coverage and precision at the unchanged reference threshold (at least 0.90).
There is no alignment search, inferred glyph, phase absence or ownership output.
A missing, inverted, occluded, displaced or differently sized group remains
UNKNOWN. Background texture can change without requiring pixel NCC to match the
same texture. Similar contours can still be mistaken for text; this witness is
an unqualified development alternative, not independent semantic correctness.

`bind_phase` binds the observation to the actual full-frame pixel hash, fixed
crop, source/PTS/acquisition witness, private Profile and reference fingerprint.
An explicit `phase_structure` receipt opts the offline lifecycle reader into
this alternative. The legacy `buy_phase` observation is retained. Score, Timer,
Result, geometry, continuity and repeated-support rules still apply. A nonmatch
never proves phase disappearance. Production Profile/Matcher configuration is
unchanged. Compare the baseline with the alternative on identical pixels,
including reviewed natural controls; do not count newly read images as new
physical rounds or as ground truth.

## Development Round Timeline

`round_timeline` projects existing offline lifecycle reports into round candidate
entries with the original Score/Result/purchase/next-clock brackets, witnesses,
UNKNOWN reasons and acquisition alternatives. Exact report repeats and
overlapping Native Score-boundary hypotheses are grouped. Conflicting Score
hypotheses remain UNKNOWN. A complete chain must already be supported inside
one acquisition; partial evidence from different epochs is never fused.
Internal End/Start and physical event identities remain unset. This projection
is private development data and must not be converted into production events.

Whole-recording sparse discovery can select bounded Native follow-ups. When a
fast backend provides frame-index/FPS offsets rather than verified Native PTS,
retain null Native tick/timebase and mark those offsets unverified. Such rows
must never enter the Native lifecycle integrator or become boundary evidence.
Only the existing bounded decoder's actual integer PTS, rational timebase,
frame hashes and acquisition ledger can support a displayed boundary.

## Coupled component geometry and observed Score intervals

The explicit `joint_regions=True` component option uses the existing frozen
outline references and Profile ROIs. A single reference must pass the existing
multi-direction spatial specificity check on the union of the two Score regions
and Timer region, then every one of their six disjoint halves must pass the
unchanged 0.90 edge floor. References cannot be mixed across parts. This differs
from accepting individual generic contours. The default three-tile method is
unchanged; neither option authorizes full HUD geometry or player ownership.
Result text still needs its independently verified title region.

Both offline CLIs expose `--observed-score-brackets`. With a complete contiguous
Native ledger, the last literal old Score and first literal new Score can bound
an interval of at most one second. Unread intervening frames and their hashes
remain visible; no Score value or internal time is filled in. A Result inside
that unread interval leaves its ordering UNKNOWN. Gaps and different epochs
remain barriers. `--observed-score-persistence` additionally permits recovery of
rejected adjacent-read persistence using the nearest actual same-Score witness
within one second, with Score geometry supported at both observations. A
contradictory intervening reading cannot be skipped. Existing successful proofs
are preserved. Both switches default off; the persistence option requires the
bounded bracket option. The output records the policy and actual witnesses.

`ProfileTimerDisplayReader` retains the configured strict Timer reader and its
inner subregion. It returns successful configured readings unchanged. Rejected
readings can only gain a literal decimal through the existing topology-checked
extension, never an alternate colon or inferred punctuation. Comparing an
unwrapped reader on the outer ROI with the configured Profile is a configuration
comparison, not proof of better OCR accuracy. Preserve that distinction when
reporting recording-to-recording diagnostics.

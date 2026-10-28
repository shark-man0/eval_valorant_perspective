# Development marker center selection and observed-endpoint associations

This opt-in experiment builds on PR #102. It does not replace a default detector,
qualify recorder ownership, publish player events, or update the Map Registry.
All appearance/temporal outputs retain `ownership=UNKNOWN` and formal outputs 0.
The incremental feature/history API is reviewed separately for Issue #105.

## Features and fitting

`development_marker_center.py` extracts 41 measurements from complete native
25x25 BGR patches: radial gradient support at seven radii, opposing-arc coverage,
center-versus-offset support, chromatic cross support, and separate center,
annulus and outer-region contrast/statistics. The feature fingerprint includes
OpenCV/NumPy versions. Position support is separate from semantic classification.
Scores are uncalibrated development scores, not confidence probabilities.

The fixed experiment reuses 24 human TRAIN labels, including 7 confirmed UI or
background labels. A balanced ridge readout requires human TRAIN support for all
four classes: PLAYER, DEATH_MARKER, UI and BACKGROUND. It refuses pseudo-labels,
UNKNOWN, SSL-only inputs and validation/comparison inputs as semantic training.
A separate weak center readout uses nine native offset crops from each of 17
positive TRAIN references (153 examples, still only 17 human references).
Those offsets are uncertain annotation-relative supervision, never extra human
GT, background labels or true center measurements. Ridge strength is fixed at 1.

The existing 192-dimensional SSL representation is an ablation. No new backbone
was trained. TRAIN, validation, previously exposed comparison data and later
transfer inputs retain their existing conservative leakage/source roles.

## Non-destructive selection

`select_center_candidates` verifies native pixels and sample/window bindings. It
ranks existing coordinates and preserves the raw pool. Seed-relative windows
within 2px are grouped only with appearance similarity; groups are hypotheses,
not a count of physical objects. Distinct or ambiguous alternatives can remain.
There is no coordinate averaging, inferred recentering or ownership promotion.

The initial group/Top-5 policy lost previously matched clicks and was rejected.
A second policy, frozen from TRAIN/validation, preserves the complete default
parent prefix and adds at most one sufficiently separated, supported alternative.
`retain_parent_with_center_alternative` implements that policy. UI/BACKGROUND
semantic candidates are ineligible as added alternatives. Default parents are
preserved even if the experimental semantic readout disagrees with them.

Callers acquire accepted DEVELOPMENT media and verify Source/split/Exposure first.
Use `bound_patches` in chunks of at most 128 and bind the combined window hashes
with `_digest(bindings)` before passing features to selection. Feature matrices
must be computed for those same current windows. Neither this function nor a
model file constitutes Source admission or recognition qualification.

## Fixed comparison and decision

Two previously exposed, reviewed DEVELOPMENT ROIs have 11 positive clicks. The
2px comparison radius is held fixed; human click uncertainty is not guaranteed
to be within 2px. These are not precise physical marker centers. Unmatched windows
are not automatically confirmed UI/background. Complete-annotation metrics apply
only inside the declared reviewed scope, never to unreviewed ROIs.

| Method | Click matches | Unmatched | FN | Old matches lost |
| --- | ---: | ---: | ---: | ---: |
| A: default parents | 7 | 3 | 4 | 0 |
| B: full broad pool | 9 | 164 | 2 | 0 |
| C: center rule, preserve parents + one | 8 | 4 | 3 | 0 |
| C: weak center, preserve parents + one | 7 | 5 | 4 | 0 |
| D: center + confirmed semantics | 8 | 4 | 3 | 0 |
| D: center + SSL + semantics | 8 | 4 | 3 | 0 |
| E: D + temporal, these isolated ROIs | 8 | 4 | 3 | 0 |
| Same-budget first-novel control | 7 | 5 | 4 | 0 |

C/D retain 2, 5 and 8 clicks at per-ROI Top-1/3/5. Their selected outputs match
6 PLAYER and 2 DEATH_MARKER clicks; the default matches 5 and 2. Adding semantic
classification did not improve the selected-window result. E has no verified
continuity between these isolated ROIs, so it correctly adds no temporal links.

A separate human-centered crop classification comparison gives 9/14 correct
with center semantics and 10/14 with center+SSL, versus 5/14 for the prior local
appearance readout. These 14 contain no UI support and only 3 BACKGROUND examples;
none of those background examples was classified exactly correctly by either
new readout. This is limited morphology classification evidence, not improved
localization, general UI/background accuracy or independent qualification.
Validation favored the simpler center semantic model; SSL remains an ablation.

**Do not adopt into the default recognizer.** The extra matched click comes with
an extra unmatched candidate (4 exceeds the frozen maximum of 3). The larger
pool and the broad Top-5 policy are also not adopted. Report implementation and
experiment completion separately from selection improvement and qualification.
No default thresholds, canonical GT or production contracts were changed.

## Unmatched-window analysis

The 164 unmatched windows comprise: 1 exact native-center duplicate; 25 hypotheses
2-10px from known positive clicks; 1 agreement with a known BACKGROUND point;
99 unannotated marker-shape possibilities; and 38 UNKNOWN. There are no confirmed
UI-point agreements. The geometric/shape categories are not human semantic GT.
Whether a hypothesis belongs to a different teammate/enemy/object remains UNKNOWN.
The two ROIs contain 101/72 windows and 91/57 seed-relative review groups, with
5/5 positive-supported, 0/1 negative-supported and 86/51 UNKNOWN groups. These
are alternative windows, not verified physical-object counts.

## Temporal and PR #107 integration

`DevelopmentMarkerAssociations` reuses existing positive-PTS, <=0.3s and matching
source/acquisition/Profile/ROI/build continuity conditions. The caller must supply
a verified source-bound continuity receipt, not just nearby timestamps. Links
require position distance <=12px AND native-patch appearance cosine >=0.90,
mutual unique matching and a 0.10 ambiguity margin. Missing detections, discontinuous
or nonincreasing PTS, identity changes and view/life changes reset association.
Crossing lookalikes are rejected rather than assigning an identity by proximity.
Malformed observations discard prior state before propagating the validation
exception, including failures inside native sample freezing.

Only observed endpoints are linked. There is no interpolation, retained track
through a missing observation, inferred movement, or recorder-marker binding.
A persistent background feature can also satisfy temporal consistency.

PR #107 is consumed as a read-only external research dependency, not copied into
this implementation. Its state is a source-bound, unqualified hypothesis. An
existing image-based spectator veto supplies an actual UI observation; absence
of this UI supplies no positive recorder evidence. Exact-frame human view labels
are a separate conditional experiment. `marker_is_self_ui` remains false because
there is no observed UI binding a marker ID to the recorder. Sage/Clove/KAY/O and
Phoenix transitions are synthetic state-machine tests, not claimed video events.
The caller verifies the receipt and pixel identity before bridging an old exact
human review onto a re-acquired native frame.

A post-selection comparison uses 80 native observations in three short intervals
from two accepted DEVELOPMENT sources. Full native frame PTS probe/decode lists,
source SHA before/after and native pixels are checked. For the later Haven input,
3 reviewed centers remain 3/3 for A-E and 18 stationary observations have 0px
candidate spread. These are sampled points, not continuous movement GT or world
coordinate accuracy. Temporal ranking changes 5/30 Haven and 7/20 spectator
selected sets without increasing reviewed-center matches. The spectator reader
finds 19/20 points; default position rejection is separate and must retain its
existing regression. Automatic recorder ownership is UNKNOWN on all 80 points.
The 30 human-conditioned Haven view hypotheses do not qualify automatic ownership.
Partially annotated ROIs have no precision/false-positive denominator.

## Reproduction and evidence boundaries

Unit tests cover actual native patch geometry/bindings, all-class TRAIN support,
weak-reference deduplication, parent preservation, confirmed-negative exclusion,
view/life/source resets, disappearance and ambiguous crossing associations:

```sh
python -m pytest tests/unit/test_development_marker_center.py \
  tests/unit/test_development_center_selection.py \
  tests/unit/test_development_marker_temporal.py -q
```

Private receipts retain frozen plans, source/window hashes, actual model weights,
all candidate coordinates, timings, classification confusions and the full
80-frame comparison/viewer. They are not included in Git. Additional human
reviews: 0. Protected recordings used: 0. The previously prepared Terra batch
remains unsent/unanalysed; no approved Terra result is claimed. The repeated
DEVELOPMENT sources do not establish an independent physical-match qualification.

## Resource measurements

Three isolated single-thread runs on the same existing 18 native DEVELOPMENT
images give median recognition times A/B/C/D/E of 14.57/14.84/17.06/16.83/16.96s,
and median peak RSS 299.9/302.0/306.6/307.9/305.9MiB. All three runs reproduce the
same output digests within each method. C/D timing differences overlap ordinary
measurement variability; the added semantic readout is not claimed faster.
Decode time is excluded and model construction is included. These 18 are not
continuous, so E correctly makes no links: its timing is a lower bound for linked
intervals. The separate 80-frame run measures 0.53s for association/HUD handling,
73.62s total processing and 261.8MiB peak RSS. Source verification and native
acquisition are separate (23.97s); neither is hidden as recognition throughput.
The experiment is not a calibration speed optimization or a performance guarantee.

After hardening exception-state reset, all 240 calls over the same 80 native
observations reproduce the earlier association results exactly. Three additional
isolated E processes reproduce all 18 original output digests; the timing/RSS
figures above use those final E runs. Lower observed RSS is process variation,
not a claimed optimization. An acquisition-mismatch validation exception is
reproduced before the fix and no longer permits a later observation to reconnect
to the pre-error state.

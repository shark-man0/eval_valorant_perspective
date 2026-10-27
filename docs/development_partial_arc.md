# Development-only partial-arc proposal experiment

This opt-in research module adds unassigned radial-edge proposals alongside
the existing D (`CrossMarkerDetector`) output. It does not modify D, select a
recorder or player, assign a death, change a Production detector, produce a
position Fact, or infer temporal continuity. All added proposals retain
`ownership=UNKNOWN`, `semantic_class=UNKNOWN` and `development_only`.

## API and limits

`DevelopmentPartialArcDetector` accepts the same explicit cross appearance
profile as D. `observe` requires an exact frozen native sample, frame, minimap
ROI and explicit appearance pool. It validates the frame pixels and sample,
executes D first, searches the same crop, rechecks the image and reference bank,
and returns the unchanged D object and an ordered union of D followed by arcs.
Each union record binds the sample, proposal source and frame-space center;
nearby D indices are an UNKNOWN relation, not a deduplication or a claim of
physical identity. Geometry, map position, and zones are not inferred for arcs.
The old D objects, order and attributes are preserved even if the arc budget is
exhausted. Parent search truncation and arc truncation are separate.

The fixed experimental search samples twelve directions at radii 6, 8, 10, 12,
and 14 pixels. A sector is supported when its Sobel gradient's radial component
is at least 48 with radial coherence at least 0.55. At least 7 of 12 sectors are
required; observed disk boundaries and deterministic local maxima with 5px
nonmaximum suppression are used. Color is not required. Up to 4096 local maxima
are processed, and up to 64 new hypotheses are emitted. `candidate_peaks_total`,
`processed_peaks`, `unprocessed_peaks`, `output_overflow`, and
`search_truncated` expose the limits. Overflow counts are processed peak
hypotheses relative to already-emitted peaks, not distinct physical markers or
an exhaustive count of lost objects. The raw sector ratio is not a calibrated
probability. This generator is deliberately broad, and unreviewed candidates
must not be converted to ground truth or negative labels.

## Diagnostic replay and fixed-input comparison

Issue #100's TMM012 native observation was replayed with the original profile,
reference bank and D method. Its five prior D proposals were reproduced with
identical stored fields; none of their centers lies in the investigated 61x61
region. No accepted NCC observation occurred there. One nearby Hough-circle
observation failed the existing rim condition because its outer color contrast
was below the required bound; no alternative-circle or cross observation was
recorded in that region. This is a stage-level diagnostic, not proof that the
rejected circle corresponds to the displayed object, or that any visible object
is a human-confirmed player. The fixed arc method emitted three hypotheses in
the region; their semantics and true-center errors remain UNKNOWN.

The comparison was fixed before running the new method: 53 previously exposed
TRAIN/SSL_TRAIN frames represented in Terra's 144 crops and three previously
reviewed DEVELOPMENT_TRAIN frames, with no validation or frozen images used.
The 24 existing human-labelled patches on the latter frames include 12 PLAYER,
5 DEATH_MARKER, 6 UI and 1 BACKGROUND. The 17 positive centers are prior human
clicks, not Terra-derived labels. A one-to-one 2px match measures agreement with
the clicks, whose own localization error is unmeasured; the tiny, exposed and
non-exhaustively annotated set is not independent qualification or population
recall. Do not count unmatched or UNKNOWN proposals as false positives.

| Measure | A: D | B: D + partial arc |
| --- | ---: | ---: |
| Fixed native frames | 56 | 56 |
| Original D candidate records | 218 | 218 |
| Additional arc records | 0 | 3,584 |
| Original D candidates lost | — | 0 |
| Matches to 17 positive clicks, full output | 7 | 11 |
| PLAYER matches / 12 | 3 | 6 |
| DEATH_MARKER matches / 5 | 4 | 5 |
| Matches at K=1 / 3 / 5, D-first ordering | 1 / 3 / 5 | 1 / 3 / 5 |
| Explicit UI/background points near any candidate / 7 | 3 | 5 |
| Candidates unmatched to positive clicks on the three labelled frames | 7 | 195 |
| Arc-truncated frames | — | 56 |
| Sum of detector times for 56 frames | 30.86 s | 34.31 s |
| Median detector time per frame | 0.548 s | 0.609 s |
| Process peak RSS | 151.1 MiB | 150.6 MiB |

The D records match exactly across the paired runs. The nine previously
identified yellow-overlap crops all retained their associated D record. The
53 original survey frames also reproduced the stored D center lists; the first
row above counts all 56 distinct native frames, not the 144 cropped samples.
Full-output click coverage is 7/17 vs 11/17; per-frame matching did not lose
any previously matched positive click. `Recall@K` uses D's existing order then
the arc sector order; neither cross-method scores nor this rank are calibrated.

The seven negative controls are annotated points, not a complete negative area:
proximity to one is a diagnostic, not a measured population false-positive rate.
The 7 vs 195 candidate counts only mean unmatched to the known positive clicks;
they can include valid, duplicate, unreviewed, excluded, or negative objects.
Every B frame hit the 64-addition cap. The search reported 109,513 processed
overflow peak hypotheses and 4,565 unprocessed peaks; these are not counts of
distinct objects or labelled errors. The D-first top-K results did not improve.

Timing is one isolated process per method with single-thread BLAS and OpenCV
threading disabled; decode is excluded from summed per-frame detector time.
It is not a statistical benchmark. RSS includes the whole process, and a small
one-run difference does not establish a memory improvement. Source IDs, native
times, frame images, exact reference hashes, review evidence, and per-frame
outputs remain private.

## Decision and next step

The additional search recovered four click agreements in this exposed
development sample but produced many candidates and truncated every frame.
Its top-K result did not improve, and precision is not measurable from these
annotations. **Do not adopt this detector as the default or as a qualified
recognizer.** Evaluate a bounded feature-based reranker and stricter candidate
budget under a separately frozen development plan, while preserving the D
stream. Human review must establish which additional candidates are eligible,
including confusing UI and overlap; a later unseen physical-match evaluation
must remain separate from these explored examples.

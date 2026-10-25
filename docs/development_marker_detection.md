# Bounded, unassigned marker detection

`BoundedMarkerDetector.detect(roi_bgr, appearance_pool)` is an opt-in first
stage for visible appearances. It searches both positive and control references
without transferring their source recording's player roles. Native-scale NCC
anchors are retained first; four additional scales and textured, colored-rim
circle hypotheses can add candidates. A circle is an appearance hypothesis,
not proof that an icon is a player, alive, or owned by the recorder.

`DevelopmentDetectedMarkerProposals(map_id).observe(...)` connects those
candidates to the existing native-sample binding, current-frame outline
calibration and registered floor check. Its arguments have the same contract as
`DevelopmentMarkerProposals`; see [the proposal API](development_marker_proposals.md).
No default factory or Production recognizer selects this new implementation.

The stages remain separate:

1. ROI appearances and their individual detection evidence.
2. Raw geometry in `geometry_only_map_position_norm`, when current calibration
   and floor checks succeed. Context-blocked diagnostic geometry is retained
   with its eligibility flag. It cannot contribute to a recorder route or dwell.
3. Target assignment remains absent. Ownership and version compatibility are
   UNKNOWN, ordinary map positions/Zone resolutions are null, and selected self
   position, Fact, events, tracks and interpolation remain empty.

Use a verified acquisition manifest for the encoded frame hash; the API checks
the decoded frame pixel digest and native sample. A caller must explicitly
select a supported development map. An unknown map must remain ROI-only outside
the geometry wrapper. Neither context eligibility nor successful calibration
qualifies map-build compatibility or authenticates a camera subject.

## Search and evidence contract

Input is uint8 BGR, with ROI edges between 65 and 1024px. There are at most four
explicit libraries. Existing inspector similarity acceptance remains unchanged.
The scales are 0.75, 0.875, 1, 1.125 and 1.25; normalization uses pixel-center
coordinates. Out-of-budget scaled ROIs are skipped with explicit truncation.
Each inspector supplies at most 32 proposals per scale. NCC duplicates use
seed-relative center distance and box overlap; no center averaging is applied.
The final deduplication radius is 4px in the actual input ROI, including resized
test inputs. It can suppress nearby distinct icons; inspect the associations.

Circle search checks at most 128 Hough hypotheses, retains at most 64 supported
circles, and checks radial gradients, inner texture and rim color distribution
across quadrants. It does not recognize death crosses or all marker styles.
The final output cap is 128. Search limits, discarded duplicates, raw NCC
observations, circle support/rejection and overflow are explicit diagnostics.
Similarity and circle support are different evidence types, not calibrated
player probabilities or interchangeable confidence scores.

Reference content, specifications, ROI shape and configuration are
fingerprinted. References and current pixels are rechecked before return;
invalid input cannot reuse the last result. No previous-frame transform or
marker is reused, and missing observations do not coast or interpolate.

## Development comparison

The predictor and parameters were frozen before reading new review annotations.
The same 2px tolerance was retained. All data are already exposed DEVELOPMENT
recordings, not final qualification. No private frames, source identifiers,
timestamps, coordinates, profiles or aliases accompany this document.

| Fixed inputs | Previous | New |
| --- | ---: | ---: |
| Known 20: annotated recorder-marker matches / 15 | 4 | 7 |
| Known 20: teammate-marker matches / 61 | 13 | 19 |
| Known 20: OTHER matches / 2 | 2 | 2 |
| Known 20: comparable unique candidates | 29 | 63 |
| Known 20: unmatched, role unknown | 10 | 35 |
| Separate 10: PLAYER matches / 46 | 5 | 11 |
| Separate 10: OTHER matches / 3 | 0 | 0 |
| Separate 10: comparable unique candidates | 8 | 27 |
| Separate 10: unmatched, role unknown | 3 | 16 |
| Fixed 40: images with an ROI candidate | 31 | 40 |
| Automatic self selection / qualified outputs | 0 | 0 |

Known 20 images were used for failure analysis and method selection. Separate
10 images were selected before predictions, one per recording, from the fixed
40-image plan. Their labels were used for scoring only. They label PLAYER
without recorder/team roles and include visible death crosses. New-review
coverage is UNKNOWN: unmatched candidates are not background false positives,
and population precision cannot be measured from these annotations. Separate
10 scoring uses one-to-one matching to avoid counting one candidate twice.

Synthetic ROI resizing improved recorder-marker matches from 0 to 5/15 at
0.75x and from 1 to 6/15 at 1.25x. These are image resampling tests, not evidence
for real HUD changes or arbitrary resolution transfer. Downsampling can destroy
texture that normalization cannot restore. At native scale the raw geometry
matches on known recorder annotations increased from 2 to 3; these remain
unassigned, unqualified geometry.

The method increases candidate recall with more unknown proposals and more
compute. It is unsuitable for default adoption without additional background,
overlap, death-marker, center-accuracy and acquisition-condition evaluation.
Small center offsets are still misses at the unchanged tolerance. Increasing
the tolerance or relabeling unknown proposals is not an accuracy improvement.
Recorder/camera proof remains a separate requirement described in
[the ownership evidence specification](recorder_camera_evidence_requirements.md).

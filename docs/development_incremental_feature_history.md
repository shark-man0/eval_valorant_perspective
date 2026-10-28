# Incremental DEVELOPMENT feature and trial receipts (Issue #105)

This opt-in API builds on the existing accepted-source `FrameRecord`, split,
Exposure, physical leakage-group and HUMAN/pseudo/unlabeled contracts. It does
not register new media, infer physical-match identity, train a backbone, or adopt
a model into Production. It is independent of the center-readout experiment.

## Data admission and deduplication

`append_snapshot(previous, additions)` validates the complete combined dataset
before admitting additions. It preserves source, acquisition/epoch, native PTS
and rational timebase, encoded-frame and pixel hashes, ROI, extraction/Exposure
fingerprints, source acceptance, declared physical leakage group and split.
Exact extraction records are deduplicated. Changed encodings/ROIs are not silently
merged. A new source SHA is counted separately from a new declared physical group:
SHA equality identifies byte duplicates, not whether two recordings share a game.
The existing Registry/acceptance process must supply that identity and Exposure.
Cross-source duplicates with different hashes are conservatively grouped upstream.

## Current-identity feature cache

`DevelopmentFeatureCache` stores bounded tensor-only NPZ entries outside Git.
The key includes the entire accepted frame record, actual feature implementation
fingerprint (including its runtime prerequisites), Profile fingerprint, native
patch pixel hash and Map build scope. A source/epoch/PTS, pixel, ROI, Exposure,
Profile, feature or build change invalidates reuse. No calibration or identity
result is carried across frames by this cache. Corrupt/mismatched entries fail
rather than being treated as a successful cache hit. Only finite 1D feature
vectors of at most 512 dimensions are accepted; pickle is disabled and archive
members/uncompressed sizes are bounded. Callers still verify source media and
patch pixels before supplying those hashes.

```python
snapshot, receipt = append_snapshot(previous_frames, accepted_additions)
features, hit, key = cache.get_or_compute(
    frame,
    feature_fingerprint=current_feature_fingerprint,
    profile_fingerprint=current_profile_fingerprint,
    patch_sha256=current_native_patch_hash,
    map_build=current_map_build,
    compute=extract_current_patch_features,
)
```

An old cache is not permission to expose a protected source or ignore its split.
For semantic fitting use the existing HUMAN TRAIN validation; weak/SSL/pseudo
examples never become human-confirmed classes through cache retrieval.

## Start, compare, retain, reject

`DevelopmentTrialHistory.begin` creates an immutable trial receipt bound to the
source snapshot, code, prior default model and trial name. An interrupted trial
can be resumed using that exact identity and explicitly finished as failed.
`finish` appends a separate immutable result; repeating the same result is
idempotent, while replacing a prior outcome is rejected. No active/default
Production model pointer exists.

A development gain requires finite nonnegative integer TP/FP/FN, old-correct loss
and known-negative matches, the same input/annotation fingerprint and the same
positive denominator. Missing/different inputs or denominators are
`insufficient_evidence`. A measured candidate with no gain or increased unmatched
candidates is `rejected`; an exception is `failed`. A narrowly passing aggregate
can be `research_candidate` only: caller-side transfer, resources, annotation
scope, UNKNOWN safety and qualification remain additional adoption conditions.
No status authorizes Production adoption. The old model fingerprint is retained.

The current center experiment exercised 8/16/24 existing human-label budgets.
They are not a physical-match learning curve. Budget 8 cannot fit all four semantic
classes and fails explicitly; budget 16 has no measured fixed-input result and is
insufficient; budget 24 is rejected using the actual same-input 7/3 to 8/4
matched/unmatched comparison. The old history is preserved. Incremental caches
reuse 8 then 16 existing vectors when adding eight records each; a warm pass
reuses all 24 without invoking extraction. This demonstrates the repeatable
admit/extract/fit/compare/reject loop, not guaranteed recognition improvement.

Private receipts preserve native input bindings, learned weights, actual feature
cache and append-only outcomes. None are public repository assets. The broader
Issue #105 (new-video intake, dataset-wide physical identity, backbone retraining,
independent qualification and continued improvement) is not closed by this API.

## Verification

```sh
python -m pytest tests/unit/test_development_learning_runs.py -q
```

Tests cover exact extraction dedup, split leakage, feature reuse/invalidation,
cache corruption, changed-input/denominator false gains, immutable rejection,
interrupted-trial failure and retention of the old default model.

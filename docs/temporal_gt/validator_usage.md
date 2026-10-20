# Offline temporal dataset validation

Run from a checkout with the project and development dependencies installed. Store all real source, frames, labels, evidence and freezes outside the checkout. Nothing in this workflow invokes recognition, opens the sealed validation Pack, or grants permission to open a prediction holdout.

```sh
python -m scripts.temporal_gt.validate_dataset freeze \
  --dataset "$PRIVATE_DIR/dataset.json" \
  --freeze "$PRIVATE_DIR/freeze.json" \
  --public-report "$PUBLIC_DIR/readiness.json"
```

The dataset follows `schemas/round_end_temporal_dataset_v1.json`. Read the annotation contract before filling it. Every required field must be supplied; use explicit null/unknown when source evidence is missing. Exposure order is a journal sequence, not a fabricated wall-clock time. Source-wide exposure has a null event reference; bounded exposure carries its actual window. Historical image records lacking an original timebase remain evidence of exposure, not certified temporal GT. An unresolved exposure scope is not an identified physical event.

`freeze` verifies actual evidence hashes, source SHA and the shared unedited contract, template fingerprint/reference files and native frame encoded/pixel hashes where provided. It creates the freeze exclusively: existing freezes are never replaced. A valid but incomplete dataset can be frozen with readiness BLOCKED. Exit 0 means mechanical integrity passed; inspect `readiness` separately. Malformed or contradictory data exits 2 with a public rule name.

Retain the SHA256 of the freeze in a trusted separate location before any evaluation. Then validate without changing the anchor:

```sh
python -m scripts.temporal_gt.validate_dataset validate \
  --dataset "$PRIVATE_DIR/dataset.json" \
  --freeze "$PRIVATE_DIR/freeze.json" \
  --trusted-freeze-sha256 "$TRUSTED_FREEZE_SHA256" \
  --public-report "$PUBLIC_DIR/readiness.json"
```

The freeze binds the canonical dataset plus schema, annotation contract, readiness policy, validator and CLI bytes. Changes require a new explicitly versioned dataset/freeze and an honest exposure amendment. A developer who replaces both a dataset and its supposedly trusted anchor can defeat hash checking; this is not an access-control service or a semantic truth detector.

Obtain source preflight with the existing `scripts/e2e/preflight_round_source.py` and reference its hash. Keep source preflight distinct from recognition qualification. Decoder epochs are local to one actual acquisition; never join them by editing strings. Full temporal readiness also needs reviewed active Start → End → next Round continuity and actual witness images, not merely a monotonic whole-source PTS scan.

The summary is an explicit whitelist of hashes, anonymous counts, coverage and blocker names. Do not publish the input dataset, raw reviewer responses, frame indexes, detailed PTS, source paths or freezes containing private metadata. Check any manually written report separately. Public CI uses synthetic data only; the existing 38 dataset cases and Windows packaging checks remain in place.

Independent source curation can establish a narrow score-display bracket while the full End temporal dataset stays BLOCKED. Sparse contact sheets cannot establish pure negatives or prove that all events in the gaps were discovered. Once predictions are opened or a case is used for tuning, retain that exposure for every future method; never reset it to an unused holdout.

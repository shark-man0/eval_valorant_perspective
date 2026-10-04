# Private diagnostic image review contract

This tool belongs to the offline diagnostic path. It neither imports production detectors nor changes classifier thresholds, identity gates, values, facts, or events. Images, bundles, individual labels, private IDs, source paths, and timestamps remain local. Only aggregate evidence and reproducibility hashes may be shared in Git.

## Why this contract exists

An earlier review opened contact sheets while a worker was still regenerating them. The finished manifest then bound annotations to a different image order. Replaying the same immutable pixels exposed the mismatch; the apparent recognition errors from the original join were invalidated. A second hazard was treating SHA256 of PNG file bytes as SHA256 of decoded BGR pixels. Two differently compressed PNGs can contain identical pixels and different file hashes.

The tool addresses these provenance failures. It cannot establish whether visual labels are correct, whether a sample was previously exposed, whether sampling is unbiased, or whether a detector is safe. Those remain separate evaluation obligations.

## Seal before review

Use `scripts/seal_diagnostic_review.py` with the repository Python environment. The private input JSON has exactly one top-level field, `images`. Each image entry has:

- `id`: a unique opaque ASCII ID, case-insensitively unique; sheet filenames are reserved. Labels must fit the actual rendered header width; overlong labels are rejected.
- `path`: a local PNG source path, never published in the generated manifest.
- `decoded_bgr_sha256`: mandatory hash already binding the source ID to its pixels.
- `png_file_sha256`: optional additional hash of the encoded PNG bytes.

Pixel hash semantics are SHA256 of contiguous decoded uint8 BGR HWC bytes, using OpenCV color decoding. The generated manifest also binds the HWC dimensions. Shape and pixel hash jointly identify duplicate crops. Unknown or ambiguous hash fields are rejected.

```powershell
python scripts/seal_diagnostic_review.py seal --inputs <private-input.json> --destination <new-private-bundle>
```

All inputs are checked before creating the destination. Every image is read once; the copied PNG and generated contact sheet derive from those same bytes. Contact sheets show opaque IDs above the entire resized image; the ID header does not cover image pixels. Existing bundle directories are refused. The manifest is published last. A directory without a completed, verified manifest is not READY and must not be reviewed.

Save the returned `manifest_file_sha256` as the frozen review receipt outside the mutable bundle, along with the selection-plan hash. Do not replace a failed or completed bundle in place. Correct inputs and create a new versioned directory.

## Verify before viewing and before joining

```powershell
python scripts/seal_diagnostic_review.py verify --destination <private-bundle> --expected-manifest-sha256 <frozen-receipt-hash>
```

Verification checks the receipt, schema, pixel semantics, all image file hashes, decoded pixel hashes and dimensions, sheet file hashes, ID ordering, and exact sheet coverage. The CLI requires the expected manifest hash; a self-consistent regenerated bundle cannot silently replace a frozen review.

The worker sends READY only after successful verification. The reviewer waits for READY, verifies the saved receipt, opens the sealed sheets, and writes image-only annotations bound to that receipt. Verify again before joining labels to predictions. Prediction files and label files have separate hashes, and the join records both. Join by the decoded pixel hash and dimensions as well as the opaque ID; verify original full-frame provenance separately when crop-based labels are associated with state/context observations. If a receipt, mapping, crop, or sheet changes, invalidate the join and start a new review; never reinterpret old labels through a new mapping.

The receipt protects the bundle after sealing. The tool trusts the caller-supplied upstream ID-to-pixel mapping; it does not authenticate that mapping or prove that a prediction belongs to that image. Freeze the original selection manifest and its hash before sealing. An independent mapping audit at the join must compare ID, pixel hash, dimensions, and source-image provenance against prediction inputs. Swapped IDs with consistently recomputed hashes can otherwise be sealed successfully. Never recompute expected hashes merely to make a failed verification pass.

Opaque IDs alone do not make a review blind. Record prior exposure, selection by detector scores, reused blocks, and prediction exposure honestly. Do not call development or integrity audits independent holdouts. Hashes prove provenance, not statistical independence or semantic correctness.

## Verification coverage

Synthetic regression cases cover different PNG encodings with identical pixels, source regeneration after sealing, destination reuse, stale and ambiguous hashes, copied crop and sheet mutation, manifest mapping/shape/semantics mutation, frozen receipt mismatch, unsafe and Windows case-colliding IDs, and sanitized CLI failure output. No real frames or private assets are test fixtures.

A local CLI exercise sealed and reverified 24 previously immutable crops into four sheets with 24 unique shape/pixel identities. The bundle manifest SHA was `631bc1ac65d1ff32189d10a8e62460637f4bd5c1c30207bc75f1642dfe7fd869`. This is an integrity exercise, not new detector validation.

Verification after adding the tool: 18 targeted regression cases passed before the rendered-ID-width hardening; the final tool passed 19 targeted cases after that hardening; full pytest was 848 passed / 2 skipped (276.44 s) with the project UTF-8 and available E2E-pack environment. Ruff passed for `src tests scripts`; mypy passed for the existing `src` contract (86 source files); staged diff check passed. The skips were the fixed sibling-pack test and the legacy real-video anchor test without its dedicated environment setting. Production source is unchanged, so no new Clean E2E is claimed for this diagnostic-only phase.

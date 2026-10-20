# Bounded native source window inspection

`scripts/diagnostics/inspect_bounded_source_windows.py` creates a local receipt for
explicit rational source intervals. It reuses `VideoService.native_window`, hashes
the original video, decodes each requested interval in a separate temporary
decoder context, and selects frames using exact `Fraction` PTS comparisons after
expanding decoder endpoints outward by one representable float. A scientific
notation seek start is expanded to zero because FFmpeg's seek parser may reject
that spelling; exact rational selection still determines which frames enter the
receipt.

The receipt includes each decoder epoch, selected PTS/pixel sequence hash,
verified frame count, retained PNG bytes, source and implementation hashes, and
FFmpeg/ffprobe executable hashes. The decoder enforces the positive per-window
PNG byte limit while writing. Each frame's encoded bytes and decoded pixels are
rechecked before the proof is emitted. The source hash is rechecked after all
windows, and `native_window` performs its own terminal integrity check and
temporary-file cleanup.

The result applies only to the requested windows. It does not verify PTS or
pixels across the whole recording, establish continuity between windows, run
recognition, or qualify an event. It does not read labels, profiles, or GT data.
Use an output path outside the repository for local receipts; the CLI refuses to
overwrite an existing output file.

Within a checkout, the existing privacy guard requires an ignored output path.
The final receipt is created exclusively, so a file created by another run while
decoding is preserved. Tool hashes identify the executables used; they do not
claim complete operating-system/shared-library reproducibility or OCR quality.

Example:

```sh
python scripts/diagnostics/inspect_bounded_source_windows.py \
  --video /path/to/source.mkv --source-sha256 <64-lowercase-hex> \
  --window '1/3:2/3' --window '3/2:2' \
  --max-png-bytes 268435456 --output /tmp/bounded-source-receipt.json
```

## Recovery and verification scope

This extracts the input-only portion of research commit
`ca4b975a439fbf028e646125e3f27b0acd60ad87` without importing its experimental
reader stack. Main's decoder and source preflight are reused, not replaced.
Native PTS, geometry, source hash and temporary-file cleanup remain the existing
decoder contract. Tiny rational differences around an actual source PTS are
selected exactly, including when both bounds round onto that PTS as floats.

A local smoke on three previously exposed windows of the existing source
verified 24/12/48 selected native frames (84 total), terminal source/code/tool
hashes and the 256 MiB per-window limit. Peak retained PNG was 82,763,237 bytes;
the process took 12.48 seconds and peak Python RSS was 83,869,696 bytes on Mac.
These are source acquisition measurements, not reader throughput, independent
samples, Self Death candidates, qualification, or canonical E2E results. Raw
receipts and original source paths remain private. No images or source video are
copied to Git.

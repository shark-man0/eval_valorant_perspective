# Offline Timer formats and purchase-to-clock evidence

A colon-only Timer reader can reject a four-digit display with one low dot,
including cases where the configured outer ROI contains bright HUD outlines.
`TimerDisplayReader` keeps every successful strict colon reading unchanged.
For other frames it reuses the Result title-line proposal, requires exactly four
aligned digits and one small, low separator between digits two and three, and
rejects ambiguous punctuation and clipping. The literal dot spelling survives;
it is never rewritten as minutes:seconds or filled from adjacent frames.

Two explicit offline alternatives use the same proposal: the frozen Timer digit
assets through the existing single-digit reader, or the existing
`TesseractDigitsReader(psm=7, whitelist="0123456789.")` on original grayscale
pixels. The glyph threshold/class margin remain 0.90/0.04. OCR must reach 0.90;
no per-frame winner, expected value, phase label or template fitting is used.
In the fixed development comparison the glyph alternative failed to recover the
remaining case, so it is not the selected method. OCR is used only with the
explicit separator topology. Neither alternative installs a production reader.

The existing Round integration accepts typed, geometry-supported dot readings
only as additional **End-side display evidence**. It retains literal text,
Native frame witnesses, quantization and observed format changes. At least two
readings of the same format are required; increases and implausible declines
are contradictions. A format switch is recorded rather than interpolated. Buy
and next-clock rules still require colon readings, unchanged Score/Result
conditions and continuous Native acquisition segments. The Source/Profile,
reader-output and pixel bindings in component receipts must be regenerated
when the reader changes; old receipts cannot authorize modified observations.

The purchase-to-clock rules are shared by End-linked Lifecycle chains and
purchase observations in a window without an observed End. The latter are
explicit display hypotheses with no internal Start timestamp. They cannot
supply a missing End, repair a gap or bypass Score/Geometry checks.

## Reuse and verification

Continue using Source-only registration, frozen allocation, DEVELOPMENT access,
Native Decoder, existing component receipts, `round_lifecycle_evidence` and
`hud_failure_corpus`. New videos require allocation and Exposure registration
before observation. Preserve all Native ledger rows, including unanalysed ones;
missing OCR observations are not negative labels. Retain bound input/output and
implementation hashes, explicit OCR settings/assets, review packets and Exposure
records outside Git. The fixed-time sampling plan must precede new predictions.
Human source review and prediction-targeted review remain distinct.

`review_natural_windows` validates the bound Human packet, exact case IDs,
explicit review flags and separate End/Start answers. Only reviewed NO answers
enter each corresponding negative denominator. YES and UNKNOWN never become
negative labels. Supported hypotheses and unresolved candidates are reported
separately; hypotheses are not formal events. A short window can contain a
Human-confirmed Start while lacking enough preceding purchase evidence for the
pipeline. Extra context is a separate targeted acquisition, not an algorithmic
accuracy gain or an enlarged fixed-negative denominator.

The initial six source-reviewed windows include purchase and normal play.
They provide six End-negative and four Start-negative windows; the other two
are Start-positive. They do not establish Menu, death/spectator, overlay,
resolution/scale safety, population false-positive rates or independent
qualification. Private images, original videos, individual times, responses and
Profiles remain private. Source visual continuity remains UNVERIFIED. Canonical
GT, tolerances, production matchers, Ownership and formal event publication are
unchanged.

# REVIEW_FIXES — v2 -> v3

v3 addresses every remaining v2 issue that can be fixed from the existing source without inventing new visual evidence.

1. **State-edge precision** — Astral, smoke, and both buy-menu episodes now have explicit observed start/end brackets, and the evaluator enforces the detected interval edges.
2. **Exact presentation timestamps** — every reference frame now has a packet-PTS sidecar; validation regenerates and compares it against the source MP4.
3. **Ownership execution** — ownership intervals are no longer documentation-only; the evaluator requires them, including R1 self/dead ownership that v2 omitted.
4. **Derived Map/Zone assertions** — `zone_id` expectations are now actually evaluated rather than merely generated.
5. **Visual-observation assertions** — the three muzzle-flash observations are executable E2E checks.
6. **Discontinuity guard** — `must_not_span_temporal_features` is now enforced against runtime trace intervals.
7. **Ordering correctness** — ordering constraints use events matched to GT requirements; they no longer depend on a test-only `oracle_id` in production output.
8. **State over-detection** — coverage uses interval unions and exhaustive edge checks; a second oversized interval can no longer hide behind the best interval.
9. **Shot granularity** — synthetic semi-auto/full-auto/reload/switch fixtures define burst-start semantics independently of the ambiguous real burst.
10. **Map/Zone mechanics** — a synthetic calibrated map fixture provides an independent oracle for interior/boundary resolution.
11. **Japanese labels** — observed `A ロビー`, `中央ファウンテン`, and `Bメイン` are captured in a map-v3 integration overlay. Spectator labels are explicitly view-owned.
12. **Audio transport** — the source's three AAC tracks are verified and generated clips can be checked for track preservation.
13. **Confidence** — malformed confidence and source-vocabulary tokens fail; a reusable advisory confidence audit is included without pretending one clip can prove calibration.
14. **Trace schema** — Codex/runtime output now has a strict E2E trace schema and a one-command evaluator.
15. **Meta tests** — thirteen corruption modes are required to fail, including state-edge, ownership, derived-zone, visual-observation, discontinuity, confidence, and vocabulary corruption.

Issues requiring genuinely new recordings are not papered over; they are formalized in `fixture_requirements/real_video_gap_manifest_v1.json`.

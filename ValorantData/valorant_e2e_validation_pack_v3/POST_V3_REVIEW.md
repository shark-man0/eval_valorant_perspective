# POST_V3_REVIEW — residual limitations after v3

A second self-review found no remaining high-priority harness defect that can be resolved honestly from the current source alone.

## Still requires new real footage

1. **Perception-level continuous combat timing** — synthetic logic can validate reaction/duration math, but a clean uncropped real combat sequence is still needed to validate pixel-to-event timing end to end.
2. **Perception-level semi-auto/full-auto granularity** — the synthetic contract is exact, but the current real burst does not uniquely determine whether production should emit 1, 2, or 3 burst-start events.
3. **Independent Summit geometry truth** — synthetic geometry verifies resolver mechanics, while the real Summit polygons still need independently authored/surveyed map coordinates to measure geographic accuracy.
4. **Missing gameplay phenomena** — self kill/multikill, plant/defuse, flash, revive/teleport, overtime, and non-Astra remote-control views are absent from this clip.
5. **Statistical confidence calibration** — one source clip cannot produce meaningful reliability curves. Use a multi-fixture corpus before setting calibration thresholds.
6. **Semantic audio analysis** — intentionally out of MVP. Only audio-track transport is covered.
7. **Exact `utility_used` coverage** — the source shows effects/remote states, but does not provide a clean enough ability-charge/cast oracle to make every utility event exhaustive without inference.

These are data-coverage limits rather than defects in the v3 harness. They should be added as separate fixtures instead of widening or inventing Ground Truth in this clip.

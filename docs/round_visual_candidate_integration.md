# Development Round visual candidates

`temporal.round_visual.attach_round_visual_candidates(bundle)` is an opt-in
projection after `build_application_timeline`. It appends candidate records to
the bundle and its one-second rows. The original Round, Life, Camera, HUD, Map,
existing event, and formal output fields are untouched. The common timeline
engine remains the only state owner.

The start cue needs an observed purchase display followed within five native
seconds by a positive active display. Missing HUD or a disappearing caption
alone cannot start a Round. End cues are a result display onset or one-point
monotonic score increment. Repeated result display and nearby score support
are folded into one candidate; a new observed purchase cue resets the ending.
The candidate second is the first observed positive cue, not an exact internal
event time. The native observation IDs and sample digest remain attached.

`temporal.visibility_supplier.VisibilitySupplier(ProfileHudObserver(...),
tessdata)` is a separate opt-in wrapper for exact native pixel HUD visibility.
It uses the existing OCR visibility reader and preserves the base HUD readings.
Its BUY_MENU and TRACKER measurements remain advisory and cannot establish
Round, Life, Camera, or Map state. The existing Zone OCR ingestion path is
`zone_observations.normalize_zone_batch` followed by exact pixel
`zone_projection.attach_viewed_zones`; no unconfigured Zone OCR is inferred.

A same-input development comparison is saved privately at
`outputs/composite_round_PRIVATE/comparison_PRIVATE.json`. It replays three
existing admitted match bundles (`newfull001`, `newfull004`, `oldfull002`) and
compares candidate seconds with existing development event candidates. These
are not human ground truth, so one-second proximity is only a consistency
measurement. No new video decode, labels, GT, or formal qualification were used.

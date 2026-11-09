# Development Round visual candidates

`temporal.round_visual.attach_round_visual_candidates(bundle)` is an opt-in
projection after `build_application_timeline`. It appends candidate records to
the bundle and its one-second rows. The original Round, Life, Camera, HUD, Map,
existing event, and formal output fields are untouched. The common timeline
engine remains the only state owner.

The start cue needs an observed purchase display followed within five native
seconds by either a positive active display or the existing positively matched
`phase_absence_template` with valid scan, layout support, and no overlay.
A failed purchase presence match, missing HUD, or occlusion cannot start a Round. End cues are a result display onset or one-point
monotonic score increment. Repeated result display and nearby score support
are folded into one candidate; a new observed purchase cue resets the ending.
Continuity breaks, decoder failure, acquisition changes, geometry changes,
and timebase changes reset contextual links. The candidate second is the first
observed positive cue, not an exact internal event time. The native observation IDs and sample digest remain attached.

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

Cached-pixel HUD visibility readout for three admitted matches is in
`outputs/composite_round_PRIVATE/visibility_cached_PRIVATE.json`; it records
read success, NOT_ANALYSED, and candidate counts with exact native sample refs.
The existing `phase_absence_template` is not configured in the three compared
full-match bundles, so that new cue was verified in a contract test but did
not change their candidate counts.

The cached HUD visibility run read 36 Round1, 36 LifeCamera1, and 46
Control_newfull001 exact native pixel samples successfully (118/118, zero
NOT_ANALYSED); all were UNKNOWN for BUY_MENU/TRACKER. A second direct wrapper
run on 22 previously retained native samples read 22/22 successfully and found
two TRACKER candidates. Its wiring probe supplies an empty UI anchor map, so
BUY_MENU, which needs a measured close anchor, is not assessed there. These
counts show actual OCR transport and candidate output, not recognition
accuracy or negative ground truth. Both receipts stay private.

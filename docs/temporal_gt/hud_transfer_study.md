# Offline HUD transfer study

`scripts/diagnostics/diagnose_hud_transfer.py` compares training-frozen reference
banks with the unchanged pixel NCC matcher and a separate structural diagnostic.
It imports no runtime acquisition pipeline, identity rules or event publisher.
`geometry_consistent` is an experimental diagnostic; `semantic_label` remains
UNKNOWN and `production_qualified` is always false. It cannot replace runtime
calibration or release Round End / Self Death events.

Freeze a private plan before decoding or looking at new results. Bind accepted
DEVELOPMENT sources through the existing private registry/review plan and append
Exposure with existing APIs. Exclude evaluation candidates. Record source SHA,
native integer PTS/rational timebase, acquisition epoch and encoded/pixel hashes.
Keep previous evidence immutable and verify source/profile/configuration hashes.
Use existing bounded `VideoService.native_window`; no new decoder is required.

The five-source study fixed 16 interior duration fractions per source (80 new
witnesses), without predictions or semantic selection. Even ordinals from the
first four sources generated references (32 images). Odd ordinals and all 16
images from the fifth source formed the 48 development checks. The old 85
witnesses were a separate regression set, never new reference input. Source five
was already exposed development data, **not** an independent holdout. Each window
was <=0.1 seconds, retaining only one witness; continuity remained UNVERIFIED.

Call the diagnostic API with training images only:

```python
bank, reference_stats = freeze_bank(training_images, layout, existing_profile_raw,
                                    new_private_asset_directory)
frozen = bank_fingerprint(bank)
# Freeze source/frame roles and persist reference/input hashes before this loop.
rows = [observe(image, layout, bank) for image in development_check_images]
assert bank_fingerprint(bank) == frozen
```

Reuse `development_sources`, `append_exposure`, private output checks and
`write_private` around this API. This module is a diagnostic component rather
than another source/GT registry. Asset writes are exclusive and private. It does
not export a loadable runtime Profile; no production configuration is modified.

Reference generation reuses persistent-edge/orientation masks and the existing
training-only observed-reference proposal. At most three references per anchor
are selected by additional non-self raw NCC coverage, requiring at least three
supporting training images. Single and multiple NCC methods share the same
training cohort, masks, search regions and unchanged >=0.90 NCC threshold.

The structural branch proposes locations using normalized binary edge
correlation, then requires existing bidirectional unsigned-orientation soft
coverage >=0.90 (>=32 reference edges). This is a separately fixed experimental
cutoff; it is not an equivalent NCC confidence or accuracy claim. No rescaling
or post-result threshold tuning is allowed. Static support is defined by the
training persistence mask, not semantic annotation of static HUD elements.

Every method still needs existing capture/resolution checks and three fresh
geometric inliers. Multiple high scores at inconsistent positions cannot bypass
these checks. Blank, random noise, large shifts, missing structure and resolution
mismatches must not become events or verified negatives. Unmodified scene labels
(Menu, Spectator, Death, HUD hidden, overlay) remain UNKNOWN without evidence.

Compare the frozen previous Profiles separately from methods trained on the new
cohort: reference-data changes and matcher changes are different experiments.
Report per-source/per-anchor support, reference failure, observed-edge shortage,
structure mismatch, structure-supported NCC rejection and geometry rejection.
Generic edges are not proof of HUD presence. Record fit/replay time and process
peak RSS, source-five regressions and known-invalid transform challenges.

In the fixed study, frozen previous Profiles reproduced 18/85 and 19/85 but both
only reached 4/80 on the new uniform samples. New single/multiple NCC references
reached 12/85 and 12/85, with 9/48 each on development checks: multiple NCC helped
training only and did not establish more stable transfer. The structural
candidate reached 35/85 and 21/48; on source five it reached 6/17 old and 7/16 new,
versus previous observed-reference NCC 3/17 and 2/16. These are structural
consistency counts, not recognition accuracy or verified correct calibrations.

Retain the structural branch for further offline investigation only. Do not
adopt new NCC Profiles (old regressions remain), or connect the new Matcher to
production. Real false-calibration/crop/HUD-scale evidence and independent
semantic geometry validation remain missing. Round End additionally needs
compatible Score preprocessing, verified source continuity and qualified
lifecycle evidence; geometry counts alone cannot satisfy those contracts.

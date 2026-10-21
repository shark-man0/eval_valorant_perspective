# Private HUD geometry transfer diagnostics

Geometry is a prerequisite for ROI measurement, not evidence of self ownership,
life state, Round boundaries or source continuity. The runtime matcher, ownership
guards, resolution policy and qualification contracts are unchanged.

The temporal generator requires both stable intensity and persistent edges.
Different backgrounds can preserve HUD edges while violating intensity stability.
The existing diagnostic edge generator instead uses persistent unsigned edge
orientation, then evaluates unchanged raw masked pixel NCC at >=0.90. These are
candidate proposals; even three geometric inliers do not establish semantic GT.

A second failure occurs when contrast reversal erases structure in a pixel-wise
median. `training_medoid` now selects an observed training reference **before**
the contrast gate. Its selection excludes self scores and never reads validation
pixels. Masks, thresholds, search regions and runtime acceptance rules are not
relaxed. Flat/noisy input and unsupported strategies still fail closed.

The existing private candidate export supports this strategy explicitly:

```sh
PYTHONPATH=.:src python scripts/diagnostics/build_geometry_candidate.py \
  --video /private/development.mp4 --source-sha256 SOURCE_SHA256 \
  --layout /private/layout.json --approval /private/scoped-approval.json \
  --development-end DEVELOPMENT_END_SEC \
  --prior-diagnostics /private/prior-diagnostics.json \
  --output /private/new-geometry-candidate --template-strategy training_medoid
```

The default remains `median`. The candidate contains geometry assets only;
identity signals/readers are not inherited and production configuration is never
changed. Existing source SHA, configuration hashes, frozen candidate fingerprints,
private output checks and post-copy verification remain required. The approval
contract scopes offline experiments; it is not production qualification.
Source/profile mismatch aborts diagnosis rather than issuing a successful report.

For comparisons, freeze source IDs, roles, actual integer PTS/rational timebase,
acquisition epochs, encoded/pixel frame hashes and profile fingerprints first.
Use identical frames, thresholds, search areas and runtime calibration checks for
each strategy. Do not combine frames into a fabricated continuous stream. Record
training and development-check results separately, including regressions. Already
prediction-exposed development frames are not independent qualification data.

A bounded five-source investigation reused 85 retained native witnesses from
previous probes. Baseline calibration was 0/85, edge/median proposals 18/85 and
edge/observed-reference proposals 19/85. On the source excluded from reference
selection, the latter regressed from 4/17 to 3/17. Consequently this change adds an
**offline diagnostic option**, not a demonstrated portable production calibrator.
The witness selection is biased toward earlier diagnostic neighborhoods, not a
representative whole-match estimate. No recognition accuracy is claimed.

Remaining work: stable top-bar structure is scarce; changing timer/portraits and
scene background need separate structural support. State-specific semantic
validation (including Spectator, Menu, Death and overlays), unmodified negative
geometry evidence, HUD scale and independent capture-crop evidence remain open.
All uncertain semantics/continuity stay UNKNOWN/UNVERIFIED. Runtime resolution
mismatch remains rejected; normalized coordinates alone do not qualify resizing.
Keep private frames, Profiles, timestamps and source identities outside Git.

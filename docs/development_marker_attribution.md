# Exact-frame marker attribution review

These Map/Visual helpers are development-only. A measured portrait, a human
marker role and the currently displayed camera state are separate evidence.
No helper emits a qualified owner, Self Position Fact, Player Event or score.

`freeze_native_sample` retains source ID/SHA, acquisition/native epoch, integer
PTS, rational timebase, encoded/pixel SHA and frame dimensions. No FPS timestamp
substitution is accepted. `assess_marker_attribution` compares a frozen candidate
against human-marked centers/roles on that exact image. Predictions retain their
method fingerprint and a canonical payload digest; callers must fingerprint the
code, profile, reference content and conditions before inference. Blinded human
roles bind the sampled image rather than one recognizer's preferred position.

The result distinguishes reviewed SELF, TEAMMATE, SPECTATED, OTHER, UNKNOWN,
unreviewed, no candidate and explicit context rejection. An unannotated location
is UNKNOWN, not a negative. Overlapping annotation tolerances do not select a
role. A view-state label never substitutes for a marker-role annotation. Annotation
tolerance is a reviewer declaration, not an independently measured error bound.

`summarize_marker_attribution` measures one frozen method at a time, rejects
duplicate source/native observations and excludes authoring/triage from evaluation.
It reports teammate candidates **if interpreted as self**, separately from formal
misattributions (zero). The output retains the ownership-UNKNOWN denominator;
candidate-role accuracy is not account ownership accuracy. Independent episode
counts require explicit human episode IDs. Source count, acquisition epochs and
frame count do not establish independent physical episodes. Map/Zone error stays
unmeasured unless a separate coordinate/geometry review supplies it.

The fixed private failure reproduced a cross-recording role reversal: one library's
positive portrait selected a teammate, while the actual recorder portrait matched
another library's negative control. Both were returned with UNKNOWN ownership.
Fresh trackers reproduce the selection, so temporal continuity did not cause it.
Neither maximum appearance score nor reusing positive/control semantics can
establish who owns the camera. The private example was used for reference
authoring and must not enter an independent evaluation denominator.

`AnnulusValidatedAppearancePool` is a separate opt-in shape veto, configured with
`appearance_pool_annulus_v1` and explicit `unassigned_visual_candidate` scope.
It uses the existing Portable tracker's annulus/texture criteria without lowering
appearance thresholds. The existing default pool is unchanged. Ring support is
an appearance cue, not self ownership; no replacement is selected when a texture
candidate is rejected. Results from one reviewed image are insufficient to make
this a cross-recording default.

On the fixed1,330 observations from ten DEVELOPMENT recordings, the default
pool's full output reproduced with zero differences. The extra veto reduced ROI
candidates243 to95 and Map candidates143 to70; calibration stayed580 in both
arms. These are retrieval changes, not measured correctness improvements. The
one reviewed teammate example is rejected, but it was already exposed for triage
and reference authoring. Other lost/retained targets are unreviewed, so this
experimental veto is not selected as a new global default.

## Version-compatible projections

`gate_map_version` is an opt-in boundary after raw development recognition. It
requires exact asset bytes/SHA and map ID, plus source/acquisition-bound build
evidence. Unknown builds, missing evidence, changed reference bytes and different
declared builds withhold top-level Map position, Zone, segment, speed and candidate
transitions. The raw fit is retained under `unverified_geometry_candidate` for
inspection, explicitly unusable as a version-compatible position. Downstream
analysis must use the returned top-level values, never bypass the gate by reading
that diagnostic copy. Existing raw studies remain reproducible and are not
retroactively described as version-qualified.

Identical **evidenced** build declarations only establish a compatibility candidate.
They do not qualify geometry, the evidence recognizer, recorder ownership or a
world-coordinate transform. Evidence artifact hashes are traceability anchors;
callers still have to verify the meaning/scope of the evidence. Build strings are
compared exactly; recording dates, ingest dates, absent update notes and current
download timestamps never imply compatibility.

See [official map reference review](map_reference_version_review.md). Production
Map registries, recognition thresholds, HUD code and canonical GT are unchanged.
Keep all frames, roles, Profiles, aliases, PTS and individual positions private.

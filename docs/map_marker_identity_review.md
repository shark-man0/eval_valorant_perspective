# Map marker identity review

**Decision: NEED MORE EVIDENCE.** The map pipeline aligns the static Summit minimap, but alignment supplies map geometry only. The effective runtime profile has no configured self-marker detector, so there is no player point to pass to the zone resolver. A nine-case replay confirms this distinction.

## Evidence

The fixed replay contains 1,026 snapshots. This audit selected its nine calibration-accepted cases. Replaying the production `MapTimeline.calibrate`, `PixelMeasurementExtractor.measure`, and `MapTimeline.resolve` paths reproduced all nine calibration statuses and saved map diagnostics exactly. All nine had accepted geometric calibration and emitted `map_marker_missing` plus `map_location_unresolved`. The active profile had no self, ally, or enemy HSV marker specs. Thus the pixel extractor returned zero components because no detector was configured; physical marker absence was not measured.

The baseline analyzer commit is `5b7a7e26c670cfc999839dcecd42c77065d19a24` with `git_is_dirty=false` and implementation digest `5ae7e89efbb32568da81b6d92283fcc15a606d34924bb1fdf762bebc559c553f`. The source video hash is `71d58558559d6f578433ce9f234bf176f76fd5a86657dbfe3eba1e7d36136b06`; fixed replay manifest hash is `f8267c437f95cb534c06d80a459961409323688f9b7a76a728b719b0350e74f1`. The recorded HUD fingerprint is `e7987bf758eb2dca8211149b6fde9bddcb04a07997f1fb66cb38e8c677580e57`. Reconstructing the effective visual profile exactly reproduced fingerprint `a17e8043bf81515b4fe4ea674ab2011acb6c3e49ddc51777ddeb8d3e8871740e`. It contains Summit selection and minimap ROI `[20,48,475,475]` at 1920x1080, with no marker HSV specs or client build.

The accepted calibration support ranged from 35 to 47 inliers, X coverage 0.84 to 0.89, Y coverage 0.52 to 0.96, and confidence 0.574 to 0.759. The reference asset SHA256 is `6ccdc19605b8885ef8d51761f872630ef6122266bcf5bb0d318fcc7661d1f3b6`; its authored map-mask box is `[38,18,430,422]` within the ROI. These results establish static-map alignment under `summit_coarse_2026-09-28_v3`; they do not establish marker ownership.

## Why no marker was evaluated

`AppSettings.visual_profile_path` defaults to an empty string (`settings.py:38`). The real-video runner accepts optional `--visual-profile` and leaves the path empty if omitted (`tests/e2e/run_real_video.py:54,83-84`). `load_visual_profile` returns `{}` for a blank path (`visual/runtime.py:339-342`) and does not search for an installed profile. Bootstrap then adds the selected map and minimap ROI (`bootstrap.py:120-129`), but does not add `minimap_colors_hsv`.

The pixel extractor gets each side's HSV component spec from that profile (`visual/pixels.py:305`) and `_components` returns an empty list when the spec is empty or lacks `lower`/`upper` bounds (`pixels.py:31-39`). The map timeline currently emits `map_marker_missing` whenever the self coordinates are null (`visual/map_pipeline.py:92-95`); this does not distinguish missing configuration from a detector that ran and observed zero candidates. The resolver only receives a controlled-player point when the minimap coordinate exists, ownership is safe, and calibration is accepted. Calibration alone cannot supply that point.

The profile inventory found no production marker profile in generated HUD profiles or E2E output. `config/visual_runtime.example.json` is deliberately unvalidated and empty. The only nonempty repository examples are synthetic tests: a generated green component in the unit test and a magenta dot painted onto the Summit reference in the integration test. They exercise code, not an actual client marker. The profile mechanism is supported; there was no real profile asset for this runner to load.

All nine cases also report `client_build_unverified`. Calibration adds this diagnostic when no observed client build is supplied (`maps/calibration.py:337-360`), but `_profile_failure` does not reject a missing build (`calibration.py:495-507`). It is a provenance warning separate from marker-profile availability and did not block these calibrations.

## Diagnostic improvement

A future diagnostic-only change can expose `marker_profile_status` (`unavailable`, `configured`, `invalid`) and `marker_measurement_status` (`not_evaluated`, `evaluated_absent`, `evaluated_unique`, `evaluated_ambiguous`). With no self spec, report unavailable and not evaluated. When a valid configured detector actually runs, report whether it returned zero, one, or multiple candidates. Keep current zone diagnostics, ownership gates, calibration, and resolver behavior unchanged. This separates setup absence from image evidence without creating a location.

## Evidence needed to identify the controlled-player symbol

The nine calibration successes cannot label any map icon as the controlled player. The reviewed crops contain several icon families, so matching color or a ring alone could select a teammate, a ping, or an ability marker. The next experiment should collect current-client full-screen frames with the controlled-player icon independently identified from its UI appearance, plus visually similar teammate, enemy, spike/ping/camera, label, absent, occluded, and ambiguous controls. Freeze appearance labels before scoring; compare contour, interior fill or portrait texture, ring thickness, cone/wedge, orientation, and edge support, using color only as a supporting feature. Evaluate on a disjoint recording and keep ambiguous cases unknown. Do not infer the role from a color range, calibration result, or predicted map position.

The aggregate evidence and diagnostic-only status proposal are in [`map_marker_runtime_evidence_v1.json`](map_marker_runtime_evidence_v1.json). Private crops and per-case metrics are excluded.

# Map marker evidence review

`NEED MORE EVIDENCE`; production unchanged. This is the next downstream diagnostic after Ability/Spectator exposed the Report exclusion dependency.

The existing clean E2E contains 4,730 HUD observations. Only 146 pass ownership eligibility; map calibration accepts 45, fails 101 and skips 4,584. All 45 accepted calibrations have `marker_missing`; no observation has a location text or zone identity. Calibration failures comprise 68 insufficient alignment confidence and 33 missing full-map evidence.

The recorded settings fingerprint exactly reproduces the runner payload containing HUD layout/assets and manual map `summit`, without an optional visual-profile argument. Initial visual profile is empty. Bootstrap subsequently injects map selection and HUD minimap ROI, so runtime profile is augmented rather than entirely empty. It still lacks `minimap_colors_hsv`; the pixel extractor therefore generates no self/ally/enemy color candidates. This is a concrete configuration-path blocker, not evidence that visible markers are absent.

A fixed diagnostic white mask (HSV S<=55, V>=210, 3x3 opening, component area 8..500) finds components in 42/45 calibration-accepted crops and 92/101 failed crops; median count is three in both. Compact components appear in 38/45 versus 76/101. Median edge density is 0.0859 versus 0.0846. These observations include map lines, labels and multiple icons; calibration status is not a self-marker identity label. Visible ring/cone-like shapes alone do not establish controlled-player ownership.

The source gives marker confidence 0.92 only when BOTH `profile.validated=true` and north-up calibration is true; otherwise 0.6. The current profile is unvalidated, so the 0.92 condition is not active. A future validated profile still needs independent per-component ownership evidence: declaring it validated based only on white-component statistics would not supply that evidence.

Next evidence requires minimap crops paired with sufficient full-frame context, independently annotated visible/absent/occluded/ambiguous self-marker ownership, visually similar nonself/map-icon controls and recording-separated holdout. Expected location, calibration output, GT times/states and downstream zone predictions cannot provide detector identity. Current ambiguous observations remain unknown. Report safety audit proceeds first; no location-confidence threshold is relaxed.

Reproducibility: video SHA256 `71d58558559d6f578433ce9f234bf176f76fd5a86657dbfe3eba1e7d36136b06`; HUD profile fingerprint `372bf43ab9c443e3d54bd46b3b5d51626aa1ebf0f8d8a68edeb76e5aff826453`; E2E analyzer `2650d09b90df50d6a004dbe5d849fc60432af33b`, `git_is_dirty=false`. No images, per-frame IDs, model assets or raw video are shared.


Additional full-context audit: 28 paired full-frame/minimap observations (12 calibration-accepted and 16 failed) show first-person scenes and unobscured minimaps, but multiple candidate marks remain. No marker is independently assignable to the controlled player in this audit: 28 ambiguous, zero confirmed absent or occluded. A 17-frame neighboring corridor sequence contains little local camera translation and moving third-person characters; it provides no independent ownership correspondence. These labels describe audited evidence limits, not universal marker absence. The available workspace contains only one raw recording, so recording-separated holdout cannot currently be constructed.

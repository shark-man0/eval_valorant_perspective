# Downstream Score, phase-title and Map evidence review

## Reproducibility

This diagnostic continues after owned HP fact source `3e9df3dab16d6dce83f3973f0386638d11286c0c` and its Clean E2E `20261004T130701Z-bb7e94b4`, `git_is_dirty=false`. Video SHA256: `71d58558559d6f578433ce9f234bf176f76fd5a86657dbfe3eba1e7d36136b06`. HP profile sidecar SHA256: `8e764d6eb2b7a6a8ce6a5f144300bdf809f16f9dcf2b689ac659333c2265b615`; complete asset fingerprint: `e7987bf758eb2dca8211149b6fde9bddcb04a07997f1fb66cb38e8c677580e57`.

The native phase-title and Map probes use the preceding HP-reader run, analyzer `4f142acd50eebf6d956893fe3f9c47b4b9bbda7b`, Clean E2E `20261004T124214Z-d332e9b4`. The later HP-fact run is exactly equal in observations after removing only the reserved HP reader confidence. Images, reference assets, frame identifiers, individual timestamps and detailed dumps stay private. The companion metrics contains aggregate results and evidence hashes only.

## Score value versus whole-field evidence

A complete ten-class, frozen .90 NCC/.04 competitor-margin parser was evaluated after independent blind pixel transcription on 46 new role crops, two fields each. It accepted 31/46 ally and 38/46 enemy values correctly, with zero wrong accepted values and 23 UNKNOWN fields. All fields were readable or partly contaminated but still readable; there were **zero genuinely absent/unreadable negative fields**. Therefore 69/92 correct acceptances establish role-font opportunity, not absent-field safety. The samples are now exposed development evidence, not a reusable blind holdout.

The frozen parser hash is `4e29f1b90a64f299932045acb983379fdca074b85c0e14e46e7b6d10ee6d8c0c`; independent labels and pre-label predictions are hashed in the metrics. No allowed-score whitelist, GT, expected state or timing is used. A previous 96 border-control test rejected every patch, but those easy controls do not replace hard negatives.

Two numeral-excluded enemy-header groups recur in 10/12 internal training and 10/12 remaining even samples at .90. The same header also accepts 20/24 synthetic foreign-font insertions; it identifies a panel scaffold and cannot authorize a numeral by itself. Ally panel context remains unconfirmed.

A literal wider field includes background/HUD ink: only 7/24 enemy and 17/24 ally training fields have exactly one unfiltered foreground component. Nine training-derived visible three-digit compositions retain one component in the narrow field and three in the wider field. For middle digits 1/2, the narrow input is byte-identical to an accepted genuine one-digit crop. This is an observable field-coverage failure, not a numeric threshold problem. Erasing all outer ink also makes the wider input indistinguishable from a genuine single digit: identical pixels cannot support different detector decisions. Such erased evidence must not be described as an observable contradiction.

Decision: **NEED MORE EVIDENCE** for Score activation. Continue bounded training-only whole-field extraction diagnostics; do not lower .90 or reinterpret UNKNOWN as zero. Independent complete multi-digit, partial/occluded, headerless and foreign-text controls are required before adoption.

## Actual purchase-title matcher and native replay

An isolated copy of the private HP profile adds only a fixed full Japanese purchase-title template. All old anchors, readers, signals and asset bytes are preserved. The decoded reference hash is `2806bf04b2ceebdde1965fe0bf31904fb95c65ac7eadf026fe36d83d9d76ecea`. The actual loader reports no diagnostics. Runtime `HudTemplateProfile.detect_signals` crops the configured centre-banner ROI and normalized title subregion, then invokes TM_CCOEFF_NORMED on the fixed 393x72 patch at .90; there is no alignment search.

The earlier prototype searched the full banner. Actual API versus prototype decisions agree in all 118 training/blind samples; all 118 exact decoded frame hashes and all 118 crop hashes match. Actual training retains 9/10 visible purchase titles and rejects 62/62 other samples. Blind role confirmation retains 4/6 visible purchase titles and rejects 40/40 negatives, including TEAM ACE, a red notification, expanded-map text and shop text. Same-recording episodes are correlated, and this is not recording-separated generalization.

One clearly visible blind title has NCC about .756 against a busy background; another scores about .896. A rejected match is **not checked title absence**. The template is a presence-only diagnostic candidate.

On 4,081 native frames, 344 title matches exceed .90. All occur on existing UNKNOWN observations. The legacy generic edge/contrast banner is true in 2,852 frames: 327 overlap, 2,525 are generic-only, 17 title-only and 1,212 neither. Thus generic banner contrast and literal title evidence have different meanings. Twelve illustrative native hits were visually reviewed; this is not an accuracy estimate for all 344 hits.

All 4,081 score pairs are unknown; the existing score-stability enrichment therefore accepts **zero** of these title hits as pre-round context. Buy-phase flags and round-start events remain zero. Existing 166 live classifications and 130 owned HP values are unchanged. No experimental profile is activated in production. Preserve the separation between literal observed title, confirmed game phase, checked absence and ownership. Do not synthesize ScoreStable or round-start to fit evaluation assertions.

## Map configuration versus self-role identifiability

The actual wrapper omits `--visual-profile`: settings load an empty profile, then bootstrap supplies the manual map and HUD minimap ROI, without `minimap_colors_hsv`. Consequently all self/ally/enemy candidate arrays are empty by configuration. Manual map selection and geometric registration do not provide self ownership.

Among 166 eligible observations, registration accepts 49 and rejects 117: 67 alignment-confidence failures, 38 missing full-map evidence and 12 insufficient-feature failures. No marker is produced even for the 49 accepted geometries. The 3,915 ineligible observations remain excluded from Map work. These numbers supersede the older 146/45 ownership/calibration counts in the initial Map review.

Training review uses 32 rank-uniform even eligible-index crops; 32 odd crops are reserved and remain unopened. Portrait/ring-like components and pale view cones occur on multiple markers. No consistent independent controlled-player outline, arrow or cursor is established. Runtime currently only thresholds profile-specified HSV and checks connected components; it contains no shape, heading or viewport-centre self classifier. North-up calibration affects confidence, not identity; map anchors intentionally exclude coloured player markers.

Multiple self assignments fit the available cues equally well. Adopting an arbitrary colour, portrait, cone or map-centre rule would manufacture ownership. A documented agent-independent local-player UI cue or a paired resource linking the controlled view to a minimap icon is required. No self HSV range is fitted, no odd sample is opened, no location confidence is relaxed. Keep Map ownership unknown and continue other measurable value blockers.

## Verification and next experiment

No production source or active profile changes in this diagnostic checkpoint. Reuse the current source verification: 830 pytest passes, two existing environment skips; Ruff, strict mypy (86 files) and diff check pass. Current committed-source Clean E2E remains 22 passed / 56 failed / 4 not evaluated, negative 20 passed / zero failed. An unchanged source does not require another full real-video run.

The next information gain is whole-field Score extraction and per-role Ammo font/field completeness, plus a bounded design audit of literal phase-title evidence. Preserve HP/Ability/Weapon plus checked Spectator exclusion, current-frame values, .90 identity thresholds and negative safety. These are active follow-up experiments, not approval requests or silent contract changes.

# Development Map quality audit

Run scripts/map_learning/audit_quality.py with --before, --after, and --output.
Use frozen private portfolios for the same recordings, native observations,
timeline, and Zone geometry.

The audit lists removed observations, current-outline diagnostics, retained
observation changes, lost measured edges, suspicious displacement, track-label
changes, and three deterministic unreviewed controls per recording.

Automatic flags require semantic review to establish wrong ownership or an
identity switch. A normal control means no automatic edge flag was observed.

Optional review JSON has a rows array. Each row binds index, sample_ref,
report_sha256, reviewer (HUMAN or AI_VISUAL), and role (SELF, NON_SELF, UNKNOWN).
A SELF review can supply center_frame_px and map_reference_px. Reference
coordinates require exact map_id and reference_sha256 values. Center and Map
errors have separate reviewed denominators. UNKNOWN counts only as reviewed.

A hidden marker cannot provide an independent center or owner label. Projection
round-trip residual measures consistency. Absolute error requires independent
Map coordinates or landmarks. Missing evidence is reported as unmeasured.

The existing portfolio importer accepts corrected quality portfolios and keeps
previous result generations available for application comparison.


Withdrawn observations can be reviewed against the corrected report hash. Their
original predictions are recovered from the explicitly supplied before-portfolio.
Review statistics are stratified as HUMAN_WITHDRAWN or AI_VISUAL_WITHDRAWN,
and never counted as current selections.

prepare_quality_review.py restores native pixels for the frozen suspicious edges
and controls after catalog and source-hash checks. It records missing pixels and
does not substitute approximate frames.

compare_canonical_quality.py joins the legacy 25-match manifest to the canonical
36-match timeline at the same source SHA and rational native timestamp. It uses
the canonical pass's evidenced own-live eligibility. Both abstentions are retained
in the denominator. Agreement at eight reference pixels is a descriptive
comparison threshold. Same-clock observations with different full pixel hashes
are reported separately from identical-pixel observations.

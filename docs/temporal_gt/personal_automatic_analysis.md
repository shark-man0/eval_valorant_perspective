# Personal DEVELOPMENT automatic candidate analysis

`scripts/diagnostics/analyze_personal_candidates.py` reuses the private source
registry, Exposure journal, VideoService, RealHudAnalyzer and ReportHeader.
Human annotation is not a prerequisite. Only accepted DEVELOPMENT sources with
DEVELOPMENT exposure are selected; prospective evaluation sources are excluded.
The frozen registry/allocation anchors are checked by the existing review plan.

Run outside the repository with private layout/template/Report assets:

```sh
PYTHONPATH=.:src python scripts/diagnostics/analyze_personal_candidates.py \
  --session /private/existing-review-session \
  --output /private/new-automatic-analysis \
  --layout /private/hud-layout.json \
  --templates /private/existing-templates.json \
  --report-profile /private/existing-report-profile.json \
  --step-sec 5 --max-frames 2000
```

The output directory must be new and outside Git. JSON is exclusively created
with restrictive permissions. At most 16 temporary original-resolution JPEG
samples are retained per batch, then deleted. A maximum of 2,000 samples per
source is enforced; an over-budget source fails rather than silently truncating
the timeline. Sparse samples have actual source integer PTS/timebase and image
hashes, but are lossy inputs, not lossless native GT evidence. Source SHA and
model/assets fingerprints are verified; no model thresholds are changed.

The immutable plan is journaled as prediction exposure before each source is
analyzed. Existing source-only human receipts remain intact and retain their
original order. Subsequent prediction-exposed reviews cannot pass the existing
blind GT import gate. Prediction runs and human GT must not be combined to claim
independent source review.

Consecutive matching observations are grouped as display runs. Multiple support
frames are not multiple physical events. Identical repeated PTS rows are
suppressed; conflicting duplicate PTS or mixed source/timebase inputs fail.
Report reappearance links to the preceding candidate as a possible redisplay;
it does not establish a new Death. A Report witness does not establish self
identity, victim/killer roles, qualified Report absence or an alive/dead bracket.
These Self Death candidates therefore stay UNKNOWN. A semantic result-template
match is only a Round result-display candidate, not a qualified End boundary.
Score changes, EOF, and Report alone cannot generate a Round End candidate.

Unmatched and unscanned portions are not negatives. Continuity stays UNVERIFIED,
including between sparse samples. Candidate counts do not measure precision,
recall or physical Death counts. Formal events are empty, approved GT and
qualification are false, and production is unchanged. Diagnostics record missing
calibration and the observations needed to investigate transfer failures.

For closer analysis use the existing bounded native source acquisition API on
explicit candidate neighborhoods, retaining independent real acquisition epochs
and source/pixel hashes. AI analysis remains a provisional interpretation.
Source-backed human review may later resolve semantics, but does not stop the
automatic development workflow.

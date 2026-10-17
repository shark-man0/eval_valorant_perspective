# Self Death: separate caption localization from Report calibration

Status: **source-backed reader/provenance fix; independent qualification and
canonical FAIL reduction remain incomplete**. Start branch
`9f65f31c0da5d38375a4a145b2dd1562300c194c`; fetched main
`7e480c2f2f7f49aea73e1541d065d78881d2f11c`.

## Problem and evidence

The five remaining later-source rifle-discovery groups were reviewed in their
fixed order. They show nonself deaths while spectating, recording-player kills,
or already visible reports; none supplies a new qualified self-death episode.
One also reveals a reproducible localization defect: its taller report places
the static self-referential caption above the current search rectangle.

The original caption reference is 18 by 87 pixels and contains only the static
text, excluding killer/player names. At the affected source image, the exact
same reference matches `[1636, 245, 1723, 263]` at NCC **0.950438**. The old
search begins at Y=270 and cannot contain those pixels. The ordinary report
example matches at Y=354 and remains inside that search. No threshold change,
new template, OCR fitting or GT is needed to establish this defect.

Read-only localization on all five fixed images distinguishes the hypotheses:

- Reference mismatch is not the cause in the affected image: unchanged NCC
  exceeds the unchanged 0.90 floor when the pixels are searchable.
- The current search geometry directly excludes the positive caption.
- Merely changing the shared search rectangle would also change the input shape
  expected by the independently calibrated generic Report-header model. Those
  are different measurements and should not be coupled.

The images were already reviewed development/discovery contexts, not blind
holdout. This observation does not establish every possible report layout or
qualify a whole source/subject recognizer.

## Implementation and compatibility

`SelfDeathImageRecognizer` accepts an optional independent
`report_presence_search_roi`. Caption search still locates the self-referential
text; generic header corroboration uses its own unchanged calibrated crop.
Legacy callers default to the previous shared rectangle. Explicit geometry is
validated against source bounds and the presence model's original input shape,
and is included in the effective reader fingerprint. No array is resized or
reinterpreted to fit another rectangle.

Experimental profile v3 makes this distinction explicit. It adds
`report_presence_search_roi` while retaining the existing assets, model and
thresholds. The source-2 development config searches the caption above the old
top bound but keeps the old presence calibration rectangle exactly. Profiles
v1/v2 retain their prior strict field sets and default behavior. The shared
Python runner loads v3 and preserves both rectangles when cloning a recognizer
for each independent native window. No Windows/Pi-specific reader is added.

Every unique caption reading also retains its actual `report_match_roi`.
Ambiguous/missing matches retain zero support and no match box. Typed witness
transport uses the original onset's actual box and score, never the later
confirmation or the entire search rectangle as precise evidence. This matters
when a broader search includes other HUD regions: independent pixels must be
the actual matched caption, not the search area. New recorded boxes must lie
within their configured search. Older artifacts without a match box retain
their explicit coarse search provenance; it is not relabeled precise.

The image-session adapter checks self-caption witnesses against this exact
measured box and generic-header witnesses against their separate calibrated
rectangle. Original candidates remain UNKNOWN/unqualified. Public HUD/Event/
RoundPackage/SQLite schemas, source ownership, confidence semantics, 0.90/0.65
gates, temporal horizons, discontinuity policy, GT/assertions and Full sampler
are unchanged. No v3 profile or qualification is installed in the application.

## Tests and real-source comparison

Synthetic tests reproduce a caption above the old crop: legacy search finds no
episode, while independent caption search plus unchanged presence calibration
preserves the true onset through later header corroboration. They also cover
duplicate-caption ambiguity, invalid calibration rectangles, v3 loading and
window cloning, exact onset ROI transport, malformed match boxes and legacy
artifact compatibility. No generic header can open a self-caption onset.

Final related suite: **168 passed in 51.04 seconds**. Ruff and mypy (145 files
including the runner) pass. These tests prove code contracts, not independent
real-video qualification.

The five actual source images were freshly processed with the current code and
both v2/v3 configurations, using the same assets/dependencies and no future
result-based selection. In 10.935 seconds, the affected image changed from
zero caption support/no box to 0.950438 at its actual box. All other four
caption results were unchanged. Every isolated reading remained unqualified,
with no prediction or formal Event. Isolated component detection is not a
temporal death detection or canonical PASS.

Continuous regression then freshly processed 896 native cached rows:

| Fixed input | Frames | Previous diagnostic episodes | Current | Delta |
| --- | ---: | ---: | ---: | ---: |
| match_001, legacy v2 profile | 171 | 2 | 2 | 0 |
| match_002, two known episodes plus three controls, v3 profile | 725 | 2 | 2 | 0 |
| New predictions in the fixed negative windows | Included above | 0 | 0 | 0 |
| Source-blocked frames | 896 total | 0 | 0 | 0 |
| Formal Death Events | 896 total | 0 | 0 | 0 |

Every original source PTS/pixel binding, diagnostic status and episode onset/
confirmation pair was compared and matched exactly. Source/config/dependency
terminal checks passed. match_001 recognition took 201.702 seconds (230.259
wall; peak RSS 94,175,232 bytes). match_002 recognition took 772.299 seconds
(934.465 wall; peak RSS 101,421,056 bytes). Timing gain is not claimed.
The high-caption component image is separate from these continuous cases:
no new continuous positive episode is inferred from its isolated match.

## Reproducibility and remaining qualification

Private investigation records include the fixed five-frame selection and source
images, `remaining-rifle-caption-localization.json`,
`separated-caption-presence-freeze.json`,
`separated-caption-presence-component-comparison.json`, and
`separated-caption-presence-continuous-plan.json`.

Fresh continuous result digests:

- `separated-caption-presence-legacy-match001.json`:
  `49c7b81e2649d0ab0f1bed28b5baf24dedbad6c5f93b126273f66b6c6f85f4a8`.
- `separated-caption-presence-v3-match002.json`:
  `a7172b14812b2416c054a3a8f117a27f8e1b83f89ea7f42ec090bae5f7c129b0`.

Reader bytes changed, so their effective fingerprints changed and old
qualification is not reused or re-signed. Reference assets, original source
images and prior reports remain intact. No private images, profiles, player
names or GT are committed.

Remaining: reserve and review independent positive/negative subject/temporal
evidence for the exact new reader/configuration, including moved-caption layouts
and non-Report text controls. Supply a genuinely qualified source/frame provider
at the existing session entrance and complete application/resume integration.
Only then is a new same-contract canonical targeted/sampled comparison valid.
No additional video is made a prerequisite by this fix, and no Full E2E was run.
Adopted 23/55/4, archived Strict candidate 28/50/4 and the separate timing-policy
comparison remain distinct historical results. The overall goal is incomplete.

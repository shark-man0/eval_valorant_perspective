# Development timer foreground study: reject score preprocessing transfer

Keep the current timer reader. A fixed development-only prototype that transfers score foreground processing to timer reduces accepted frames from 679 to 651. It does not address the independent End failures and is not installed in production or a qualification profile.

## Fixed inputs and hypothesis

Use only the original additional-source development windows 354–362, 444–452 and 518–526 seconds, 481 frames each. Source SHA256 `06919642d69f68895ac123b505bfd7d3643dd28d903585008fcdc2b7f1b7e3fd`. These are existing development data, not the newly evaluated source's three held events. No new held image or tracker call is used.

Current recognizer `414f9d9d3f1841cfe50fdf9732bb78e1bfa35aa4382eb7c0d90d194ed81155fa`, profile `ca8aa2a0325afd5f5bcf6d6d8eaddab94ea764ecdcbacecc6104ca3b2f0895f9`. Fresh current reader calls verify every cached full-image pixel hash. The inventory reports 679 accepts and 764 unknowns: 713 foreground-border rejections, 28 below NCC0.90, and 23 incorrect separator counts. Many border rejections are legitimate Spike displays, so unknown reduction alone is not an accuracy target. Representative original source/mask images also show a bright background flooding the Otsu foreground of a readable countdown.

Before the prototype call, save a single hypothesis and its exact source hash: replace only timer Otsu with fixed white200 plus maximum of the left/right eight-pixel row medians and contrast floor12, using the existing score convention. Preserve digit templates, Gaussian comparison, 0–9 competition, NCC0.90, margin0.04, digit/colon geometry and border requirements. No grid search, preferred value, retry, temporal input or horizon change. Prototype source hash `cccddbdb8862bcbf8c7672042fdfd92b572600ac5402ac45830b6745a342e0ba`.

## Actual paired results

| Original development window | Prior accepts retaining value with changed confidence | Prior accepts lost | New accepts | Remain unknown |
| --- | ---: | ---: | ---: | ---: |
| LOST | 268 | 7 | 3 | 203 |
| WON | 26 | 0 | 0 | 455 |
| Numeric countdown | 322 | 56 | 32 | 71 |
| Total | 616 | 63 | 35 | 729 |

There are no changed accepted values, but none of the 616 retained accepts keeps identical confidence. All new accepts remain development predictions rather than assumed correct. Of the 63 lost accepts, 55 fail NCC0.90, seven fail exactly-two-colon-dots, and one touches the border. Thus the foreground replacement changes digit shape enough to break the existing template comparison in many previously accepted frames. There is no evidence supporting a lower threshold or a changed competitor margin.

Assistant post-prediction source/mask review selects first, middle and last of each window/delta group, 12 images in total. It confirms examples of readable original countdowns among the lost accepts and examples of recovered digits after background suppression. It is not complete changed-field accuracy, independent human review or new holdout. An initial montage export has an undersized canvas and fails; enlarging that canvas produces the review images without rerunning either reader or changing results.

Inventory takes 29.190 seconds and the prototype 29.161 seconds on cached full images, excluding acquisition. Code/profile identities are rechecked at both run ends. The aggregate hashes plans, rows, exact prototype and source-review selection. These are call measurements, not a benchmark.

## Decision and next constraint

Reject this fixed preprocessing transfer. Leave all production code, profiles, admission, GT, timestamps and the End one-second deadline unchanged. In particular, do not adopt an Otsu-then-white retry to choose whichever reads, bridge unknowns or infer an earlier boundary. Further foreground work needs development-trained templates consistent with the preprocessing, complete source-reviewed controls and a new frozen method before any distinct independent event is opened. Availability alone does not prove accuracy.

This report-only checkpoint does not rerun the implementation tests or full E2E. The previous independent three-event trial still has zero detected End boundaries. Formal End, original-source R1 timing, continuous complete lifecycle, full R2 sampling and round membership remain unresolved. No qualification is issued. Keep Issue #16 open and PR #42 draft. Network approval remains unavailable after the prior CI query's automatic approval usage-limit rejection; no push or new remote CI result is claimed.

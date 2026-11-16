# Development Map recorder selection

PR #148's candidate order is the input baseline. The order and original
candidate centers remain available even when the more selective geometry
measurement abstains. The new measurement fits a textured portrait inside
an enclosing component, then locates a single attached protrusion using
the component's radial envelope. It estimates the tip from the outer cap
and rejects competing protrusions. Nearby proposals count as duplicate
observations only when their fitted centers and native rim pixels agree.

`MapRecorderSelector.observe(image, pool, sample, timeline_frame)` consumes
the native BGR frame, ordered Map pool and corresponding frame emitted by
the shared timeline. Keep one selector per replay and call it in native
acquisition order, including observations that cannot be selected. Provide
Agent portrait references using the existing catalog reader. A proposal
requires all of the following:

- Exact native sample and pixel binding, and an ordered pool bound to the
  shared frame.
- SELF and ALIVE, current recorder-view evidence, and a causal recorder
  anchor from the same acquisition. The current view must agree with the
  recorder's Agent and ability signature.
- A top candidate with an attached tip, a matching Agent portrait, and no
  unresolved nearby or similarly ranked competitor.
- Three consecutive matching measurements on distinct observed frames
  with gaps of at most 250 ms, compatible acquisition context, and bounded
  image-space displacement.

The return value can propose a candidate index and a native pixel center
for research review. It carries UNKNOWN ownership and no position authority.
The original observed center or a research pixel center is not a Map
coordinate. No provider registration or shared timeline rule is changed.

| Development result | PR #148 | Follow-up |
| --- | ---: | ---: |
| Comparison Top-1 / Top-3 / Top-5, 27 visible | 22 / 25 / 25 | 22 / 25 / 25 |
| All visible Top-1 / Top-3 / Top-5, 61 scenes | 51 / 56 / 58 | 51 / 56 / 58 |
| Tip error, two tuning marks | 11.2–19.2 px | 2.0–2.2 px |
| Direction error, same two marks | 37.4–113.2° | 6.8–11.4° |
| Fixed 100 correct / wrong / abstained selections | 0 / 0 / 100 | 0 / 0 / 100 |
| Reviewed duplicate pairs recognized / distinct pairs merged | 0/2 / 0/3 | 0/2 / 0/3 |

The two tip examples were used to investigate the error. Tip and direction
accuracy on other matches remain unmeasured. The new fit produced centers
for 16/27 comparison scenes. On those same 16 observations, median distance
from the manual center was 2.53 px, up from 2.24 px with PR #148's center
refinement. The stricter measurement is supplementary to the ranker.
In eight of the 36 negative scenes it still found a portrait-like component,
including four with a tip. A component cannot establish recorder ownership.

The five usable pair labels include two crowded duplicate pairs. The shared
rim test did not resolve either pair. A separate synthetic control verifies
that a clean duplicate and a distinct nearby portrait remain distinguishable.
The fixed replay abstained on 55 SELF/ALIVE frames without a usable anchor
and on the remaining 45 frames without a SELF/ALIVE context. Synthetic tests
exercise successful selection and resets after spectator, an unmatched pool
or native sample, and an uncovered gap. The synthetic results establish
control flow only.

## Shared Camera evidence replay

Call `observe(..., observations=rows)` with the full native observation set
referenced by the shared timeline frame to evaluate the measured Camera route.
It uses the existing `camera_panel` owner HUD observation and its recording
prototype fingerprint. The observation must be bound to the exact native
sample and cited by the Camera estimate or the Map view evidence. The selector
abstains on competing current signals, including a combat report, and expects
the shared timeline to supply SELF and ALIVE.

This route requires a warm rim around a distinctive portrait, no unresolved
neighbor, and agreement of the portrait pixels over three consecutive native
observations. At least one of those observations must show an attached tip.
An observed Agent contradiction prevents selection. The recurring measured
ability HUD provides the recorder witness when the catalog cannot name the
Agent. That case needs candidate-level review before any use as ground truth.

The integration replay uses separately pinned, unmerged timeline branches
from #150 (continuity) and #151 (Camera panels). The ability prototype is
learned by the existing Camera supplier from each recording's unlabeled
native frames. Manual labels and the five-match tuning/comparison split
remain separate from that procedure.

Across the frozen 150 frames, the shared Camera replay reduced UNKNOWN
from 47 to 6 and increased frames with a recorder anchor from 69 to 101
within this paired replay. The selector produced two proposals from the
90 tuning frames and abstained on the 60 comparison frames. All 100
frozen sparse scenes abstained. The shared Camera result called three of
23 manually labeled spectator scenes SELF. These three carried a combat
report and were blocked before measuring the Map candidate. Dense proposals
still need strict human confirmation of their roles.

The independently replayed ten-match timeline retained 69/69 fixed scores,
9/9 and 6/6 supplemental scores, with 21,999 second rows and zero formal
outputs. The Map ranker retained the 22/25/25 Top-1/3/5 and .869 MRR@64 on
the 27 comparison scenes.

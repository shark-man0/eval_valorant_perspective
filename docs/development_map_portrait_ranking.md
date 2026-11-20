# Development Map portrait ranking

A white arrow or a nearby amber pixel can rank a wall, another player or an
interface icon above the recorder's portrait. The development-only
`temporal.map_rim_ranking` module measures a warm, enclosing rim around a
textured interior and adds a weaker cue for a continuous outward projection.
It penalizes fill inside and outside the rim and can adjust the measurement
center within a small window. Ranking still refers to the original candidate
indices and centers. It does not change the captured pool or any timeline output.

To compare an unchanged candidate pool and ordering on a native BGR frame:

```python
from valorant_ai_coach.temporal.map_rim_ranking import measure_warm_rims, rank_rim_candidates
from valorant_ai_coach.temporal.map_shape_ranking import rank_marker_context

legacy = rank_marker_context(image, candidates)
measurements = measure_warm_rims(image, candidates)
research_ranking = rank_rim_candidates(
    legacy, measurements, rim_weight=6, direction_weight=2,
)
```

The shape and color configuration above was fixed on three development
recordings before measuring the other two. Positive ranking rows are scored
against human centers using the *original* candidate centers, with a nine
native pixel tolerance and a 64-candidate cutoff. Top-1 is a proximity
metric. A nearby teammate or icon can satisfy it.

| Frozen development cohort | Top-1 | Top-3 | Top-5 | MRR@64 |
| --- | ---: | ---: | ---: | ---: |
| Historical 64 positives | 20 → 53 | 33 → 59 | 42 → 61 | .459 → .880 |
| 61 positives after occlusion review | 20 → 51 | 32 → 56 | 40 → 58 | .471 → .882 |
| Tuning, 34 visible | 15 → 29 | 22 → 31 | 25 → 33 | .575 → .893 |
| Comparison, 27 visible | 5 → 22 | 10 → 25 | 15 → 25 | .341 → .869 |

Both comparison recordings improved in Top-1 (3/15 → 14/15 and 2/12 → 8/12).
All 20 previous positive Top-1 hits were retained in the 61-scene set. At
three pixels, Top-1 in the comparison improved from 2/27 to 22/27. This is
a stricter sensitivity check against manual clicks, rather than a measurement
of exact position error. The old white-arrow-specific ranking and the initial
portrait/template prototype were not substituted for the legacy baseline.

Six supplemental tuning reviews yielded five visible centers and one
occluded scene. Four reviewed candidate-specific portrait centers could be
compared; the center refinement reduced distance to the manual mark in all
four. Two marked tips differed from the algorithm by about 11–19 native
pixels, so the projection estimate is not suitable for heading. One pair
label conflicted with the candidate role labels. Among the other five pairs,
exact component grouping kept all three different pairs separate but missed
both annotated duplicates. The existing duplicate handling was preserved.

The separate `temporal.map_portrait_rim` module can compare a Map Agent
reading with the shared timeline's recorder Agent anchor. It requires matching
native pixels and pool, matching acquisition scope, a non-future anchor,
and SELF/ALIVE context. An Agent match still has no authority to declare
ownership. Exact physical pixels were located for all 100 scenes in replay,
with 55 SELF/ALIVE and 22 SPECTATOR contexts. None had a usable serialized
recorder anchor at those samples. The ranking therefore leaves ownership
UNKNOWN and all 100 selections abstained, including all 36 negative scenes.
No self position, Zone, movement, Fact or Event is emitted by this ranking.

The port from the previous Map branch kept the original 100-scene candidate
order, spatial grouping and abstentions intact. In the common timeline
regression, 10 recordings / 21,999 one-second rows retained the fixed 69/9/6
scores and matching native state and event outputs. No timeline state or
production API reads the new ranking.

Next: acquire independent candidate-level role labels in additional matches,
especially overlaps, spectating, and the remaining comparison failures.
Validate causal recorder anchors in wider replay before testing any acceptance
policy. These development rankings are not independent qualification.

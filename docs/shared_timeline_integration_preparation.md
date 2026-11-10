# Shared timeline integration preparation

This is review preparation, not main merge authorization. The main baseline is
`ef4eec376e83f5bf5345eb2fefbc4e660d4bca4a`. The development stack remains Draft.
No historical branch is rewritten and Production qualification gates stay closed.

## Dependency chain

The currently open linear chain is:

`115 -> 116 -> 117 -> 118 -> 119 -> 120 -> 122 -> 123 -> 125 -> 126 -> 127 -> 128
-> 129 -> 130 -> 131 -> 132 -> 133 -> 134 -> 135 -> 136 -> 137 -> 139 -> 140`.

At the review snapshot, all 23 PRs were open, Draft, unmerged and mergeable with
their declared bases. The latest development head was `07ad038`; simulating its
merge with the unchanged main using `git merge-tree` reported no textual conflict.
That is not evidence that every research feature is ready for Production.
Earlier independent research PRs are not blanket-merged into this stack.

## Shared responsibilities and overlap

`temporal/game.py` is the only game-state owner and is touched in 14 stacked PRs.
`temporal/application.py` is touched in 13, `temporal/match.py` in 10 and
`temporal/viewer.py` in 10. Map projection/correspondence and native transport are
also shared. These files must be reviewed as their final composed implementation;
parallel HUD/Map work must not recreate Round/Life/Camera state management.

Supplier interfaces carry native observation identity, raw measurements, profile
and producer fingerprints. Sampling configuration, observer code, OCR/reference
assets and engine options are separately bound. Changing one invalidates an old
checkpoint binding; old measurements may only be replayed with explicit original
producer lineage, never relabelled as a newly run recognizer.

## Proposed review stages

1. Review Source/native transport, observation contracts and the shared state API
   from the foundation PRs. Require source-break, conflict, missing-observation and
   exact-sample tests. Keep all unqualified gates intact.
2. Review the composed whole-recording acquisition, JSON/CSV export, original-video
   viewer and development evaluation consumer. Verify complete duration, missing
   values and seek offsets on multiple permitted recordings.
3. Review HUD/Map/Zone supplier joins and research state projections together.
   Compare original fixed positives and abstentions; retain competing identity
   hypotheses and distinguish recorder from viewed actor. Map ranking does not
   establish recorder ownership or a continuous path.
4. Review staged data admission, exposure accounting, optional visual models and
   high-density experiments as development tools. A passing CI or extra candidate
   count does not establish semantic accuracy, independent generalization or
   Production qualification.

Each stage requires a concrete reviewed patch/dependency plan and exact-head
Linux/Windows, Ruff, mypy, Text I/O and packaged executable evidence. Do not merge
all Drafts merely because their bases are textually compatible. A supervisor
decides the actual merge sequence and any Production adoption separately.

## Reference coverage

The current private reference index uses public catalog `08.09.00.2521387`.
The [Riot developer asset page](https://developer.riotgames.com/docs/valorant#assets)
still links the 08.09 catalog at the time of this review and says updates are
manual. The [official Map page](https://playvalorant.com/en-us/maps/) also lists
Summit, Corrode and Abyss, which are absent from this index. Existing map names
may also have changed geometry. An old catalog cannot establish support for all
current maps; missing or incompatible references must retain UNKNOWN/candidates.
Do not mutate reference assets underneath a running acquisition or checkpoint.

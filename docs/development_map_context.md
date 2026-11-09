# Development Map marker context and public references

`rank_marker_context` orders existing visual candidates using the previous white
shape score and proximity to a small amber component. It does not create a
candidate, identify an agent, or assign a marker to the recorder. Its output
always has `ownership=UNKNOWN`, `qualified=false`, and
`position_authority=false`. Any camera or agent evidence must be joined by the
common timeline owner before a position can be considered.

On the same 140 previously exposed DEVELOPMENT frames, the pool remained
14,574 generic candidates. Four scoring-only recorder footprints were already
available. With the existing 9 pixel footprint retrieval tolerance, the
previous shape rank retrieved 0/4 in Top-1 and 2/4 in Top-5. The context rank
retrieved 2/4 in Top-1 and 2/4 in Top-5. One former Top-5 hit was lost, one
was gained; thus this is a bounded research improvement in Top-1 only, not
evidence of reliable marker ownership. No new physical correspondence or
formal Map position was produced. The historical 140 Map packets, 17,414 raw
proposals, and four provisional positive controls are untouched. The private
per-frame evaluation is under `outputs/composite_map_PRIVATE` outside Git.

Riot's [VALORANT developer documentation](https://developer.riotgames.com/docs/valorant)
describes its Public Content Catalog as assets available for use. The
[Riot legal page](https://www.riotgames.com/en/legal) and developer policies
still govern a project's use. `load_public_map_references` reads a caller
supplied extracted catalog and records the catalog version, map ID, minimap
image path, and supplied coordinate scalars. It does not bundle assets,
silently select a map, generate Zones, or infer player identity. The catalog
checked here was release 08.09 (version `08.09.00.2521387`, published in
2024). It contains 15 map entries, including 10 with nonzero coordinate
scalars, but it predates current maps such as Summit. Its coordinate formula
is a geometry candidate and needs validation against actual observed
minimaps before use. The existing Summit MapRegistry remains the active
Zone source. Official reference images stay in private local storage.

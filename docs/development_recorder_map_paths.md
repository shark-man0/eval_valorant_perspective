# Recorder Map trajectories for development replay

The exporter reads exact native images and the existing application's common timeline.
It emits a sidecar with native observations and their existing one-second rows.
Map coordinates are pixels in a versioned map reference image. An empty second
has UNKNOWN coverage. Segments stop at missing observations, acquisition or map
changes, and selection gaps. Intermediate points are never interpolated.

```sh
python -m valorant_ai_coach.temporal.map_recorder_export \
  --bundle-path timeline_PRIVATE.json --frame-manifest acquisition_PRIVATE.json \
  --policy-path policy_PRIVATE.json --catalog public_reference_catalog.json \
  --layout config/hud_layout_1080p_v3.json --zones-path reference_zone_index.json \
  --output recorder_paths_PRIVATE.json
```

The frame manifest supplies `frames` with `sample` and `path`, from the native
acquisition contract. The catalog uses the existing public Map reader's `maps`
format. Optional `characters` entries provide `name` and `minimap_portrait`
relative to the catalog. The selector emits a named Agent only when a validated
current Map portrait agrees with shared HUD Agent evidence. The Zone index
provides a `maps` array. Each entry supplies `map_id`, `reference_sha256`, and
`polygons` mapping zone IDs to vertex pairs in the exact reference image's space.
The Zone reader abstains on missing coverage, overlapping polygons, and
boundaries within four reference pixels. Use authored geometry for the exact
registered texture. The sidecar has development-only position hypotheses.

`--recover-supported-portraits` enables a research option. It follows a
bounded, visible Map candidate when the top-ranked shape is unresolved,
only if the measured current view still belongs to the recorder. The
candidate must match the previous portrait and have noncompeting current
support. A partial fit cannot start a track or supply a tip. The public
ranking and the default selector behavior stay as approved in the prior PRs.

| Fixed 150-frame replay outcome | Count |
| --- | ---: |
| Current view evidence conflicts | 41 |
| Current SELF and ALIVE unavailable | 31 |
| Top portrait shape unresolved | 33 |
| Insufficient consecutive observations | 24 |
| Recorder anchor missing | 7 |
| Competing marker or overlap | 5 |
| Current view and recorder identity disagree | 3 |
| Recorder anchor unusable | 3 |
| Marker pool empty | 1 |
| Strictly correct research selections | 2 |

Five-match replay of the optional selector and 29 public minimap portrait
references reproduced two selections and 148 abstentions. A named Agent
match was not established for the selected real frames. The earlier
100 ms comparison experiment remains one correct selection and four
abstentions across five targeted comparison endpoints. These measurements
do not establish a recognition gain for this PR.

The CLI reproduced three Lotus coordinates over 0.4 seconds, joined to one
original common timeline second. This segment falls outside the authored site
polygons. The held endpoint and the second training sequence remain without an
accepted coordinate transform. The Zone polygon checks pass controlled tests.
All 100 frozen ranking scenes retained the established ordering.

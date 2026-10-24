# Development Map reference versions — 2026-10-24

The current Corrode and Bind textures came from the third-party valorant-api
displayicon endpoint recorded in their development provenance. Neither upstream
asset supplied a verified client build. Existing provenance hashes reproduce;
fetch dates for the original bytes were not recorded as build evidence. Do not
infer a build from their commit date or from a recording's filename.

| Reference | Existing development reference SHA-256 | Build |
|---|---|---|
| Corrode, authored CCW270 | `c6ffcf7e8c8b73781d08bc562594690fdfd7c6dbd35dbfd15fbc1be145096959` | UNKNOWN |
| Bind | `84f5ff72aa58bf677617ab5792def847c1c154b38f6e7458f7234121baa3507f` | UNKNOWN |

## Official evidence

[Riot's patch 13.08 notes](https://playvalorant.com/en-us/news/game-updates/valorant-patch-notes-13-08/),
published 2026-10-13, describe changed Corrode defender paths, Mid cover and A
plant zone. The screenshots are before/after perspective views, not a surveyed
replacement coordinate system. A previous texture cannot be assumed compatible
with this change. Conversely, the unknown-build existing texture cannot be called
definitively pre-patch without further evidence.

The [official Map page](https://playvalorant.com/en-us/maps/) provides labelled
Corrode and Bind diagrams, retrieved 2026-10-24 for inspection. Neither diagram
declares a client build. Labels/pins/backgrounds occlude geometric detail; these
are not drop-in calibration textures or exact world-coordinate ground truth.
Site labels do not define this application's plant/interior Polygon semantics.

| Official diagram | URL | Retrieved byte SHA-256 |
|---|---|---|
| Corrode | [515px labelled diagram](https://cmsassets.rgpub.io/sanity/images/dsfx7636/news_live/90666c45369269a33eebddc363b250dbc7d61a34-515x515.jpg?accountingTag=VAL) | `036dd46b87713301d516395caecea4e9744005c53b0ffac9a3675c36e076a679` |
| Bind | [641px labelled diagram](https://cmsassets.rgpub.io/sanity/images/dsfx7636/news/9c2f75aa4d00022c440615ce08988c7dd5f2bb00-641x641.png?accountingTag=VAL) | `87f2ae1c5a12559f52e4ac75085d839c3c669892fa442de55a29d086c35bde67` |

No new image or Polygon is installed by this review. Bind runtime differences
may involve scale, crop, rotation, UI overlays or texture/version changes. A failed
alignment is not by itself proof of a patch mismatch. The current registration
metadata lacks verified acquisition-scoped client build evidence, so both map
version correspondences remain UNKNOWN. Current-frame outline fit acceptance
alone cannot settle it.

## Asset and product policy

The [VALORANT developer policy](https://developer.riotgames.com/docs/valorant)
describes the public content catalog as reusable content, but says catalog updates
are manual and may lag patches. Its linked release label is not proof that all
current map revisions are available. That catalog permission is not a blanket
license for third-party data or a geometry guarantee.

The same policy requires registration for player-facing products, player opt-in
for personal data, and prohibits identification of deliberately hidden players
and immediate tactical real-time instructions. This work is offline development;
no service, API account or production deployment is enabled here.

[API terms](https://developer.riotgames.com/terms) and Riot's
[Legal Jibber Jabber](https://www.riotgames.com/en/legal) retain Riot's IP rights
and attach conditions to use, redistribution, commercial products and attribution.
Do not treat source code licensing as licensing the embedded Riot assets. Any
future distribution must check the applicable registration/license requirements
and carry the required non-endorsement notice. This review does not assert Riot
approval of this application or third-party asset redistribution.

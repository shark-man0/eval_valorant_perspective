# Self Death: frozen-reference discovery and role controls

Status: **new scoped real-image negative evidence; no independent positive
qualification or canonical PASS gain**. Start branch
`7dc87328645658c2167215724041cb88e0333544`; fetched main
`7e480c2f2f7f49aea73e1541d065d78881d2f11c`.

## Why inspect these inputs

The frozen expanded reference bank improved numerical victim support in two
known second-source episodes. Before requesting transfer of another recording,
the unchanged additional reference was applied to the existing second source
to locate other usable contexts. No reference fitting, threshold tuning, GT,
actor labels or expected names were used for discovery.

Keyframes are used only for localization. Their gaps do not certify absence,
continuity, event timing or negative accuracy. They are not a changed Full E2E
sampler. Subsequent recognition uses every native frame in explicitly frozen
short intervals. Discovery-conditioned selection is not blind holdout; the
second source's global exposure history remains unknown.

The fixed component scan inspected 2,245 keyframes and found 208 icon matches
over the source. The frozen later-source selection yielded eight separated
groups after excluding the already reviewed native interval. The first three
groups were selected without looking at their subject roles or downstream
recognizer success. A group outside the exact exclusion still overlapped the
tail of a known episode; it is explicitly retained as a persistence control,
not relabeled an independent death.

## Source review and continuous results

The three selected windows each contain 121 native frames, for 363 total. Their
source SHA, rational PTS, encoded/pixel hashes and decoder epochs were recorded
before replay. Start, middle and end full-resolution source images were reviewed
and preserved privately before the recognizer output was produced. This is
nine-frame context review, not exhaustive per-frame semantic labeling or
qualification of content continuity. No source images or player text are public.

| Source context | Frames | Numeric role readings | New death predictions | Source-blocked frames |
| --- | ---: | --- | ---: | ---: |
| Ability view / nonself killfeed | 121 | No recorder role | 0 | 0 |
| Recording player in killer position | 121 | 7 killer | 0 | 0 |
| Known self death already in progress at cold start | 121 | 84 victim | 0 | 0 |

The second control exercises actual positive killer-slot recognition rather
than only rejection of an unreadable row. The third has caption support in all
121 frames and actual victim support in 84, but no locally observed fresh onset;
it correctly produces no new death. Counts are correlated readings, not
independent events or a whole-video false-positive estimate.

| Comparable measure on these fixed inputs | Previous | Current | Delta |
| --- | --- | --- | --- |
| Full recognizer replay | Unmeasured | 363 native frames | — |
| New death predictions | Unmeasured | 0 | — |
| Formal Death Events | Unmeasured | 0; release disabled | — |
| Newly qualified positive episodes | 0 | 0 | 0 |
| New canonical PASS/FAIL/NE | Not run | Not run | — |

No new self-death positive was established by these three windows. The known
positive results, expanded-bank negative suite and adopted/archived canonical
baselines retain their existing scope and fingerprints.

## Cost and input-contract defect

The discovery stage's recorded timer was 249.973 seconds; it excludes the initial
source hash and is not total command wall time. Native acquisition took
746.623 seconds. The 601,002,233 encoded bytes were held in temporary RAM,
not copied into persistent video storage. The source video was not duplicated.
Successful recognition took 368.536 seconds, total replay wall time 512.646
seconds, and peak Python RSS 100,540,416 bytes. All terminal bindings passed.

The first replay failed at final aggregation because the acquisition manifest
omitted its required total `frames` key. No result was saved or counted as a
successful negative. The original manifest and failure log were preserved.
A second manifest adds only the correctly summed total (363), with every
previous source record/metadata field unchanged and an explicit repair ledger.
No decoding or pixel mutation was needed. The successful result uses that
second manifest; the failed attempt is not concealed in the timing above.

The runner now validates aggregate count and row-container structure before
profile loading, source/dependency hashing or recognition. `replay_cache()`
also validates directly before observation, and retains its processed-count
postcondition. Missing/invalid totals and malformed row containers raise
`ValueError` immediately rather than performing expensive recognition first.
This fixes orchestration cost, not recognizer accuracy. Count validation rejects
bool/string/noninteger totals; it does not relax source integrity, geometry,
NCC, identity, temporal policies, qualification or existing assertions.

Tests verify early rejection with spies that fail if recognition begins, and
a CLI test rejects the missing count before profile/hash work. Existing valid
positive, negative, native/cached equivalence and profile tests remain in the
same suite. No skipped/relaxed assertions are introduced.

## Private reproducibility records and next task

Existing private investigation directory:

- `match002-expanded-rifle-discovery-plan.json` and
  `match002-expanded-rifle-result.json` freeze the component/reference selection.
- `match002-expanded-rifle-native-plan.json` and original manifest freeze native
  windows and pixel provenance; `match002-expanded-rifle-source-review.json`
  records the pre-replay context review.
- `match002-expanded-rifle-manifest-repair.json` proves the metadata-only repair;
  repaired manifest SHA-256:
  `cc8765a83d8f36e2245eed8087716cc3bf6c2f504223f4b82042a9b73a2a2663`.
- Successful `match002-expanded-rifle-native-replay-v2.json` SHA-256:
  `54ce9935bbe32a6e90c110a7dbf6a3f3dd74df7b5fd03df05a7f1ba8c61e9457`.

The successful replay binds the exact orchestration bytes that generated it;
the later move of cheap validation to CLI entry does not re-sign that result.
Image recognizer/profile/dependency fingerprints remain identical to the
expanded-bank positive replay. The preflight change does not alter successful
recognition behavior and is covered by the existing positive equivalence tests.

Next: inspect the remaining discovery groups under a newly frozen selection,
without template tuning or assuming they contain positive deaths. Independently
qualify actual subject/temporal positives before supplying a real qualified
frame producer at the session entrance, application wiring and canonical
targeted/sample evaluation. Additional video remains optional, with contents
unverified; no transfer or new filming is required by this result.

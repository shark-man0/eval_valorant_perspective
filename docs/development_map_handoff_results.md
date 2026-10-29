# Map handoff validation (development only)

## Scope and preservation

The handoff starts from PR112 `c4f1cf5ffb33320344dac55eee5992194b94751e`.
The additional local research commit
`6d6bc09a249bb67edd622fc2c79aed01954d204a` remains on its original branch;
it is not imported or discarded. Startup main was
`ef4eec376e83f5bf5345eb2fefbc4e660d4bca4a`.

This branch changes only Map-owned development code, documentation and tests.
The existing stateful baseline remains available. Native features were moved
unchanged to a Map-only module and re-exported from the old import path. No HUD
reader, shared Production schema, GT, threshold, model or default recognizer was
changed. No protected recordings, newly decoded video or Full E2E was used.

The actual common producer/API is not available yet (confirmed by the user).
Consequently this is a handoff implementation, **not completed common-engine
integration or recognition improvement**. No new life/camera/Round inference
was added to Map. The provisional boundary and duplication inventory are in
[the connection specification](development_map_handoff.md).

## Same-input comparison

The fixed replay uses 140 previously acquired native DEVELOPMENT observations
from two admitted physical matches. Every encoded-frame hash and native-pixel
hash was checked, UI evidence was recomputed, and current calibration reproduced
all supplied geometry-only candidate points within numerical comparison
tolerance. This checks replay consistency, not independent coordinate accuracy.
The baseline was rerun; its serialized results match all 140 frozen results.

| Fixed acquisition | N | A: existing single-frame Map | B: existing Map temporal | C: no common producer | D: controlled external-state adapter |
| --- | ---: | ---: | ---: | ---: | ---: |
| Haven acquisition 1 | 30 | 1 | 26 | 0 | 28 |
| Bind acquisition | 30 | 26 | 29 | 0 | 29 |
| Haven acquisition 2 | 30 | 3 | 26 | 0 | 25 |
| Spectator control acquisition 1 | 30 | 0 | 0 | 0 | 0 |
| Spectator control acquisition 2 | 20 | 0 | 0 | 0 | 0 |
| Total | 140 | 30 | 81 | 0 | 82 |

These columns count unqualified Map coordinates, **not correct self positions**.
D supplies controlled ALIVE/SELF/ACTIVE or SPECTATOR snapshots to exercise the
adapter. Those state labels are not produced by an automatic common engine.
Its +1 net coordinate availability is not a recognition improvement. C emits
140 UNKNOWN recorder positions while preserving raw candidate packets. All
methods have zero qualified recorder ownership, formal Facts, Events or scores.

D produces seven observed path segments and 75 adjacent-observation chords;
its 28 one-second bins retain all 140 native samples. Missing seconds/positions
are not filled. Fifteen named Zone candidates occur in the first Haven
acquisition. Its 2.8-second same-Zone endpoint span is **not continuous occupancy**.
Other acquisitions have zero named Zone candidates. Five private viewers pair
the original acquired images with observed candidate points and dashed chords.
They are explicitly labeled controlled external-state ablations and are not
published in this repository.

The first adapter experiment retained an expired marker association indefinitely
and reduced one acquisition to 3/30 coordinates. The corrected Map-only memory
policy retains history but expires active reassociation at the existing
0.6-second horizon. Fresh evidence then starts a separate lineage. The resulting
25/30 still loses one baseline observation; the adapter is opt-in and does not
replace the baseline. No thresholds were relaxed to match reviewed examples.

## Reviewed correctness and uncertainty

Five existing exact-image role reviews were reused **after** inference; no human
marker ID or role is a runtime input and no new human review was requested.
Four refer to recorder markers and one to Spike UI. B selects all four reviewed
recorder markers and does not select the reviewed Spike. D selects three of the
four, withholds the fourth during ambiguous identity retention, and does not
select the Spike. It selects no different marker at these five reviewed points.
The withheld reviewed self point is a measured loss, not a corrected error.
C selects none because the common producer is missing. These few exposed
examples are not population accuracy, misattribution-rate qualification or
independent match-level evaluation. Unreviewed candidate roles remain UNKNOWN.

Absolute coordinate error and Zone-boundary error were not newly measured in
this handoff. Recomputed calibration agreeing with cached candidate geometry
does not establish semantic correctness. Existing independently reviewed
coordinate/static results remain in private regression artifacts; their limited
annotation uncertainty does not become a transferable error bound.

## Legacy real-data regressions

| Preserved check | Result |
| --- | --- |
| Fixed Bind/unregistered-Map comparison, 198 observations | ROI 112; calibration 149; Map 70; named Zone 3; zero compared-field regressions |
| Existing Haven 50 | Map 40; zero unexpected differences |
| Later Bind 30 / Haven 30 | Map 27 / 28, preserved |
| Existing spectator 20 | 20 explicit rejections, no Map positions, preserved |
| Default reviewed-reference repeat | Map 27, named Zone 15; zero record differences |
| Portable-reference repeat | Map 30, named Zone 20; static 18/18, pairwise diameter 0 reference pixels |

Static spread is not absolute positional accuracy. Repeated known DEVELOPMENT
inputs are regression data, not independent qualification.

## Cost and remaining integration work

The controlled 140-observation replay, including image reads, feature/UI checks,
baseline tracking, fresh calibration, two consumer variants and private viewer
generation, took 36.91 seconds, with process peak RSS 294.45 MiB on the development
Mac. Within this run calibration took 22.84 seconds, feature/UI processing 2.48
seconds, legacy tracking 0.17 seconds, packet construction and both consumers
1.53 seconds. This is one sequential development run, not a matched speedup
benchmark or isolated per-model memory measurement. No calibration reuse policy
or recognizer optimization was changed.

The Map boundary has contract tests for external death/spectator/remote/unknown
states, Round scope/reconfirmation, missed intermediate transitions via external
tracking epoch, missing marker identity retention, ambiguous reappearance,
source/geometry/reference changes, stale snapshots, duplicate/backward time,
one-second aggregation and legacy path adaptation. Controlled transitions do
not prove a natural death-to-spectator-to-new-Round episode.

Before adoption the common owner must supply its actual API and independently
supported recorder/camera correspondence, map snapshots and invalidation epochs
to the native observations, repeat A/B/C on identical inputs, resolve the
reviewed selection loss without increasing misattribution, and validate natural
Round/death/spectator/reentry sequences. Production and Qualification remain
blocked. Draft handoff review is appropriate; main merge is not authorized.

Validation at `6f6d37d`: Ruff (the repository CI scope plus the new CLI) and mypy
(182 source modules) pass. The final related tests pass 57/57. The broader
local run passed 4,806 tests with nine skips; its sole failure was a sandbox
loopback bind denial, and that exact synthetic test passed when rerun with
loopback permission. Two final safety tests were added after the broader run
started and are included in the 57/57 result. Linux/Windows exact-head CI must
be checked on the Draft handoff commit; older PR112 CI is not evidence for it.

## Follow-up acquisition/provenance audit

Four failing reproduction cases exposed two handoff gaps: a backward or repeated
native sample could retain a later position as last-known history, and the
geometry summary omitted supplied detector/execution provenance. The consumer
now rejects nonincreasing native time per Source/epoch even after a camera veto,
clears its retained state on rejection, and preserves the full geometry envelope
alongside a separately copied calibration/version summary. Consumption checks
that the summary and original envelope agree. No game-state inference is added.

The repaired consumer replays the same 140 native observations with **zero
selection/state differences** from the preceding controlled run: 82 Map
candidates, 28 one-second bins, all 140 original geometry envelopes retained.
No new calibration or video decode was run; this consumer-only replay reuses the
previously measured geometry/calibration and is not a recognition or speedup
experiment. It took 7.58 seconds, with peak process RSS 210.56 MiB, and is not
comparable to the earlier calibration-plus-viewer run. All non-handoff legacy
recognizer file digests in the fixed real-data regression are unchanged.

Current related tests pass **61/61**, Ruff passes and mypy passes for 182 modules.
The earlier broad suite predates this repair; it was not rerun needlessly.
Exact-head Linux/Windows CI for the follow-up commit remains unverified pending
the user's verification notice; no repeated CI polling was performed. Actual
common-engine integration is still blocked on the integration owner/API and
source-bound snapshots. The reviewed selection loss remains unresolved, and the
adapter still does not replace the baseline. The full integration Goal is not
complete.

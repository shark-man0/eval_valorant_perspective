# Numeric Self Death: image-to-Event candidate session

Status: **experimental adapter, not a qualified image producer or application
adoption**. Start branch `784e8f96e76dd6a24c19cc79058ab5cb79fde5a2`;
fetched main `7e480c2f2f7f49aea73e1541d065d78881d2f11c`.

## Missing connection and implemented scope

The existing numeric Event consumer accepted separately assembled typed proof,
but there was no streaming adapter joining an actual image prediction to its
original reviewed frame witnesses. `experimental/numeric_death_session.py` adds
that adapter using the existing image recognizer and consumer. It does not
implement, manufacture or install a qualification provider.

`NumericDeathImageSession.observe(image, source)` first runs the unchanged image
recognizer. Without both an exact qualification contract and a frame provider,
it returns that original diagnostic reading, no Event and an explicit blocker.
It never changes the original reading's UNKNOWN/CANDIDATE/review state or grants
HUD identity, Alive, HP, Weapon or other player-owned facts.

The frame provider must come from a separately qualified source/subject producer
and return a genuine `ProbeFrame` for the exact current source. It cannot be a
Boolean approval switch. The adapter checks:

- Source SHA, code/profile/dependency fingerprints and native cadence against
  the existing reviewed candidate qualification contract.
- Exact source binding, ordered native adjacency, previous PTS, different
  pixels and retained continuity provenance. Discontinuities/gaps poison the
  pending chain until a genuine producer-qualified new-round rearm.
- Every supplied positive witness against current image measurements: role,
  allowed method, exact ROI, and confidence no greater than actual numerical
  support. Geometry without numerical NCC cannot substitute for a victim.
- A transition witness only at the original self-caption onset, with an actual
  predecessor; a generic Report header cannot create an onset.
- The complete original image-prediction evidence set and onset in the source
  chain. The final reviewed witnesses are selected from their original frame,
  rather than assigned the confirmation time or rewritten from a candidate.

The existing consumer then independently enforces reviewed Self roles, token,
disjoint evidence, current-frame corroboration, confidence minimum, qualification
scope, source chain and duplicate suppression before constructing an Event.
The adapter neither qualifies a provider by hashing its output nor treats a
continuity digest as semantic continuity proof.

Only the existing one-second marker-to-onset horizon, one-second confirmation
horizon and one native predecessor are retained. This is a storage bound, not
a change to either existing detection horizon. The marker's earlier predecessor
must survive even when confirmation is more than one second after that marker.
All qualified provider observations remain immutable. Default-disabled sessions
retain no qualified frame chain. A restored consumer checkpoint suppresses an
already released episode in a fresh session. In-flight image state and complete
application checkpoint/resume are not implemented by this adapter; a fresh
session cannot borrow pending evidence from a previous run.

## Compatibility and fingerprints

No public HUD/RoundPackage/Event/SQLite Schema, review-status enum, actor contract,
confidence meaning, identity policy, GT, assertion, threshold or sampler changes.
No application caller or real qualification certificate is enabled. The existing
candidate-evaluation authorization is sufficient after actual qualification;
there is no added production-adoption permission gate before candidate E2E.

The release fingerprint now also binds `numeric_death_session.py`. An old
qualification/consumer checkpoint cannot silently authorize different adapter
bytes. No old report is re-signed. The image recognizer/runtime/profile remain
unchanged, so their previous reader measurements are not relabeled new results.

## Verification

Synthetic tests exercise actual image recognition through the adapter and
consumer with an explicitly synthetic reviewed source provider. They cover one
Event, original onset/later confirmation, duplicate suppression and restoration,
default missing qualification/provider, wrong source/fingerprints/cadence,
unproved continuity, discontinuity, skipped frames, wrong ROI, inflated support,
unreviewed/unknown identity, persistent Report/self-killer negatives, bounded
retention, and adapter-source invalidation of release qualification. These prove
orchestration and safety contracts, **not real source qualification**.

A real-source default-disabled smoke freshly processes the same 171 native
cached input rows as the frozen expanded-bank match_001 replay. All source image
status outputs and both original onset/confirmation pairs match exactly. The
two diagnostic episodes remain, the short negative windows have no prediction,
all session Events are absent, and no qualified frame chain is retained. This
verifies that the adapter's default cannot enable the real unqualified cases.
It is not an enabled-provider real-positive test or canonical E2E.

Private evidence: `numeric-death-session-default-smoke-v2-plan.json`,
`numeric-death-session-default-smoke-v2-result.json` and its source driver in the
existing private investigation directory. Result SHA-256:
`f1382bbff8700a3d6e47e59e4815a0facf1aa225b7e3957cd30b99278d72edee`.
Source/profile/asset/dependency/code terminal checks passed. Recognition and
session processing took 199.638 seconds. Images, player text, profiles and
source records remain private.

The initial default smoke is preserved separately; it predates the buffer-bound
correction and is not re-signed as the current adapter result. The correction
retains the marker predecessor across delayed report onset without changing
either detection horizon. A synthetic delayed-onset regression covers that
case. Final session/consumer tests: 72 passed in 22.86 seconds, including 23
session cases; the earlier broader 181-case suite passed in 62.45 seconds before
that correction. Final Ruff and mypy (145 files) pass. Current-revision remote
CI is reported separately; earlier green checks are not assigned to new code.

## Previous / Current / remaining work

| Measure | Previous | Current |
| --- | --- | --- |
| Streaming image-to-reviewed-witness-to-consumer adapter | Missing | Implemented and synthetically exercised |
| Real default-disabled input rows through this adapter | Unmeasured | 171; original statuses/times identical |
| Real adapter-issued formal Death Events | 0 | 0 |
| Independently qualified image/continuity provider | Missing | Missing |
| Application-native caller and complete checkpoint integration | Missing | Not enabled / incomplete |
| New canonical targeted/sampled/Full result | None | None |

Adopted 23/55/4, archived Strict candidate 28/50/4 and the separate timing-policy
comparison remain historical, distinct results. No real canonical PASS gain,
qualification grant, main merge or goal completion is claimed.

Next: independently qualify source-bound positive/negative subject and temporal
recognition, supply the genuine reviewed frame producer at this entrance, wire
candidate orchestration and application resume, then run same-contract targeted
and fixed sampled canonical comparisons. The adapter does not remove these
requirements and development images cannot become fresh blind holdout.

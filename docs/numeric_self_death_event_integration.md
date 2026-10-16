# Numeric Self Death: gated native event integration prototype

Status: **experimental integration; no installed qualification/adoption report,
production caller or real-video PASS gain**. This continues the approved
independent Self Subject design using numeric support for all three required
roles. It does not implement the pending structural-role proposal.

Start recognition branch: `cfac17ac532b04367dda7f680517493bc1b4a69b`.
Fetched main: `7e480c2f2f7f49aea73e1541d065d78881d2f11c`.
PR #44/#46 and the legacy HUD ownership guard are unchanged. PR #54's decoder
fix remains separate; none of its changed fingerprints is substituted into old
recognition records.

## Missing connection addressed

The image recognizer predicts the known two source-1 episodes, and frozen
transport preserves their numeric witnesses. Those observations remain
UNKNOWN/CANDIDATE, and no qualification or production adoption is installed.
The old probe deliberately cannot construct native events.

`experimental/numeric_death_release.py` adds a separate consumer for the later
qualified numeric path. Its default construction emits nothing. It does not
upgrade the image reader, observations, subject token or review state. In
particular, the current frozen UNKNOWN/CANDIDATE output is insufficient even
if a consumer is configured with an approval object.

This is a connection prototype for qualification-ready evidence. It is not
completion of the recognizer or of its native application entrance.

## Authority and qualification boundary

`ApprovedNumericDeathRelease.load()` requires an **externally approved exact
report digest**, supplied independently of the file. It rejects altered files,
unknown fields (including GT/expected-time fields), incomplete review scope,
non-hash bindings, invalid cadence and a mismatched release-consumer fingerprint.
The certificate binds:

- source SHA and the recording-player subject token;
- original image recognizer, profile and dependency fingerprints;
- native cadence and a release fingerprint covering the consumer and downstream
  FactBuilder source;
- split-independence review and production-adoption review hashes;
- recording-player binding, victim role, report transition, native temporal
  continuity and negative-control qualification review hashes.

**The loader verifies an authorization artifact; it is not an image-accuracy or
split-independence evaluator.** Referenced evidence and actual outcomes must be
independently reviewed before deployment configuration supplies an approved
digest. A digest computed automatically from an unreviewed report is not
approval. No production CLI, configuration, valid real-source certificate or
automatic digest approval is introduced here. Tests create explicitly synthetic
certificates solely to exercise the integration contract.

No existing Qualification Pack is edited or reinterpreted. The certificate is a
new private experimental deployment artifact, not a public HUD/Package schema
migration. Real adoption remains subject to qualification and approval.

## Numeric and temporal requirements

The consumer requires the existing three distinct, disjoint source roles:
source-player binding, victim and death transition. They must already be
reviewed SELF observations of the certificate's single recording-player token,
with actual finite numeric support >= 0.90. Unknown, nonself, candidate-review,
geometric-only, conflicting, overlapping and same-method witnesses reject.

All source contexts/fingerprints must match. Every intervening native frame must
be present, ordered, nonduplicated and in the same segment; explicit source
breaks, missing continuity provenance and respawn conflict reject. Continuity
hashes retain provenance; their mere existence does not qualify their semantic
contents. The approved qualification must cover the actual native continuity
producer. Future native wiring must supply its genuine records, not arbitrary
booleans, fabricated proof hashes or diagnostic packets relabeled qualified.

Confirmation additionally requires current reviewed marker, numeric victim and
Report support in **every** final corroborating frame: at least three frames
spanning at least 0.05 seconds, within the existing one-second onset horizon.
Dropout restarts the complete run. Generic current Report presence cannot
substitute for the separate original self-referential death-transition witness.

Event confidence is the minimum of the parent support, original onset/role
witnesses and all contributing current-frame supports. Geometry has no invented
numeric score. No acceptance threshold or existing probe behavior changes.

## Native event, association, persistence and downstream safety

Only an accepted proof constructs the existing six-field native event shape:
`player_death`, actor `player`, actual original onset time, deterministic event
ID, measured confidence and attributes. Later confirmation is separate in
provenance. IDs use physical source/subject/onset PTS and time base, excluding
decoder-session IDs, GT and inferred round numbers.

Existing attributes retain onset/confirmation bindings, original role witnesses,
the complete source chain, corroboration evidence and review digests. No unknown
victim name, killer agent or damage is filled. This event identifies its subject;
it does not set live HUD identity, owner, state, HP, Armor, Weapon, Ammo or Alive.
The stable native event ID is also retained in provenance, since the existing
trace adapter does not export that native top-level property. Fact event-ID
references can therefore be traced to the retained source event without changing
the adapter's public output shape.

The integration test uses the existing RoundPackageBuilder, FactBuilder, trace
adapter and SQLite repository. A synthetic confirmation after the first round
end still associates the earlier onset with that first round, not the next.
Fact confidence/provenance and all event attributes survive storage and trace;
HUD ownership remains unknown. No public schema or database migration is needed.

A downstream regression was reproduced before enabling any real event: the
existing normalizer inferred `first_death_by_player=True` from a single Death
event and no earlier *detected* elimination. This new producer observes only
Self Death, so it cannot establish a complete elimination timeline. It now
declares `elimination_coverage=self_death_only` in provenance. FactBuilder retains
the verified `player_died` Fact and its confidence/event reference, but withholds
the ordering Fact for this explicitly limited scope. All source events remain
available. Legacy events without this new scope keep their previous behavior;
their ordering semantics are not newly qualified by this change. The release
fingerprint includes this downstream guard, so changing it invalidates an
approval. The regression fails before the guard and passes afterward.

The consumer's JSON checkpoint retains released event IDs, exact approval digest
and consumer fingerprint. Repeated episodes and re-decoded source epochs keep
the same event identity; resume suppresses duplicates. Mismatched certificates,
source-code fingerprints and malformed state reject before replacing state.
Connecting this checkpoint to the application resume lifecycle is still future
work; a JSON round-trip test is not a claim of full application resume coverage.

## Verification and limits

Local results: **251 related tests passed in 40.72 seconds**, including 41 new
authorization, current-frame corroboration, source-break/respawn, confidence,
role-independence, duplicate/resume and Package/Fact/Trace/SQLite contract tests.
Another 82 Fact/HP/shared-timer/source-confidence **unit tests** passed in 32.73
seconds; these are not the canonical 82 assertions. Ruff passes the existing CI
scope plus the image replay runner; mypy passes all 144 checked files. The
text-I/O gate initially caught five implicit encodings; those operations now
explicitly use UTF-8 and the local audit reports zero unresolved contracts.
Remote CI is pending for the corrected change.

All positive integration cases here are synthetic. Existing real-source
recognition results retain their original fingerprints and unqualified status.
No new canonical targeted/sampled/Full evaluation is claimed; no Full was run.

| Result | Previous | Current |
| --- | --- | --- |
| Adopted Full | 23 / 55 / 4 | No new run |
| Archived unadopted Strict Full | 28 / 50 / 4 | No new run |
| Independent real-source numeric qualification | Incomplete | Incomplete |
| Installed real-source adoption approval | None | None |
| Native Event/Fact/Package/Trace/SQLite connection | Missing consumer | Synthetic contract verified |
| New real-video PASS assertions | Unproven | Unmeasured |

## Remaining work toward the actual goal

1. Complete independently reviewed source-positive/negative qualification for
   the frozen numeric reader/profile. Exposed development episodes do not become
   new blind holdout. The source-2 geometry-only cases cannot satisfy this
   numeric consumer; the separate structural-role decision remains separate.
2. Produce genuinely qualified current-frame Self observations and continuity
   records from the native analyzer entrance. Do not promote saved diagnostic
   packets or copy unknown observations into reviewed SELF.
3. Only after qualification and adoption review, configure an approved report
   digest and wire the opt-in native consumer/checkpoint entrance. Preserve the
   default legacy path, terminal integrity checks and exclusion policies.
4. Run canonical targeted evaluation and fixed sampled regression under the
   same evaluation contract. The first conditional targets are death-count
   constraints; point assertions still need actual missing semantic fields.
5. Run Full only for an independently qualified positive hypothesis that
   survives those checks. Publish measured gains/regressions, not projections.

The goal remains incomplete: a verified transport contract is not independently
qualified recognition, formal production adoption or Strict E2E FAIL reduction.

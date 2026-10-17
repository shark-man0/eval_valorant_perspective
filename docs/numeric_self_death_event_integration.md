# Numeric Self Death: qualified-candidate event integration prototype

Status: **experimental integration; real-source qualification and native
application wiring remain incomplete. No real-video PASS gain is claimed.**
The existing goal authorizes candidate E2E after independent qualification.
This implementation does not add a production-adoption permission requirement
before candidate evaluation. Main adoption remains a separate review decision.

Start recognition branch: `cfac17ac532b04367dda7f680517493bc1b4a69b`.
Fetched main: `7e480c2f2f7f49aea73e1541d065d78881d2f11c`.
PR #44/#46, legacy HUD ownership guards and PR #54's separate decoder fix are
preserved. No old recognition fingerprint or qualification is rewritten.

## Connection and qualification boundary

`experimental/numeric_death_release.py` adds a default-disabled consumer for
independently qualified numeric Self proof. Current real-source observations
remain UNKNOWN/CANDIDATE and are insufficient for this consumer. It does not
upgrade their identity, review state or confidence. No real qualification
certificate or native application caller is installed.

`QualifiedNumericDeathContract.load()` binds a reviewed qualification artifact
using its expected SHA supplied by trusted candidate-run configuration. It
rejects changed files, unknown/GT fields, incomplete component scope, invalid
hashes/cadence and mismatched consumer fingerprints. The private artifact binds:

- source SHA and the recording-player subject token;
- original recognizer, profile and dependency fingerprints;
- native cadence and consumer plus downstream FactBuilder source;
- split-independence and qualification-review hashes;
- recording-player binding, victim role, report transition, native temporal
  continuity and negative-control qualification review hashes;
- the exclusive `qualified_candidate_evaluation` scope; production scope rejects.

**The loader is an integrity/qualification-artifact boundary, not an image
accuracy or split-independence evaluator.** Actual evidence, metrics and exposure
must be verified before accepting a report. Computing a digest of an unreviewed
file does not qualify it. Tests use explicitly synthetic reports, never a real
qualification grant. A Boolean switch cannot replace the typed qualification.
No existing Qualification Pack, public native schema or database schema changes.

## Numeric method and temporal contract

All three original source roles must already be reviewed SELF observations of
one source-bound recording-player token, each with finite measured support
>= 0.90 and the supported method:

| Role | Accepted method |
| --- | --- |
| Recording-player binding | `killfeed_highlight_shape_color_v1` |
| Victim position | `killfeed_weapon_template_ncc_v1` |
| Original death transition | `fresh_self_referential_report_caption_ncc_v1` |

The admitted method pairs are immutable and covered by the consumer fingerprint.
An accidentally high score on geometric output, a global timer or a generic
Report header cannot substitute for these methods. Three synthetic misuse cases
failed before this method guard and reject afterward. Numeric thresholds are
unchanged; no score is manufactured for geometry. Source-2 geometry-only cases
still cannot enter this numeric consumer. The structural-role proposal remains
separate and is not a prerequisite for the existing numeric route.

Witness methods and ROIs must be independent. Every intervening native frame
must be ordered, nonduplicated, same-segment and retain continuity provenance;
breaks, gaps, missing proof or respawn conflict reject. A proof hash alone does
not qualify semantic continuity: the actual native producer must have independent
qualification and future wiring must supply its genuine records.

Every final corroborating frame needs current reviewed marker, numeric victim
and Report support: at least three frames spanning at least 0.05 seconds within
the existing one-second onset horizon. Dropout restarts the complete run.
Qualified independent header presence can corroborate current Report presence
but cannot open the separate self-referential onset. Global Report presence
need not claim player identity. Confidence is the minimum of original onset,
roles, parent support and every contributing current-frame support.

## Native event, Fact, association, trace and storage

An accepted proof produces the existing six-field `player_death` shape with
actor `player`, original onset PTS/time base, measured confidence and deterministic
identity. Confirmation remains separate in provenance. IDs exclude GT, round
numbers and decoder-session randomness. Existing attributes retain qualification
scope/references, all source bindings, original witnesses and corroboration.
Native event ID is also retained in provenance because the current trace adapter
does not export that top-level native field.

The integration test exercises the existing RoundPackageBuilder, FactBuilder,
trace adapter and SQLite repository. Confirmation after one round ends still
associates its earlier onset with that round. Source proof, attributes, confidence
and Fact event references survive storage and trace. Unknown victim name, killer
agent and damage are not filled. HUD identity/owner, HP, Armor, Ammo, Weapon and
Alive are not promoted by the event.

A reproduced downstream issue inferred `first_death_by_player=True` from one
Death and no earlier *detected* elimination. This producer observes Self Death
only; it cannot establish complete elimination coverage. It declares
`elimination_coverage=self_death_only`. FactBuilder retains `player_died` with its
original confidence/provenance and withholds the unsupported ordering Fact for
that explicitly limited scope. All source events remain available. Legacy event
normalization stays compatible; its ordering semantics are not newly qualified.
The release fingerprint includes this guard and invalidates if it changes.

JSON checkpoints bind qualification digest and consumer fingerprint and preserve
released IDs. Repeated episodes and new decode epochs retain the same identity;
resume suppresses duplicates. Mismatched/malformed state rejects atomically.
Application-level resume integration remains future work; this contract test is
not a claim of complete application resume coverage.

## Verification and remaining goal

Final local validation: 259 related tests passed in41.77sec (including49 new
consumer tests);82 additional Fact/HP/timer/confidence unit tests passed
in32.73sec. Those82 unit cases are not the canonical82assertions. Ruff, mypy
(144files) and the zero-unresolved text-I/O audit pass. Results are recorded
alongside the source revision in
[PR #53](https://github.com/shark-man0/eval_valorant_perspective/pull/53), including
Ruff, mypy, zero-unresolved text-I/O audit and Linux/Windows CI. Source `8f24020`
previously passed all five remote checks: Linux 4,055 passed/7 skipped (87.03%
coverage), Windows 4,051 passed/11 skipped (86.99%), UTF-8-disabled 13 passed,
packaging/smoke successful. Subsequent method/scope changes have separate CI;
those prior results are not silently assigned to different source bytes.

The original image-runtime fingerprint remains unchanged. A transport-only check
binds both original real-source prediction artifacts and keeps their
UNKNOWN/CANDIDATE state, zero formal events and original fingerprints. It is not
a new recognition run. Positive integration tests are synthetic. No new
canonical targeted/sampled/Full result or PASS increase is claimed.

| Result | Previous | Current |
| --- | --- | --- |
| Adopted Full | 23 / 55 / 4 | No new run |
| Archived unadopted Strict Full | 28 / 50 / 4 | No new run |
| Independent real-source numeric qualification | Incomplete | Incomplete |
| Event/Fact/Package/Trace/SQLite connection | Missing consumer | Synthetic contract verified |
| Actual canonical PASS gain | Unproven | Unmeasured |

Remaining work: complete source-backed independent numeric qualification;
produce genuinely qualified current-frame Self observations and continuity
records at the native entrance; wire candidate-mode processing and application
resume; then run same-contract canonical targeted and fixed sampled regression.
Point Death predicates still need actual missing victim/killer/damage fields.
Full requires an independently qualified positive hypothesis surviving these
checks. Main adoption is not automatic. The goal remains incomplete.

Follow-up: the [image session adapter](numeric_self_death_image_session.md) now
joins actual image predictions with original, separately reviewed frame
witnesses and this consumer. Its source is also bound by the release fingerprint.
It does not provide the missing independently qualified subject/continuity
producer or enable an application caller; real-source default output remains
empty. Original recognizer/profile fingerprints are preserved.

# Development recorder association and observed paths

This opt-in study connects existing image readers to a concrete marker observation
and follows that observation through verified native acquisitions. It does not
change Production ownership, events, map definitions, thresholds or defaults.

## Independent states

`development_owner_state` keeps recorder life, camera presentation, marker binding,
current image position, and map/zone measurements separate. Spectator UI alone
sets the camera to spectator; recorder death remains UNKNOWN. A self-to-spectator
edge, direct recorder death, other-player death, and a spectator-only hypothesis
have distinct fields. Direct life evidence requires a recorder-subject receipt.
The PR107 state machine is retained only as an explicitly named legacy hypothesis.

A current agent signature plus visible HP is one correlated HUD evidence family.
The source roster associates the recording with an agent; neither proves the
current account. The minimap rim can highlight a Spike or spectated target.
Consequently the automatic result is `first_person_candidate`, recorder life is
UNKNOWN, account ownership is UNKNOWN, and formal outputs remain zero.

`development_owner_binding` requires same-frame source/pixel/pool bindings, a
source-bound recorder-agent reference, current positive HUD agent evidence,
readable positive visible-subject HP, and a unique rim/portrait-consistent window.
Positive spectator/name-slot evidence vetoes a proposal. The ID is derived from
the current native sample and candidate pool. Human per-frame candidate IDs are
not runtime inputs. Source roster/reference reviews are separate prior metadata.
The existing portrait inspector's peak/contrast policy is reused; its scores are
not compared with an unrelated ability-glyph threshold.

## Tracking and gaps

`development_owner_tracking` reuses PR109 `DevelopmentMarkerAssociations` for
mutual appearance and position links. A small native blur reduces pixel-shift
sensitivity; candidate centers are unchanged. The existing 0.90 cosine, 12px
endpoint distance and 0.10 mutual margin remain unchanged. Source, epoch,
timebase, pixels, ROI, Profile, map/build, reference and feature identities must
match. Native continuity receipts are required; close timestamps alone cannot link.

The initial association has a stable, unqualified identity lineage. Frame marker
observation IDs remain separate. Missing observations suspend the identity and
clear current position/map/zone. A unique appearance-and-distance reappearance is
bounded to 0.6 seconds of verified acquisition continuity. It starts a new observed
segment; no missing position or connecting path is invented. Ambiguous reappearance
and contradictory reinitialization keep current position UNKNOWN. Agreeing UI
refreshes retain the segment. Spectator/view/context changes discard the binding.

Each connection explicitly means observed endpoints, not the actual continuous
movement between them. A coordinate jump limit does not measure absolute accuracy.

## Map and Zone connection

Current measurements retain geometry-only candidate coordinates. The proposal
calibration envelope now preserves its actual measured confidence, previously
omitted at this API boundary. Missing confidence is still rejected by ZoneResolver;
no replacement confidence is invented. Resolve candidates through the isolated
development registry with `controlled_player=False`, reset on missing/segment
breaks, and tag the nested result `development_only` / ownership UNKNOWN.
No Production consumer is invoked. Zone observations and endpoint-bracketed spans
are not guaranteed occupancy or tactical evaluations.

## Measured development comparison

Two accepted DEVELOPMENT recordings, five short native-frame windows, 140 sampled
observations. This is exposed development evidence, not independent qualification.
Methods and the new interval selection were fixed before decoding that interval.

| Window | Observations | Legacy position candidates | Frame UI binding proposals | Tracked map candidates | Named Zone candidates |
|---|---:|---:|---:|---:|---:|
| Haven moving/static | 30 | 27 | 1 | 26 | 15 |
| Bind purchase/start | 30 | 26 | 26 | 29 | 0 |
| Additional Haven movement | 30 | 22 | 3 | 26 | 0 |
| Spectator contexts, two windows | 50 | 0 | 0 | 0 | 0 |

Legacy coordinates are unqualified candidates too; they are not zero merely because
there is no automatic owner initializer. The moving/static window loses one
coordinate observation versus legacy. Retained raw candidate pools do not change,
but selected-path coverage is not uniformly better. The additional Haven interval
has four more map observations. Neither increase alone proves correct ownership.

One initial Haven selection and three additional-interval initial selections were
independently reviewed as recorder markers after predictions were frozen. These
are frame-only proposals; one is a UI refresh in the temporal run. Of the four
temporal starts, three have direct role reviews; the Bind start remains unreviewed. A
highlighted Spike was reviewed as UI and was not initialized as recorder. Exact
review roles are evaluation only. The two already-reviewed static coordinate
samples and one Bind sample provide limited coordinate comparisons; unreviewed
path points remain unreviewed. Click agreement is not world-position accuracy.

The longest observed segment is 4.6 seconds. A moving segment has eight observations
over 1.4 seconds in the original Haven window; the new Haven window includes a
15-observation moving segment over 2.8 seconds. The 18 previously reviewed static
observations are all retrieved, with zero spread in reference-image pixels on
these samples only. None of this qualifies intervening movement or global accuracy.

An old Bind reference lacked source/agent binding metadata. Its exact patch was
verified in both the original reference frame and the previously human-reviewed
image, then joined to the existing source roster. No new template pixels, later
frame labels or threshold changes were used. This is provenance repair, separate
from the tracking algorithm improvement.

Recorder life and formal ownership remain UNKNOWN in all 140 observations.
Direct recorder-death/revival/round-return recognition has not been demonstrated.
The current-account link is still unqualified. General misattribution rate and
independent physical-match transfer accuracy remain unmeasured.

## Reuse and reproducibility

Base: PR109 `259a051a18700cb4f2de5cf68003c4af45eb96a4`.
Only `development_self_timeline.py` and its tests are reused from PR107
`c5bdd4f42ed5aadf1d1b9a9767e5e5c047441f87`; only
`development_learning_runs.py` and its tests are reused from PR110
`9459e0b269fd4275ee1747f614bedebe9cd35883`. No wholesale research-branch merge occurs.
The existing dataset contract is already in the base. PR110's source-bound feature
cache is exercised on native appearance vectors and exact reuse is verified.
Immutable trial history records both failed attempts and limited reviewed results.
It cannot activate a Production model. No new SSL training or Terra session is used.

Private input manifests, native frames, profiles, identities, PTS, coordinates,
review responses, feature caches, histories and HTML stay outside Git. Only source,
synthetic tests and aggregate documentation are published. The common CI checker
remains in its dedicated PR104 checkout. Main is not merged.

## Adoption boundary

Implementation and the real development pipeline are demonstrated. Limited initial
association/interval gains are measured, but the default recognizer is retained:
current-account proof, direct recorder-life evidence, broader independent role and
coordinate evaluation, and cross-recording transfer are still required. This work
does not complete Issue105 or establish independent qualification.

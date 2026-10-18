# Self Death: luminance binding and explicit ability separator

Status: **one previously missed development episode recognized as an unqualified
candidate; independent qualification, formal Event integration and canonical
FAIL reduction remain incomplete**. Branch start `98ee45521799b3f431c35c5869547220bdd3daca`;
fetched main `7e480c2f2f7f49aea73e1541d065d78881d2f11c`.

## Reproduced failure and implementation

The [ability-episode investigation](self_death_ability_episode_measurement.md)
found two separate blockers: sparse source-player outline support and an ability
pictogram unsupported by the weapon separator bank. A frozen-box audit found no
accepted outline discarded by the search screen. The middle binary mask failed
on 83/106 post-caption frames. Adding just an ability image would not have
satisfied the existing temporal requirements.

The experimental reader now supports explicitly selected
`grayscale_yellow_outline_v1`. It measures the current luminance raster against
a separately calibrated luminance reference, requiring all three existing
disjoint structural supports at NCC >=0.90 and the existing independent yellow
color fraction >=0.90. This is a different fingerprinted feature, not a lower
binary-color threshold. Existing binary features remain their original paths;
there is no automatic fallback and no qualification transfer. Current pixel,
source, profile and executable-code binding remain mandatory.

An explicit ability-reference bank adds the second missing measurement. Ability
templates require their own measured NCC >=0.90 plus the current plain team
plate fraction >=0.90. Their position relative to the independently located
recording-player portrait determines killer/victim role. Duplicate templates
of one glyph do not provide extra corroboration. Conflicting weapon/ability
matches remain ambiguous. Names, timestamps and expected identities do not
select templates or roles.

Ability measurements use `ability_roi`, `ability_support` and
`ability_plate_fraction`. They leave `weapon_roi`, `weapon_support`, weapon
geometry and weapon plate support absent. Candidate witness transport uses
`killfeed_ability_template_ncc_v1`, retaining its actual current pixels and score.
It does not relabel an ability as a weapon or promote its subject from UNKNOWN.

Private diagnostic profile v4 requires a canonical, contiguous explicit ability
bank. Profiles v1-v3 reject ability arrays. v4 preserves v3's separately
calibrated caption/presence rectangles, exact-match provenance and native-window
cloning. Public HUD, Event, RoundPackage and SQLite schemas are unchanged.

The source image recognizer may form an **unqualified diagnostic prediction**
using the new numeric evidence and its unchanged temporal policy. The formal
consumer's method whitelist is unchanged: a weapon qualification cannot release
an ability witness. No profile or certificate is installed in the application.
This development path grants no HP, Alive, Weapon, Shot or other owned Fact.

## Frozen development data

One already exposed final image supplies the luminance border reference and the
ability pictogram. The pictogram has three pixels of plain plate above/below;
it contains no player name or numeric field. All old masks, weapon references,
Report assets and calibration arrays are preserved byte-for-byte. The reference
was frozen before the full comparative replays.

The original three-second episode contains every native frame: 181 images.
Three frozen control windows first contribute 31 consecutive frames each for a
274-frame comparison. Each window resets observation context; no evidence is
joined across the unobserved intervals. Both sides freshly recognize identical
PTS/pixels with identical code, dependency hashes and OpenCV settings. No old
recognition is re-signed. Source/encoded/pixel/config/asset terminal checks pass.

All frames are development/regression inputs. The training episode was already
exposed, and the wider recording's historical exposure ledger is incomplete.
These results are **not blind holdout or independent producer qualification**.

## Measured results

First, the luminance-only implementation was compared with the unchanged binary
feature. Its exact intermediate source is privately preserved at SHA-256
`32909181dc91c12f0f8f9532366d26ea03fb17506691b80baba87e2ee206ab2d`.
The two profiles ran under the same intermediate executable and dependencies.

| Episode metric | Binary | Luminance | Delta |
| --- | ---: | ---: | ---: |
| Recording-marker readings | 22 | 60 | +38 |
| Marker frames in first second after caption onset | 2 | 20 | +18 |
| Runs meeting the original temporal duration in that second | 0 | 2 | +2 |
| Victim-role readings | 0 | 0 | 0 |
| Death predictions | 0 | 0 | 0 |

This established a viable current-frame binding hypothesis without pretending
that unknown role was sufficient. Next, the completed implementation freshly
compared v3 luminance-only against v4 luminance plus ability on the same 274
frames, using identical final source and dependencies.

| Episode/control metric | Without ability | With ability | Delta |
| --- | ---: | ---: | ---: |
| Episode recording-marker readings | 60 | 60 | 0 |
| Episode victim-role readings | 0 | 60 | +60 |
| Correct diagnostic predictions in the reviewed episode | 0 | 1 | +1 |
| Missed reviewed development episodes | 1 | 0 | -1 |
| New predictions in the three short controls | 0 | 0 | 0 |
| Formal Events / qualification grants | 0 / 0 | 0 / 0 | 0 / 0 |

The one prediction retains the original caption-onset PTS; confirmation occurs
0.6 seconds later. Actual candidate support is 0.9375, bounded by measured
current-image support. Its ability NCC is 0.989262 and plate support 1.0; no
weapon score is assigned. The source-backed typed witness remains CANDIDATE /
UNKNOWN and default formal release returns no Event. This is not independently
labeled boundary-time accuracy or an E2E acceptance-window result.

Complete comparison wall time was 390.347 seconds without ability and 416.354
seconds with ability (+26.006 seconds, +6.66%). Recognition time was 247.399 and
273.463 seconds respectively; Python peak RSS was 95,059,968 and 91,906,048
bytes. These are single observations, not a speed benchmark or memory trend.
Both comparisons used OpenCV's recorded four threads; they are not the earlier
one-thread report-geometry experiment. No internal parallelization was adopted
or qualified by this work.

## Expanded negative and legacy checks

The short killer control contained no accepted source-player marker. It was
therefore insufficient to establish behavior on an actual highlighted killer.
The v4 reader was subsequently run on **all 363 native frames** of the three
original controls, without changing the frozen profile.

| Full exposed control | Frames | Observed roles | New predictions |
| --- | ---: | --- | ---: |
| Nonself killfeed / ability view | 121 | no accepted recorder marker | 0 |
| Recording player as killer | 121 | 60 killer, 7 unknown | 0 |
| Cold post-death, persistent self Report | 121 | 99 victim | 0 |

Repeated correlated frames are not independent successes. No unknown role is
filled. Total wall time was 525.311 seconds, recognition 381.102 seconds, peak
Python RSS 97,873,920 bytes. Source-blocked frames were zero; this is not a
blanket qualification of semantic continuity.

The unchanged legacy profile was also freshly run with final source on all 171
original native regression frames. Its two known diagnostic episodes remain
two, with zero new predictions in the persistent-report/spectator windows and
zero source-blocked frames. Wall time was 224.526 seconds and recognition time
196.316 seconds. This checks legacy behavior; it does not test the new reference
on all previous sources or grant the old qualification to new executable bytes.

## Tests and remaining acceptance work

### Frozen cross-context and cross-source regression

After the feature and ability bank were committed at `6eafb85`, the exact same
references were tested on two other already exposed source-2 episodes and the
source-1 legacy windows. No further reference, mask, threshold or temporal
parameter was adjusted. Source-1's diagnostic profile explicitly binds its own
video SHA and restores both Report rectangles to that source's original search
geometry; all other original configuration and asset arrays remain identical
outside the selected marker feature/reference and added ability bank.
Changing source binding is not qualification transfer.

| Regression cohort | Native frames | Unique known episodes detected | New control predictions |
| --- | ---: | ---: | ---: |
| Other source-2 episodes | 362 | 2 / 2 | no control windows in this cohort |
| Source-1 legacy windows | 171 | 2 / 2 | 0 |

The source-1 cohort deliberately includes two overlapping R1 windows. It yields
three per-window predictions but only **two distinct death episodes**. Treating
these as three true positives would double-count R1. The short 24-frame R1
window, previously too short to confirm a candidate with the binary profile,
now confirms one; the longer R1 window confirms the same original onset. These
are independent recognizer contexts, not a claim of three events in one match.

The source-2 known onsets and confirmation times remain unchanged. Source-1
onset PTS also remain unchanged: confirmation delay is now 0.1 seconds for both
episodes, compared with 0.4 seconds for the prior longer R1 replay and about
0.1167 seconds for R2. Nothing backdates an event or moves an onset toward GT.
Source-1's unique recording-marker role readings remain numeric, with no ability
score borrowed into its weapon measurements. These results show transfer of the
frozen reference across exposed contexts, **not independent or blind holdout**.

Source-2 wall/recognition time was 552.089 / 392.973 seconds and peak Python RSS
97,071,104 bytes. Source-1 was 227.771 / 199.465 seconds and 98,729,984 bytes.
Every source/config/encoded/pixel terminal check passed; no source-blocked frame
or formal Event was produced. Both used the previously recorded four-thread
dependency fingerprint; no parallel full-video jobs or new sampling was used.

Private records: `luminance-ability-cross-context-plan.json`,
`luminance-ability-cross-context-source2-manifest.json`,
`luminance-ability-cross-source1-profile-v4.json`,
`luminance-ability-cross-context-{source1,source2}-replay.json` and
`luminance-ability-cross-context-execution.json`.

### Canonical Death predicates still need more than a released event

Read-only inspection of the unchanged private assertion definitions and
reference evaluator confirms two different requirements:

- `event_count_constraints-001` and `event_count_constraints-005` count
  `player_death` events with the required actor and native Round association.
  They do not require the three point-event semantic attributes below.
- `GT-R1-DEATH` and `GT-R2-DEATH` additionally require the exact independently
  read `victim_name`, `killer_agent` and `combat_report_damage_received`, as well
  as type, actor, Round association and the original acceptance window.

The scoped numeric release producer deliberately emits no guessed victim name,
killer agent or damage. Consequently, independently qualifying and integrating
the present detector alone cannot establish those two point assertions. At
most the two count assertions are direct candidates for improvement, conditional
on qualification, actual release, correct native package membership, exactly one
event per episode and no regression elsewhere. This is a dependency analysis,
not a measured or guaranteed PASS gain. No event or Round ID was copied from GT
to demonstrate it.

At source-1 confirmation, the raw accepted victim-name reader is present for R1
(confidence 0.909972) but absent for R2. R1's accepted string is retained in the
raw reading; it is not automatically a qualified Event attribute, and no name
is propagated from R1 to R2. Killer-agent and received-damage extraction remain
separate producer work. This distinguishes missing semantic observation from
intentional lack of formal adoption; simply releasing every candidate would
not complete all four Death-related assertions.

The next qualification input must supply positive and negative source episodes
that were not used to develop this Self Death recognizer. The existing two
recordings' reused development images cannot become a new blind holdout.
One of the previously identified supplemental originals may provide suitable
source-held-out evidence, but its contents and size must be checked before a
transfer; its prior Round-calibration exposure must still be disclosed. No
supplemental source is assumed to contain a death or to be automatically blind.

Local related unit/integration suite: **231 passed in 63.30 seconds**. Ruff
passes for the repository CI scope (`src tests scripts/e2e`) plus the changed
diagnostic runner. mypy passes for 145 source files including that runner.
An exploratory unrestricted `ruff check .` also inspected private validation
and out-of-scope diagnostic scripts and failed with 390 findings. No GT, pack,
or unrelated script was modified to conceal them. CI results must be read from
the exact pushed commit; historical green checks are not new-code evidence.

Regression tests cover explicit feature selection, independent support loss,
gray non-yellow lookalikes, source/profile mismatch, mirrored killer/victim,
ability/weapon conflict, plain-plate absence, duplicate templates, missing
separator, native confirmation, duplicate suppression, v4/legacy loading and
actual method/provenance transport. A new release test explicitly rejects an
ability method under the old weapon qualification even at high numeric support.
Synthetic passes prove these contracts, not real-video accuracy.

No canonical targeted, fixed sampled or Full E2E was run: the remaining gate is
independent qualification of source binding, ability role and native temporal
evidence, followed by an appropriately reviewed formal-consumer integration.
Existing certificates may not be reused across the new code/feature/profile.
The actual qualified image/continuity provider is still missing. New-method
release must not be enabled from this one development true positive.

Adopted Full remains historical **23/55/4**; archived unadopted Strict Full
**28/50/4** and the separate timing-policy comparison remain distinct. Current
canonical PASS/FAIL/NE, PASS-to-FAIL changes and canonical negative/discontinuity
violations are **not remeasured**. No new canonical PASS, production adoption,
main merge or goal completion is claimed.

Private reproduction assets include `gray-border-feasibility-*`,
`luminance-border-development-*`, `luminance-border-*-replay.json`,
`luminance-ability-development-freeze.json`,
`luminance-ability-{without,with}-ability-replay.json`,
`luminance-ability-full-controls-*`,
`luminance-ability-legacy-regression-*` and
`luminance-ability-witness-transport.json`. Original sources, images and profile
arrays stay outside Git; only code, synthetic tests and aggregate results are
published.

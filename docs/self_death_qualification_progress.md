# Self Death qualification and semantic Event connection

Status: **B — candidate recognition and gated attribute transport improved;
independent qualification and Strict E2E improvement remain incomplete**.
Start branch `dbedfa3bba100ada6c6f91b2912cfb48fe22c32a`; fetched main
`7e480c2f2f7f49aea73e1541d065d78881d2f11c`. PR #53 remains stacked on PR #52,
Draft, with no main merge. The earlier
[convergence report](e2e_validation_convergence.md) remains the historical E2E
baseline, not a current-reader result.

Latest static source measurements are recorded separately in the
[fixed component audit](self_death_fixed_source_component_audit.md): 192 images,
11 correct Self/role rows, four missed Self rows, zero observed false Self/role
outputs, and five correct Report damage readings. Independent Victim/temporal
qualification and formal Death remain incomplete; this is not a new canonical
E2E result or a replacement for the exposure limitations below.

The follow-up [scoped attribute/timing report](self_death_scoped_attributes_and_timing.md)
adds an opt-in internal v2 certificate with an exact reviewed killer-class scope,
while preserving v1 and all Subject/fatal-row checks. A native source timing
review supports the original onset in one known episode; menu closure in its
negative control is explicitly not proof of Report absence. No real certificate
or formal Death is installed by these changes.

The [bounded qualification workflow](self_death_bounded_qualification_workflow.md)
adds a diagnostic-only native-window decoder option using the existing verified
decoder and a temporary PNG cap. Fresh decoding of 84 known source frames
matches the prior same-image-producer results, including both diagnostic deaths
and the persistent-Report control. It does not qualify Subject/absence or
produce a canonical PASS; independent qualification remains outstanding.

## Connection audit

| Stage | Implemented | Actual-image measurement | Independent qualification | Formal application connection / first blocker |
| --- | --- | --- | --- | --- |
| Source image / native PTS | Yes, existing decoder and SHA/pixel bindings | Yes | No new whole-source assurance grant | Existing entrance; historical source exposure remains explicit |
| Recorder marker / killer-victim role | Yes, `killfeed_subject.py` | Yes, including the new case below | Incomplete | Candidate reader; geometric role cannot substitute for numeric NCC |
| Subject evidence | Typed models and [source-backed provider](numeric_self_death_subject_provider.md) | Numeric image witnesses retained; provider positive tested synthetically | Incomplete | Provider supports qualified scene or explicit source-assured input; no real Subject qualification installed |
| Episode evidence | Existing fresh Report + victim onset and native corroboration | Yes | Incomplete | Diagnostic only; persistent Report cannot open an episode |
| Fatal row / received damage / portrait | Existing independent readers and episode collector | Existing source-backed measurements | Incomplete | Candidate fields do not establish semantic Event attributes |
| Qualified Death decision | Existing exact-fingerprint numeric qualification loader and consumer | No qualified real decision | Missing real certificate | Default emits nothing; synthetic decisions are contract tests only |
| Semantic Event attributes | Added gated projection from existing episode fields | Candidate field availability already measured; no qualified real emission | Separate attribute certificate required | New opt-in session-to-consumer connection; no certificate shipped |
| Native Event → Round Package | Existing onset-based membership | No qualified real Death yet | Blocked upstream | Synthetic regression includes confirmation after the original Round ends |
| Package → Fact / Trace / SQLite | Existing contracts; attribute preservation tested | No qualified real Death yet | Blocked upstream | No player HUD identity/Alive/HP/Weapon promotion |
| Canonical evaluator | Existing unchanged evaluator | Historical 28/50/4 only | Not a current-code qualification | No new targeted/sampled/Full result claimed |

## New frozen-reader positive measurement

The local second recording was used; no additional video was transferred.
Before new replay, the reader/profile/assets were frozen and three native
source frames were visually reviewed. The review observes first-person play,
an actual death animation, the recorder marker on the victim side of an
independent weapon separator, a new self-referential Report and its fatal row.
Private names, Report values and images are absent from this public report.
No expected label, name, value or timestamp was passed into the recognizer.

The 367.750–369.250-second native window contains 91 frames. Selection used
an earlier caption-only keyframe localizer; historical geometry exposure is
unknown. This is a prospective frozen-reader role check, **not blind holdout,
independent qualification, a whole-match false-positive estimate or canonical
E2E**. There was no reference/ROI/threshold/horizon adjustment after inspecting
the outcome.

| Metric | Previous measurement for this case | Current | Delta |
| --- | --- | ---: | --- |
| Native frames | Not measured | 91 | Not comparable |
| Reviewed positive episodes detected | Not measured | 1 / 1 | Not comparable |
| Victim-role frames | Not measured | 36 | Not comparable |
| Accepted victim-name frames | Not measured | 32 | Not comparable |
| Extra episode predictions | Not measured | 0 | Not comparable |
| Qualified formal Death Events | 0 | 0 | 0 |
| Source-blocked frames | Not measured | 0 | Not comparable |
| Replay wall / recognition seconds | Not measured | 269.376 / 95.938 | Not comparable |
| Python peak RSS bytes | Not measured | 97,525,760 | Not comparable |

The candidate's original onset is **368.550**, confirmation **368.700** and
measured support **0.947606**. Unknown/pending/prediction/latched-duplicate
frame statuses are 53/4/1/33. The 33 duplicate statuses suppress repeat
issuance; they are not 33 emitted duplicate events. Multiple accepted frames
are correlated observations, not independent positive episodes.

The pre-replay visual review brackets the transition only between 368.500 and
369.250. It does not establish an exact boundary or ±0.1-second accuracy.
Terminal source/input hashes passed. Machine-readable aggregate evidence:
[self_death_qualification_progress.json](../e2e_reports/match_001/self_death_qualification_progress.json).
Private reproduction plan, source review, native manifest, CLI arguments,
execution and result remain under `qualification-20261018` in ignored outputs.

At confirmation, recorder-border supports are 0.969385/0.981458/0.971890,
yellow fraction 1.0, and accepted victim-name OCR 0.918629. The weapon separator
has actual connected-component geometry and plate measurements, **no weapon
NCC**. Neither plate support nor geometric acceptance is converted into NCC.
This case therefore remains outside the numeric formal release contract.
Nonself killer is visually reviewed, but no new automatic Nonself/Teammate/Enemy
classifier result or independent qualification is claimed.

## Implemented semantic attribute connection

Previously, `NumericSelfDeathEventConsumer` could construct a qualified count
event but always omitted `victim_name`, `killer_agent` and
`combat_report_damage_received`. The existing episode collector already retains
candidate names and Report fields at their own PTS, including a name read before
confirmation. Reimplementing those readers or filling the confirmation frame
was unnecessary.

The new internal `QualifiedDeathAttributeContract` is an explicit opt-in for an
already qualified numeric Event. It binds an externally trusted report digest,
the exact parent event-qualification digest, current release code, split review,
three semantic component reviews and the original Report/fatal-row producer
code/profile/dependency fingerprints. The loader verifies bindings; it does
**not** judge or manufacture semantic qualification or split independence.
No real certificate is included.

The image session passes the collector's original episode directly to the
consumer. Only after the existing Death acceptance checks succeed may attributes
be projected. Each contributing frame must itself satisfy the unchanged
reviewed numeric current-frame Self binding, victim and Report predicates;
confirmation's ownership cannot qualify an earlier unknown field frame.

- Victim name must match that exact source image's accepted victim OCR, ROI,
  method and measured confidence. Names are never supplied by GT or code.
- Received damage needs the exact original Report producer plus its same-frame
  fatal-row marker/ROI/producer and accepted support. An arbitrary damage value
  or generic Report is insufficient.
- Killer agent requires independently reviewed portrait semantics for the exact
  producer and a same-frame accepted fatal-row context. Portrait presence alone
  cannot establish a killer. Missing/conflicting damage context withholds it.
- Fields outside original onset–confirmation, changed sources/pixels/producers,
  contradictory accepted values, nonfinite/invalid confidence, missing evidence
  and unknown/unreviewed own-source identity withhold the affected attribute.
- Each attribute retains original source PTS/pixels, component provenance,
  measured confidence, association support and semantic review digest. It
  does not move the Event onset, raise Event confidence or fill another frame.

Count qualification and attribute qualification remain separate. Missing an
attribute does not fabricate a point-assertion PASS or invalidate independently
proved count evidence. Missing attribute qualification emits no semantic
attributes, even if candidates are available. `attribute_blockers` describes
withheld attributes without replacing the original Death `last_blocker`.

## Compatibility and safety

No public HUD/RoundPackage/Event Schema, GT, assertion, acceptance window,
identity authority, numerical confidence meaning, threshold, ownership guard,
sampler or default application caller changes. The new file format is an
internal experimental qualification certificate, separate from the existing
v1 numeric event certificate; it is not a public saved-data migration.
Candidate observations stay candidate/unqualified and are not mutated.

The release fingerprint now includes the attribute projection source. Old
qualification cannot authorize new release bytes. Opt-in consumer checkpoints
also bind the attribute certificate; count-only checkpoints keep their existing
shape. A checkpoint with a different attribute report cannot restore. SQLite
and Trace retain qualified attribute provenance using their existing event
attributes contract. Player HUD ownership remains unknown in the downstream
synthetic test, including with a qualified Event.

## Qualification still required

The new positive demonstrates a frozen reader finding an additional actual
death. It does not resolve historical exposure or qualify all roles/absence
readers. Remaining concrete requirements are:

1. Independently reviewed source-player marker and numeric killer/victim role
   positives/negatives under the exact intended profile. Self Killer, Nonself
   Victim/Killer and uncertain role must not become Self Death. Geometric-only
   roles need their separately proposed contract; existing NCC requirements
   remain intact.
2. Independent temporal controls for fresh versus persistent/reopened Report,
   spectator, respawn, repeats and source discontinuity. Existing developmental
   controls remain regression evidence, not a new blind cohort.
3. Independent semantic review for victim OCR, killer portrait association and
   fatal received-damage row, with class/geometry coverage matching the actual
   Report producer. Unsupported classes stay unknown.
4. A genuine qualified image/continuity witness provider and exact reviewed
   certificates. No provider is manufactured by relabeling candidate JSON.
5. Enabled-provider source-continuous validation followed by same-contract
   targeted canonical evaluation, fixed sampled regression and only then a
   justified Full run. Application-native wiring/resume remains incomplete.

No additional video transfer is a blanket prerequisite. Continue using the two
local originals and preserve uncertainty about exposure. The independent
review/split gaps cannot be replaced by more synthetic tests.

## E2E comparison and tests

| Metric | Historical adopted Full | Archived unadopted Strict | New reader/consumer canonical run | Delta |
| --- | ---: | ---: | --- | --- |
| PASS | 23 | 28 | Not measured | Not measured |
| FAIL | 55 | 50 | Not measured | Not measured |
| NOT_EVALUATED | 4 | 4 | Not measured | Not measured |
| Negative violations | 0 | 0 | Not measured | Not measured |
| Discontinuity assertion violations | 0 | 0 | Not measured | Not measured |

No new canonical PASS ID or regression ID is claimed. The separate timing-policy
30/49/3 is not a recognition result. Full was not started: independent
qualification and formal positive release are absent. Re-evaluating an unchanged
old Trace would not test this connection.

The final production change passed the 222-case
subject/Death/Report/ownership/Trace suite in 47.54 seconds. After adding the
explicit test that an attribute certificate cannot substitute for subject
qualification, all 42 focused attribute cases passed in 2.15 seconds.
Earlier runs (149 / 91 / 221 cases) are not added to those totals.
Current-commit remote CI is reported separately. Ruff passes and mypy passes
(147 source files). An initial `pytest` launcher collection failed because the
repository root was absent from its import path; the correct invocation is
`python3 -m pytest`. No assertion was skipped or relaxed.

Tests cover positive attributes, count-only compatibility, missing individual
fields, semantic conflicts, finite confidence, exact source/ROI/producer,
unknown own-source identity, changed certificates/code, dedup/checkpoint and
native Package/Fact/Trace/SQLite preservation with no HUD ownership promotion.
Before this change, Linux/Windows/text-I/O checks at starting head `dbedfa3`
were successful. Those checks are not assigned to new release bytes.


CI at the initial attribute commit `f1aa1f5` found one existing production
leakage-check failure on both operating systems: a digest parameter name
contained the reserved token `expected_event`. No GT value was read, but the
unchanged guard correctly blocked the new spelling. The parameter is now
`parent_qualification_sha256`; the certificate payload and runtime acceptance
are unchanged. The guard/test was not weakened. That first run otherwise had
4,224 passing Linux tests (87.14% coverage) and 4,220 passing Windows tests;
its failure is retained, not reported as successful CI. Current-source CI must
pass separately.

## Additional frozen source role/temporal cases

Source commit `80eeca2be377fd2503983939fd2481091b644e2d` adds the independently
gated numeric Subject provider described above. No real qualification is
installed. With the same unchanged v4 image reader/profile, two further local
source windows were frozen, decoded and visually reviewed before replay.
Their selection remains caption-conditioned and historical geometry exposure
unknown; they are not blind or independently qualified test cohorts.
No reference, ROI, threshold, role predicate or temporal horizon was adjusted.

| Case | Native frames | Diagnostic deaths / reviewed episodes | Onset → confirmation | Numeric victim frames | Formal Death |
| --- | ---: | ---: | --- | ---: | ---: |
| 002: recorder kills, then dies; two recorder rows coexist | 151 | 1 / 1 | 69.216667 → 69.333333 | 119 | 0 |
| 003: enemy and recorder share an agent class, different roles | 121 | 1 / 1 | 512.616667 → 512.716667 | 0 | 0 |

Case 002 supplies 149 recorder-killer row readings and 119 recorder-victim
readings; they coexist after the actual death. At confirmation the victim's
independent weapon NCC is **0.997985**, plate support 1.0 and candidate support
0.966339. At the pre-reviewed live frame, only the recorder-killer row is
accepted and the result is unknown. After the actual death, the new victim row
and fresh Report produce one candidate despite the old killer row. This checks
that an old Self Killer row neither becomes a Self Death nor vetoes a new,
independently observed victim row. Counts are correlated frame observations,
not hundreds of independent role/death successes.

There are **zero accepted victim names** in case 002: all 132 accepted strings
belong to its killer row. The episode collector must not borrow those names,
even though the source recorder is the same person. Count eligibility and
point-event semantic attributes remain separate. This is a concrete missing
victim OCR observation, not an attribute transport loss or a permission to
copy the other role's string.

Case 003 begins with a visually reviewed Nonself killfeed row while the recorder
is alive; both reviewed live frames yield no recorder Subject reading and no
prediction. The later actual death supplies 50 victim-role readings and one
candidate, support 0.972684. Its separator remains geometric, with no numeric
weapon NCC. Twenty-nine accepted victim-name readings include three between
onset and confirmation; their presence does not qualify the role or authorize
a formal Event. Sharing an agent portrait class does not establish identity.

Both windows have zero extra episode predictions and zero source-blocked
frames. The 115/47 latched duplicate statuses suppress repeated issuance.
Acquisition processed all 272 native frames without skipping, taking 569.329 s
and retaining 415,368,960 bytes of lossless PNGs through same-filesystem hard
links. No source video was transferred or copied. Recognition took 382.550 s,
replay wall 532.130 s, and Python peak RSS 91,693,056 bytes. Terminal source,
profile, dependency, encoded-frame and pixel hash checks passed.

Together with case 001, these new prospective windows contain three visually
reviewed episodes and three diagnostic predictions; only one has numeric
victim support suitable for the existing numeric contract. **All three remain
unqualified and formal output is zero.** No exact independent boundary label,
±0.1-second accuracy, full-match recall or whole-match false-positive rate is
claimed. A human Role review of cases 002/003 has been requested and is pending;
that review alone cannot grant full qualification or resolve exposure gaps.

At code `80eeca2`, Linux PR CI passed **4,259 tests**, 7 existing skips and
**87.17% coverage**. Windows PR verification passed dataset validation, pytest
coverage, UTF-8-disabled checks, Ruff, mypy and packaged smoke. Both push
workflows and text-I/O gate passed. Exact run IDs, source/input hashes and
per-case counts are retained in the aggregate JSON. These CI results apply to
that source commit, separately from later documentation-only changes.

The canonical comparison remains unmeasured for this code. Adopted 23/55/4,
archived Strict 28/50/4 and the separate timing-policy comparison are unchanged
historical records. No new PASS or regression assertion ID is claimed, and no
Full E2E was started. The additional evidence demonstrated here is
frozen-reader positive recognition across further source contexts; completing independent
Subject/temporal/attribute qualification is still required before release.

### New persistent-Report negative and Report attribute checks

An additional frozen 103.500–105.000-second native window shows the living
recording player closing the purchase menu after respawn. The previous death's
self-referential Report reappears, without a new killfeed or death transition.
Source frames were reviewed before replay. All **91 frames remain unknown,
with zero death predictions, zero recorder-role readings and zero source-blocked
frames**, despite 85 accepted self-caption frames. Thus Report appearance alone
does not identify a victim or create a new death in this window. This is one
new caption-conditioned negative context, not a full-match false-positive rate
or an independent blind cohort. Wall/recognition time was 229.156/77.574 seconds,
peak Python RSS 93,511,680 bytes; terminal hashes passed. Native acquisition took
267.710 seconds and retained 174,838,427 PNG bytes without copying the video.

The unchanged older `NumericFieldsReader`/Report locator and fatal-row model were
also applied directly to seven pre-reviewed source frames from cases 001–003.
All four visible Report frames, representing **three distinct death episodes**,
supplied the correct observed damage and the fatal-row witness. The three
no-Report controls supplied no accepted fields. Fatal-label NCC was
0.978281–0.981296. All original source, ROI, value confidence, native PTS/pixels,
producer/profile/dependency bindings are retained privately; no expected value
was passed to a runtime reader or used to fit/select references.

The frozen portrait bank supplies zero accepted classes for these unsupported
portraits. Their actual killer-agent attributes remain unknown. Report and
fatal-row candidates stay unqualified; correct digit reading does not establish
Self, a new death or killer semantics. The seven-frame run took 4.822 seconds.
An initial private diagnostic incorrectly tried to build a candidate with empty
fields; the unchanged schema rejected it. That failed attempt is retained.
The corrected diagnostic records missing fields as absent and changes no reader,
schema, threshold or production behavior.

The latest local new-window evidence therefore consists of three reviewed
positive episodes with three diagnostic predictions, one menu/respawn/old-Report
negative with zero predictions, and the bounded Report-field checks above.
Only case 002 supplies numeric victim support under the existing release
contract. The independent Role review request remains pending. Qualification,
enabled real-provider output and canonical improvement remain incomplete.


## Source entrance correction and bounded actual replay

The initial numeric Subject provider unnecessarily required the scene-only
entrance. Existing actual native lifecycle processing also has an explicit
SHA-bound source-assurance entrance. Both the archived Full and an already
reviewed current-code start bundle use that route without a scene component.
The provider now accepts it only through explicit `source_assured` mode,
reusing the original input-contract loader and source-row validator. The scene
mode stays default; source assurance never grants Self identity, role evidence,
reader confidence, Death qualification or player-owned HUD state. No threshold,
global policy, Qualification Pack, Schema or default application changed.
Details and source fingerprints are in
[numeric_self_death_subject_provider.md](numeric_self_death_subject_provider.md).

Actual current-code source replay admitted **96/96 native rows** in two exposed
death windows and two persistent-Report/spectator windows, in **144.259 s**, with
peak Python RSS **98,381,824 bytes**. All primary states stayed unknown, accepted
timers were zero, owned-state promotions were zero and formal Death Events were
zero. No new Subject certificate was generated, the old Full qualification was
not re-signed, and terminal source/PNG/pixel/code/profile/review hashes passed.
This is evidence about the native source entrance, not a real qualified
Subject-provider or canonical run. The provider's 55 unit cases pass with
explicit synthetic qualification; those positive Events are not real accuracy
measurements.

The broad image-runtime fingerprint includes HUD/global modules. That binding
requires review after code changes, but does not by itself prove that native
killfeed marker or separator parameters were fitted on past geometry images.
The Subject reader reads native pixels and its own frozen ROIs/assets directly;
it does not call HUD geometry or infer Self from a global timer/score. Therefore
historical geometry exposure must be assessed per component. It must neither
be called blind holdout nor treated as automatic proof that all independent
Subject validation is impossible. The existing caption-conditioned prospective
case selection, original fitting frames and unresolved component-specific
review limitations remain disclosed. No independent qualification is granted
by this clarification.

**Current verdict remains B.** Self/role/episode and semantic-attribute
qualification, a genuine qualified-provider positive, and same-contract targeted
canonical improvement remain incomplete. New canonical PASS/FAIL/NE and deltas
remain unmeasured; adopted 23/55/4 and archived Strict 28/50/4 are historical,
separate records. Full E2E was not launched.


## Actual own-name crop defect fixed

A concrete reader defect was found after a private, source-backed weapon-class
reference expansion: padded NCC bounds clipped the headshot search and let that
symbol enter name OCR. The reader now keeps its original numeric role witness
while using a unique contained current-image pictogram for name layout. No
threshold, qualification, identity or ownership policy changed. Details,
intermediate failure and exact source evidence are in
[self_death_name_roi_transport.md](self_death_name_roi_transport.md).

Actual re-recognition covered 544 source-2 and 171 source-1 native frames.
Correct own-victim names in the coexisting killer/victim case increased **0→74**
from that victim's own row. Another source episode gained **0→74 numeric victim
readings** with the private development reference; the crop fix restored its
54 correct names and removed the intermediate symbol-prefix errors. Source-1
fixed output counts and onset/confirmation values are unchanged, and the living
Report-reappearance negative still has zero predictions. Formal Events remain
zero. The new development profile is not installed or independently qualified.

Related tests: **345 passed**, Ruff and mypy (148 files) passed, text-I/O audit
has zero unclassified calls. The preceding source-entrance commit `4e1fbe3`
passed all five Linux/Windows/text-I/O CI runs including packaged smoke; new
reader CI is separate. Real qualified-provider/canonical runs remain pending,
so verdict stays B and this is not canonical FAIL reduction or Goal completion.

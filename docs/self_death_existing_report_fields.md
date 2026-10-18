# Self Death: reuse existing Report readers before adding recognition

Status: **source-backed unqualified field availability verified; formal semantic
association and independent qualification remain incomplete**. Source/test code
is unchanged from `6eafb85d2e12de0a74136996cb7707953e36222a`. Fetched main remains
`7e480c2f2f7f49aea73e1541d065d78881d2f11c`; this investigation started at
documentation head `4ea70efe00efeb1ed129c93056dda5aec900af61`.

## Existing implementation, not another reader

The unchanged `NumericFieldsReader.read_candidates()` already supports
independently accepted damage displays and candidate Report portrait classes.
`ReportFieldLocator` measures the current static-header translation; no previous
frame's placement is retained. The historical diagnostic profile includes frozen
damage bounds, two portrait classes, NCC/value gates >=0.90 and a calibrated
header model. None was refitted here.

The HUD producer records these results as `combat_report_readings` with
`status=candidate`, source PTS/pixel hash/profile and per-field support. That
status explicitly does not establish player ownership or a Death event. The
current scoped release consumer deliberately omits guessed `victim_name`,
`killer_agent` and `combat_report_damage_received`. An empty formal attribute
must therefore not automatically be classified as an unimplemented reader.

## Frozen source-backed measurement

The existing profile was run directly on 13 original native cached frames:
distinct known episode onsets/confirmations, frozen context-window first frames,
and the first source-1 R2 frame at which the already frozen killfeed reader
accepted a victim name. PTS/pixels selected that last frame from existing actual
outputs; no expected name/value or GT selected or corrected a reading.

The cache's original verified extraction manifests and encoded/pixel hashes
identify the historical source bytes. No video was decoded or rehashed in this
frame-only experiment. Exact current reader source, profile/assets, engine,
trained language, shared libraries and runtime environment are recorded. The
final v2 dependency binding includes actual file hashes, not just version/path
metadata. Its 29 dependency-file hashes were verified again at completion.
The earlier v1 record is retained and was not re-signed.

No ROI, reference, preprocessing, OCR acceptance, NCC, source ownership or
production default was changed. The old runtime/model was reused explicitly;
its fingerprint must not be conflated with the separate image recognizer's
dependency fingerprint. Joining evidence requires the same physical source
PTS/pixels and preservation of each component's own provenance.

| Source-1 location | Damage candidate confidence | Portrait candidate confidence |
| --- | ---: | ---: |
| R1 original onset | 0.966946 | 0.981218 |
| R1 image-model confirmation | 0.966506 | 0.974591 |
| R2 original onset | 0.958963 | 0.979226 |
| R2 image-model confirmation | 0.962158 | 0.984021 |
| R2 first accepted victim-name frame | 0.960960 | 0.987338 |

These are actual observations, not independent accuracy estimates. Values and
class labels remain in the private result. All five rows supply both fields.
Confidence remains capped by the independent current header placement. For
example, the R2 confirmation's portrait template score is 0.995882 but retained
field confidence is 0.984021; that cap was not removed.

The complete 13-frame experiment retained seven damage candidates and six
portrait candidates, including persistent-Report observations. It took 8.408
seconds. No candidate was turned into an owned observation, killer identity,
Event, Fact or canonical PASS.

## Victim name is frame-specific, not absent throughout R2

The R2 image-model confirmation frame has no accepted victim-name string.
However, the existing native replay contains 32 accepted name readings in that
episode, all with one identical string hash and confidence 0.902336–0.925233.
The first occurs 0.05 seconds after the original Report onset, before the
image-model confirmation. At that **same physical frame**, the unchanged Report
reader also accepts the damage and portrait candidates shown above.

This disproves the stronger claim that the source or reader cannot supply R2's
victim name. It does not justify filling the confirmation frame's missing value,
inheriting another frame's confidence or treating the name as qualified Self.
A future qualified episode association must retain the original field PTS,
pixel hash, ROI, confidence and component provenance; prove current owner/role
at the field's own source frame; reject conflicting accepted names, stale rows,
different episodes and source breaks; and never use GT to resolve a conflict.

## Negative and unsupported contexts

The persistent Report before a later round still supplies accepted damage and
portrait candidates. A second cold post-death Report also supplies a damage
candidate. Neither is a new death. This is direct evidence that field presence
must not bypass fresh-transition and subject qualification.

The later source-2 ability death has valid static-header placement, but its
damage and portrait remain absent under this unchanged older profile. A
delegating diagnostic recorded the actual underlying returns on all three
confirmation frames without changing acceptance:

- Source-2 damage support is 0.706965 and is rejected by the configured numeric
  reader gate; it is not a transport loss.
- Its portrait score is 0.162620 and is rejected as below threshold. The frozen
  two-class bank does not establish this different portrait class.
- Source-1 confirmations retain their actual accepted OCR/template results.

Four no-Report context frames yield no fields. These are exposed regression
checks, not independent semantic qualification or a general false-positive rate.
The unsupported source-2 case was not repaired by new references or lower gates.

## Remaining work and canonical effect

For source-1 R1/R2, new damage/portrait OCR is not the first missing implementation.
The missing step is independently qualified semantic association with the Self
Death episode: a portrait class must not become `killer_agent` merely because
it is visible, and damage must belong to the relevant subject/report row. A
Report's persistent or reopened contents are not a fresh life transition.
The current formal consumer does not implement that association or emit these
attributes. Public schema, confidence and identity contracts were not changed.

The two point-event assertions therefore remain unproved even though candidate
field observations are available. The two event-count assertions still need
independently qualified actual release and correct native Round association.
No assertion was evaluated with fabricated events or semantic attributes.
Canonical targeted/sampled/Full values are not remeasured; historical baselines
remain distinct. No new production logic, formal output, PASS gain, main merge
or goal completion is claimed by this investigation.

The next independent source review must cover both detection and semantic-role
association. Supplemental-original contents, file size and storage location
have been requested before choosing at most one transfer. Existing development
images cannot be renamed a new blind holdout; previous auxiliary Round-work
exposure must also be disclosed.

Private reproduction records: `s01_reuse_report_field_probe_v2.py`,
`reused-report-fields-v2-plan.json`, `reused-report-fields-v2-result.json`,
`s01_report_rejection_detail.py` and `reused-report-rejection-detail-*.json`.
The exact reader source retains its prior 231-test local suite and successful
Linux/Windows CI at `6eafb85`; no new behavior was introduced that warrants
another multi-hour recognition run or repeating those tests for this document.

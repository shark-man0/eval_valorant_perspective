# Fatal Report row evidence

Status: experimental current-image reader and episode transport implemented;
independent qualification and formal Death attributes remain incomplete.
Started at `ecff680eade407b78488443873e23223564fc079`; fetched main remains
`7e480c2f2f7f49aea73e1541d065d78881d2f11c`.

## Actual missing meaning

The existing Report reader can read a damage number and a portrait class, but
neither alone establishes that the selected damage slot describes the fatal
interaction. The current-frame Report has a static Japanese fatal-row label
below the received-damage display. The upper self-referential killer card is a
different region. These two regions must not be treated as interchangeable.

Full-frame source review established the label's presence below the values in
the two exposed source-1 death contexts. An additional crop review selected only
the static label, excluding the damage digits, player name and agent portrait.
The label remains visible in persistent Reports, so it is deliberately **not**
used to open a death episode or establish Self ownership.

## Implemented reader

`experimental/report_fatal_row.py` reuses the existing independent Report header
locator and masked NCC matcher. A frozen profile supplies the static label
reference, local search box and the existing received-damage field bounds. The
current header translates both regions; no placement is inherited from another
frame. The label must have a unique match at the unchanged NCC floor of 0.90.

The original Report field producer, physical pixel SHA, crop shape and original
field payload must match. The accepted numeric field must occupy exactly the
calibrated translated slot. The label must be below that slot in the same column.
A marker beside another row cannot lend its support to an unrelated number.
Unknown numbers remain absent even when the static label is recognized.

The output preserves the original numeric producer binding separately from the
fresh label reader binding. The latter fingerprints its executable, matcher,
transport dependency, label pixels, search/calibration, header reference/mask/
regions/threshold and actual image dependencies. Template/header arrays are
copied and frozen. Association support is capped by the actual label, header
and field support. No original field confidence is overwritten or increased.

The experimental image session accepts an optional `report_row_reader` alongside
the existing Report provider. The episode collector attaches a matching row
witness only to the original `damage_received` observation. Source mismatches
reject the join; absent/bad label support leaves the raw candidate unannotated.
Names and portrait classes do not inherit the fatal-row witness. The original
onset, confirmation and source fields are preserved.

This reader emits no Event or Fact. The existing formal consumer still ignores
unqualified field candidates. Its implementation fingerprint now includes this
optional session dependency; prior release certificates cannot silently cover
changed orchestration. Public Event/HUD/Package/SQLite schemas, existing
ownership, confidence floors, GT, sampler and default application path are
unchanged.

## Source-backed measurement

Development used one already exposed source-1 R2 label crop. Its original source
frame, ROI and reference hash were frozen before evaluation. The previously
selected 13 cached frames were reused; all are exposed development/regression,
including the training frame. **These are not independent holdout results.**

The initial label probe found unique >=0.90 matches in nine frames. Four frames
without Report header support did not match through the gated path. Two of the
nine label-positive frames have no accepted numeric/portrait fields under the
unchanged reader; the label did not fill those missing values.

Fresh execution of the implemented row reader associated seven original
accepted damage observations with a fatal-row label. Exact retained label NCC
ranged from 0.965969 to 1.0. Seven accepted observations include persistent Report
contexts and the development reference; they are not seven independent deaths.
The numeric/portrait outputs were hash-verified and retain their earlier producer
fingerprints. Only the new label measurement is freshly recognized here.

| Episode/context measurement | Previous | Current | Delta |
| --- | ---: | ---: | ---: |
| R1 long window damage observations with fatal-row evidence | 0 | 1 | +1 |
| R2 damage observations with fatal-row evidence | 0 | 2 | +2 |
| Source-1 persistent Report control episodes | 0 | 0 | 0 |
| Source-1 spectator control episodes | 0 | 0 | 0 |
| Formal real-source Death events | 0 | 0 | 0 |

The short R1 window does not borrow another acquisition epoch's Report fields.
The fresh row measurements were transported through the original 171-frame
source-1 image replay. Existing names/portrait candidates are not renamed as
qualified Self or killer attributes.

Final fresh 13-frame measurement plus archived episode transport took 3.176
seconds and saved 168,356 bytes. Original input, executable, profile/assets,
dependency and pixel bindings were checked; terminal input hashes passed. No
additional video transfer or Full E2E was performed.

Private reproduction records are `report-fatal-row-development-plan.json`,
`report-fatal-row-development-result.json`,
`report-fatal-row-reader-v3-plan.json`,
`report-fatal-row-reader-v3-result.json`, and
`s01_report_fatal_row_reader_replay_v3.py`. Reference pixels, names, values and
raw images stay private. The reference is not installed into an application
profile or published as a qualified asset.

## Tests and limits

171 related tests passed in 42.92 seconds. Ruff passed (`src tests scripts/e2e`
and the episode replay diagnostic). Mypy passed for 147 checked source/diagnostic
files. Tests exercise independent header/label loss, wrong numeric slot,
source/profile mismatch, current header translation, duplicate label ambiguity,
persistent Report, value-invariance, confidence caps, immutable assets, invalid
calibration and invalid label support, plus the existing image session, numeric
release and episode-field regression suites. Synthetic tests do not prove real
recognizer qualification. Linux/Windows CI for the preceding `ecff680` remained
in progress at the last check; this new source has not yet completed remote CI.

The text-I/O gate at `f28a540` rejected two implicit `encode()` calls in
fingerprint construction. They now explicitly use UTF-8 for JSON and ASCII for
the hexadecimal digest. The local mandatory audit reports zero unknown I/O
contracts; 28 focused row-reader/encoding tests passed in 10.67 seconds, with
Ruff/mypy still passing. The actual pixels were remeasured under the resulting
new code fingerprint (v3 above), retaining seven row associations and three
episode annotations. No old observation was re-signed.

Adopted Full remains 23/55/4; archived unadopted Strict remains 28/50/4; the
different timing-policy comparison remains 30/49/3. New canonical results and
PASS/FAIL deltas are unmeasured. No precision gain is claimed from the annotation.

Next: qualify the fatal-row meaning, value accuracy, self-referential killer-card
role and subject/temporal producer independently, then pass qualified attributes
through the existing formal Event contract. A source-2 unsupported value/class
must remain unknown. The current small exposed set does not establish an
independent false-positive rate for nonfatal Report rows, other report layouts
or all portrait classes. Additional video transfer is not a prerequisite for
continuing implementation with the sources already available.

# Text I/O encoding audit (#28)

Start main commit: c11ec6d333957cccb270417bc95a8a57f433e6ad (2026-10-13).
The historical estimate of roughly 220 missing encodings is NOT a current measurement.

Run the deterministic static inventory:

    python scripts/audit_text_io.py --summary-json
    python scripts/audit_text_io.py --json

It scans Python sources under src/, scripts/, tests/, config/ and ValorantData/.
The two standard Linux/Windows CI workflows print the fresh site counts.
JSON/CSV text file calls are counted through open/read_text/write_text.

| Class | Review contract |
| --- | --- |
| UTF-8明示 | Explicit UTF-8 or intentional utf-8-sig BOM support. |
| その他の明示的encoding | Preserve format-specific non-UTF8 encoding. |
| Binary I/O | Preserve bytes, modes, and file checksums. |
| OS依存が仕様 | Manually document any intentional host-locale protocol. |
| 要調査 | Determine producer, protocol, BOM and newline before changing. |

Classification is conservative, not a change recommendation: subprocess
output and bare encode/decode are not indiscriminately changed. Python
bytes.decode()/str.encode() default to UTF-8 even on Windows; binary ffmpeg
output must not be converted into textual data. Existing PowerShell UTF8
parameters and deliberate BOM/CRLF behavior are retained.

## Measured inventory (current main baseline + PR #39)

From Linux Basic CI run 38392798509 on the PR snapshot (2026-10-13):

| Metric | Count |
| --- | ---: |
| Python files scanned | 552 |
| Python I/O call sites inventoried | 1,532 |
| Binary I/O | 662 |
| Explicit UTF-8 / UTF-8-SIG | 420 |
| Other explicit encoding | 10 |
| Needs manual producer/contract review | 440 |

These **1,532 sites are not 1,532 encoding omissions**. The 440 candidate
sites include subprocess and encode/decode calls, and are not confirmed
UTF-8 requirements. Seven application-owned Visual JSON reads and one E2E
JSON write were corrected; the thermal sysfs read deliberately uses ASCII.
Actual classification totals may shift as independently developed code is
merged. Review the `--json` output before assigning an individual site.

The scan itself previously failed when the Windows console used cp1252;
its JSON CLI output now uses ASCII escapes for non-ASCII labels so audit
reports can be written to a locale-limited stdout without losing information.
The synthetic BOM test continues to check the exact same UTF-8 bytes.

## Verified minimal correction

The E2E runner emits application-owned error_code.json as a JSON document.
The one missing file encoding is now explicit UTF-8. No source provenance,
artifact content, error code, round identity or evaluation logic was changed.

New tests demonstrate cp1252 incompatibility with Japanese JSON, explicit
UTF-8 round-trips, a Japanese filename with legal Windows punctuation,
unaltered BOM/CRLF bytes and audit categorization. Previous Windows fixes
are not reimplemented.

## Limitations / follow-ups

The scanner is observational and cannot certify which unknown sites ought
to use UTF-8; their data-contract-specific remediation remains OPEN.
This PR should not be described as resolving all UTF-8 ambiguities.
Existing test skips are unchanged; complete Windows packaged smoke runs in CI.

## Additional confirmed production I/O fixes

Six Visual code files now use explicit UTF-8 for seven application-owned
JSON policy/configuration reads, preserving the same parsed JSON data and
recognition/aggregation behavior. The Linux sysfs thermal sensor decimal
text is explicitly ASCII. Git/FFmpeg/Tesseract child output retains its
producer-dependent decoding contract pending separate review.

## Additional manually checked diagnostic JSON outputs (2026-10-14)

Eight application-generated diagnostic JSON writes in `scripts/diagnostics/`
are now explicitly UTF-8: source review plan, assured-start evidence,
client graph history, descriptor competitors, descriptor photometry,
native adjacent regions, native PNG storage and native seed failure.
This does not change JSON fields, source-provenance logic or the prior
newline/BOM contract. A regression test enumerates these writers and checks
explicit UTF-8 with the AST inventory. This is an independently confirmed
subset of the unresolved-site list, not a claim that all 441 candidates
require changes or have been manually classified.

The source package's 131 Python files were also spot-audited for direct
Path.read_text/write_text/open calls; all observed output writers use
explicit UTF-8, and observed `rb`/`xb` paths are intentionally binary.
This limited pass does not cover every AST call category in that package.

## Continued source-contract triage (2026-10-14)

The independent latest-head Linux CI #38495100212 (commit `327e685`) printed
all **363** unresolved AST candidates, down from the prior **441** snapshot.
The full `--review-json` report records the concrete path, line, operation and
expression for every candidate. This count is **pre-this-commit**:

| Scope | Unresolved AST candidates |
| --- | ---: |
| tests/ | 288 |
| scripts/ | 41 |
| src/ | 23 |
| ValorantData/ | 11 |
| **Total** | **363** |

By operation: 167 `write_text`, 111 `read_text`, 49 `encode`,
33 `subprocess`, 2 `decode`, 1 `open`. Python's default
`str.encode()`/`bytes.decode()` is UTF-8 rather than the host locale;
those call sites are therefore not evidence of Windows text file failures.
The subprocess cases require individual producer/protocol contracts.
The test-site majority mostly concerns synthetic fixture text and must not
be conflated with application-owned production I/O.

On inspecting the remaining diagnostic and frame-suite writers individually,
**16 additional application-generated JSON file writes in ten source files**
were confirmed to need explicit UTF-8; they are now fixed without changing
JSON structure, provenance, hash checks, error handling, newline arguments or
recognition/GT decisions. Static regression tests cover all ten file paths.
The post-change count must be measured on CI; the current PR is still an
incremental remediation rather than closure of all Issue #28 contracts.

## FFprobe JSON subprocess contract (2026-10-14)

Eight additional FFprobe subprocess calls (seven source files in `src/`,
`scripts/diagnostics/` and `scripts/e2e/`) explicitly decode text as
UTF-8. These calls request `-of json`, a UTF-8 JSON data protocol; their
Python `text=True` calls previously selected the Windows host code page.
Binary FFmpeg frame pipes, command stderr redirected to log files, and
locale-dependent human-readable Git/OS utilities remain unchanged. A synthetic
subprocess test verifies that Japanese UTF-8 output cannot be decoded as
cp1252 while explicitly UTF-8 text capture round-trips unchanged. The
additional change only controls text decoding; native source video identities,
metadata assertions, timing, frame extraction and GT remain identical.

The prior 363-site inventory was taken before both the 16 JSON-writer edits
and this eight-probe contract fix; CI must provide the new count.

## Reviewed synthetic fixture test text I/O (2026-10-14)

Eight selected test modules were reviewed site-by-site: fixture validation,
finalization, provenance tamper guards, approved boundary ledgers,
HUD auto-profile configuration, boundary review assembly, scene-source bindings,
and temporal calibration. The **17 read_text + 57 write_text** sites use
application-generated JSON, generated HTML, or ASCII synthetic Python test
recipes; each now explicitly specifies UTF-8. Only test text boundary
parameters change, not assertions, synthetic input payloads, frozen ground
truth, or comparison rules. An AST regression test guards these sites.
Other test candidates require separate contract review, and the latest CI
inventory remains authoritative for post-change totals.

## Reviewed integration/report readers (2026-10-14 continuation)

After the 265-site Windows inventory (commit `783d931`), 15 test modules
were reviewed for reads of application-owned JSON, HTML and E2E schema
files. Exactly **49 `read_text()` calls** now explicitly use UTF-8 in
commits `c872486` and its successor. The synthetic inputs and assertions
are unchanged; no ground truth, hashes or evaluation-policy semantics were
modified. Long call sites are wrapped without altering file content.
Two AST regression checks enumerate all 15 modules and assert that every
`read_text` has `encoding="utf-8"`. A fresh CI inventory is needed for
post-change counts; the Linux Qt destructor abort is tracked under #18
rather than being hidden or treated as an encoding regression.

## Site-specific classification for remaining default-codec/locale calls

Starting from the measured 265 AST candidates on `783d931`, 49
integration/report JSON readers, 139 additional fixture/validation-pack
text file boundaries, 16 machine-protocol subprocess decoders, and one
child-process binary log file have been fixed in subsequent commits.
The remaining **60** sites comprise 49 default `str.encode()` calls,
2 default `bytes.decode()` calls and 9 intentionally host-locale subprocess
human-diagnostic calls. Python's built-in encode/decode defaults are UTF-8
on all operating systems; unnecessary `encode("utf-8")` can trigger
Ruff UP012. External FFmpeg/Tesseract/version diagnostics and Python child
messages may use their producer's locale and should not be forcibly decoded
as UTF-8. None of these 60 calls requires a runtime change to satisfy the
present producer contracts.

The 60 sites map to 57 unique file/operation/AST-expression decisions in
`scripts/text_io_reviewed_contracts.json` (three reviewed expressions
occur in two locations each). Decisions carry the producer rationale and
apply only to **exact matching** source expressions, so additions or edits
become `要調査` again. A regression test checks ledger coverage, stale
entries, and the repository-wide absence of unresolved candidates. A
reported count of 0 will mean **all observed static candidates have a
reasoned classification**, not proof of universal locale compatibility.
The Windows `PYTHONUTF8=0` test and Windows packaged smoke, Linux pytest
process exit, plus #18 Qt teardown still require independent acceptance.

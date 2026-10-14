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

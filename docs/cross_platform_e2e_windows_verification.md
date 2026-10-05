# Windows migration verification / Pi handoff

Decision: **WINDOWS PARITY CONFIRMED; PI UNVERIFIED**.
Analyzer feature development stops here until the first Pi result is reviewed.

Migration starting HEAD: `530c47d9303a8a06ceb0d17f24588ad0b4d468fa`.
Clean E2E source commit: `ba8135a3563e5c451b3a2d2685b5f6cbf6036a7d`.
Compared clean baseline: `5b7a7e26c670cfc999839dcecd42c77065d19a24`.
Both runs have `git_is_dirty=false`, identical source SHA, pack and settings fingerprint.
No src/config difference exists between the baseline and migration source.

| Measured result | Before | After |
|---|---:|---:|
| E2E passed / failed / not evaluated | 22 / 56 / 4 | 22 / 56 / 4 |
| Negative passed / failed | 20 / 0 | 20 / 0 |
| HUD observations | 4,038 | 4,038 |
| Live / Spectator / Buy / UNKNOWN | 165 / 335 / 1 / 3,537 | 165 / 335 / 1 / 3,537 |
| Published HP facts | 130 | 130 |
| Published Timer facts | 1,470 | 1,470 |

Native stream/PTS/ordinal pairing finds **4,038 unchanged**, zero added/removed
observations, zero confidence/evidence/ownership/world changes and zero reader
gains/losses/value changes. HP/Timer semantic facts and round window bounds match.
Evaluator JSON objects match exactly. Shared summary JSON content matches exactly
after excluding run metadata; textual ordering differences do not change values.
FFmpeg/ffprobe version logs and Validation Pack validation logs have identical SHA.

PowerShell returns exit **1**, correctly preserving the existing assertion FAIL;
this is not a tool/runtime failure. The source suite is **966 passed / 3 skipped**,
Ruff passes src/tests/scripts, mypy passes 86 src files, and diff checks pass.
Both common Python and PowerShell environment smoke checks exit 0.
POSIX syntax, Unicode argument and 0/1/2 stub checks pass on Git Bash. Git Bash
does not establish Linux or Raspberry Pi runtime compatibility.

Remaining Pi work: install/import pinned ARM64 dependencies, verify native system
libraries and Python 3.12, copy the unchanged raw source/pack/private assets, rebase
the four absolute Windows image references (25 total), verify decode/fixed-frame
hashes and detector/fact parity, and measure memory/runtime. Source E2E does not
initialize Qt; PySide6 remains the optional desktop `gui` dependency.

After setup, first run `./run_e2e_pi.sh --check-environment`, then use the same
private inputs/profile with `./run_e2e_pi.sh --video-id match_001` from a clean tree.
Do not reduce sampling or weaken thresholds to obtain a Pi result.

Aggregate evidence: `cross_platform_e2e_windows_parity_v1.json`.
Setup: `../RASPBERRY_PI_E2E.md`; architecture audit: `cross_platform_e2e_migration.md`.
Raw/crops/per-frame rows/profile assets remain private and are not part of this report.

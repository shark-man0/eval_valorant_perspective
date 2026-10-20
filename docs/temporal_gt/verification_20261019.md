# Verification of the offline temporal data contract

Starting main: `ba90c0ba05185642265d269979d7a0cb25c9e517`. Independent branch: `codex/round-end-temporal-data-contract`. Production `src/` is unchanged, including the source decoder, confidence policy and recognizer fingerprint.

Local checks on macOS / Python 3.12.15 / OpenCV 4.14.0:

- Existing dataset validation: **38 cases valid**.
- New synthetic contract checks: **38 passed**. Cases include source/event/split aliases, prior training/view/prediction exposure, sealed reserve and reuse, noninteger PTS, timebase/epoch/bracket errors, unknown-negative and partial-complete confusion, missing provenance, policy/freeze tampering, evidence corruption and duplicate rasters across splits. A valid PNG with altered pixels is rejected through shared `NativeSourceFrame` verification.
- Related source/preflight/dataset/contract suite: **116 passed**.
- Ruff: passed for `src`, `tests`, `scripts/e2e`, `scripts/temporal_gt`.
- mypy: passed for **133 production modules** and **2 new offline modules**.
- Text-I/O audit with required classification: passed, **564 files / 1,605 sites**; no new unclassified encoding sites.
- Whole repository test suite: **3,784 passed / 4 failed / 9 skipped**, coverage **87%** (required floor 75%). The four failures concern existing spectator-icon rendering assertions. Running their two test modules from a clean archive of the starting main in the same environment reproduces exactly **4 failed / 46 passed**. Both affected tests and all production source files have no diff against that main. No recognizer fix or test suppression is included in this data-contract task.

Current-branch Linux and Windows CI results must be checked on the submitted PR; the previous main's successful CI is not substituted for this branch. Existing CI tests, dataset fixtures, Windows UTF-8-disabled checks, PyInstaller build and packaged smoke remain enabled. The new offline modules are added to Ruff/mypy coverage. Public tests use synthetic data and never load real GT or source.

Actual private source preflight completed successfully with recognition and qualification disabled. Original source/contract SHA bindings and all 130,039 frame timestamps were verified. Two bounded same-epoch native acquisitions retained 121 and 181 source frames within their declared 256 MiB budgets. This is integrity evidence, not proof of independent label truth or full temporal continuity. The frozen private dataset's anonymous summary remains BLOCKED.

The code commit `b515771` passed Linux CI ([run 39223988058](https://github.com/shark-man0/eval_valorant_perspective/actions/runs/39223988058)) and the text-I/O review gate. Its Windows run stopped before dependency installation/tests because the existing Chocolatey FFmpeg feed returned HTTP 503/504 on all three attempts ([run 39223988030](https://github.com/shark-man0/eval_valorant_perspective/actions/runs/39223988030)); one failed-job rerun was requested. This is not a Windows test/package PASS. Later documentation-only snapshot amendments require their own current-head check status.

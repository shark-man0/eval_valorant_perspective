# Development timeline in the desktop app

The existing desktop app provides these development-only menu actions:

- **開発用: 共通タイムライン** selects an exported application
  `timeline_PRIVATE.json`, then the matching registered Source policy JSON.
- **開発用: 試合横断比較** selects a locally generated comparison manifest JSON.
- **開発用: Map解析一覧** selects a private Map library directory and then a recording.
  Set `VALORANT_MAP_LIBRARY` to skip the directory picker. It opens the registered
  original video, the common timeline, the standard and recovered Map views,
  and the matching evaluation. The application checks package digests before
  opening the viewer.
- **開発用: Map解析を実行** registers a distinct recording as DEVELOPMENT,
  runs Map analysis, shows progress, and saves a local versioned result. It can
  create a private recording catalog or use an existing one.

The selected input is validated by the corresponding localhost viewer factory
before a browser opens. The viewer serves only on `127.0.0.1`, uses its tokenized
URL, and stops when the desktop window closes or another development viewer is
opened. Keep the desktop app open while reviewing the original recording.

Generate the single-match application bundle as described in
[`development_timeline_application.md`](development_timeline_application.md).
The comparison manifest is produced by the development comparison workflow;
it is a local private artifact. The Map analysis dialog performs acquisition
and all four actions keep candidates outside formal Fact, Event and coaching scores. The original recording and policy must remain available for
video seek and source verification.

The GUI is an entry point to the existing local viewers. Timeline calculations
and uncertainty handling remain in the shared development engine and its
application/comparison projections. The Map library accepts only catalog-admitted
DEVELOPMENT recordings and its evaluations run with formal promotion disabled.
See the [Map workflow](../scripts/map_learning/README.md) for registration,
import, resuming and publishing packages to this menu.


## Run Map analysis from the desktop

Prepare a Python 3.12 environment with the application dependencies and PyTorch
if the selected setup uses learned models. Install FFmpeg and FFprobe on the
system path. Select that Python executable and the private Map setup JSON in the
dialog. The Windows package includes the analysis worker source. Model weights,
reference assets and setup paths remain in the operator's local data directory.

Select a recording, a private recording catalog, a working directory and a result
library. Confirm that a new recording represents a distinct physical match.
Select **登録して解析**. The dialog shows the current stage and reports measured
frame counts where available. **中断** stops at a safe checkpoint. **前回の解析を再開**
uses the saved recording and setup, retains completed checkpoints and reacquires
any incomplete native decode. A newer setup should start a separate run.

Different model and recognition options produce separate immutable results.
Use the same recording and timeline inputs for both configurations, point the
new setup to the model receipt directory, then launch it from the same dialog.
Select a baseline and a candidate to compare selected one-second rows and measured
trajectory links. Standard results and missing-observation recovery each have
their own comparison. Select either version to open the registered original video,
Map candidates, trajectory, Named Zones and its development evaluation.

Updates to Named Zones may be applied without decoding video. The published
callout atlas supplies landmark anchors. The development generator retains small
interiors where the reference geometry supports them and preserves any existing
Zone. These areas cover only part of each callout.


## Compare a multi-marker replay

Select the original result in the Map dialog, then use **追跡結果を取り込む** to
attach a multi-marker report. The app checks the original timeline and incumbent
hashes, the source and native frame lineage, and retention of the original
observed points and edges. The original library entry remains available.
The attached entry has a third viewer mode. Compare it with the original
entry to see added or lost positions and measured links for each mode.
The development evaluation panel continues to describe the recovery result.

`scripts/map_learning/import_marker_tracks.py --portfolio <private JSON>
--library <private directory>` can attach a portfolio in one pass. If the exact
incumbent is missing, import its original standard/recovery pair first.
`run_marker_tracks.py --help` prepares a plan using the frozen native manifest.
It verifies retained frames and existing pixel overrides before considering
restoration. Use `--whole-episode` for the complete evidenced self-view episodes
that contain a target, `--exclude-covered` to skip previously covered targets,
and `--replay-script` to run the externally supplied tracker. Restoration is
optional and keeps the disk reserve. The launcher reuses sealed results bound
to the exact input, coverage, assets, and tracker source.

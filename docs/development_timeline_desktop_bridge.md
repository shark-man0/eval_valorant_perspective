# Development timeline in the desktop app

The existing desktop app has two development-only menu actions:

- **開発用: 共通タイムライン** selects an exported application
  `timeline_PRIVATE.json`, then the matching registered Source policy JSON.
- **開発用: 試合横断比較** selects a locally generated comparison manifest JSON.

The selected input is validated by the corresponding localhost viewer factory
before a browser opens. The viewer serves only on `127.0.0.1`, uses its tokenized
URL, and stops when the desktop window closes or another development viewer is
opened. Keep the desktop app open while reviewing the original recording.

Generate the single-match application bundle as described in
[`development_timeline_application.md`](development_timeline_application.md).
The comparison manifest is produced by the development comparison workflow;
it is a local private artifact. Neither menu action performs acquisition, changes
the recognizer configuration, or moves candidates into formal Fact/Event or
coaching scores. The original recording and policy must remain available for
video seek and source verification.

The GUI is an entry point to the existing local viewers. Timeline calculations
and uncertainty handling remain in the shared development engine and its
application/comparison projections. These actions are not Production analysis
controls.

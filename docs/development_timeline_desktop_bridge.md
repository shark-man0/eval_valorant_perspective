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
application/comparison projections. The Map library accepts only catalog-admitted
DEVELOPMENT recordings and its evaluations run with formal promotion disabled.
See the [Map workflow](../scripts/map_learning/README.md) for registration,
import, resuming and publishing packages to this menu.

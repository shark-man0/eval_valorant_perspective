# Draft timeline integration audit

Audit basis: `origin/main` at `ef4eec3`, Draft #115–#133 latest heads through
`b514b88` (#133), inspected on 2026-11-06. #121 and #124 are tracking Issues,
not pull requests. No merge into main is recommended at this stage.

## Dependency and interface

The seventeen Drafts form one linear stack:

`#115 → #116 → #117 → #118 → #119 → #120 → #122 → #123 → #125 → #126 → #127 → #128 → #129 → #130 → #131 → #132 → #133`.

Each PR base SHA matches the preceding PR head SHA. #115 starts from the
fetched main SHA. The latest branch contains the whole stack. Applying an upper
branch independently or merging PRs out of order would include, or conflict
with, its parent changes. A local merge-tree of `origin/main` and #133's head
is clean as of this audit; that checks textual integration, not semantic
qualification or a future main state.

`DevelopmentGameTimeline` in `temporal/game.py` is the single development
Round/life/camera state owner. Native suppliers, Map projection, HUD values,
visibility and one-second application export feed or read that state. The
Production `DeterministicRuleEngine` remains separate. The application and
comparison viewers consume saved development results; they do not create a
second state machine. Later Drafts use opt-in configuration and retain
provenance, candidate channels and UNKNOWN. The evolving `game.py` and
`application.py` APIs are the highest-risk integration points and need one
combined regression run after any rebase or selective merge.

The stack adds many focused tests for individual gates and transport. Full-suite
results from a parent SHA do not qualify a later SHA. The already existing
`evaluation_package` carries development rows and event candidates while
formal Facts, Events and state snapshots stay empty. `review_timeline` creates
a candidate queue and verifies that the formal engine issues no decision.
This supports review and coverage inspection, not coaching scores or Production
recognition accuracy.

## Current separation and open risks

- #127's provisional Map recorder hypotheses are a separate research channel.
  Strict current-self correspondence still abstains on four reviewed controls;
  do not substitute provisional hypotheses for owner facts or paths.
- #128's active-clock bridge revises UNKNOWN Round candidates with an opt-in
  offline rule. UNKNOWN reduction and candidate counts are not measured
  accuracy. #130's wider acquisition changed previously known state values on
  exposed recordings and remains an unadopted configuration comparison.
- #131's purchase-menu and Tracker signals describe visible overlays only.
  #133's inventory label is not the selected weapon. Neither channel conveys
  recorder ownership or life state.
- The shared development code adds about 17.9k lines across 97 files relative
  to main. This is a broad review and rollback surface. Preserve each original
  Draft and its private research evidence while preparing a small, reviewed
  integration sequence.
- No new Production or GT/split/fixed-window changes were found in the
  main-to-#133 name diff. This does not by itself prove that every candidate
  is semantically correct or qualified on independent data.

## CI and recommended integration order

Own-head GitHub checks were inspected once per distinct PR SHA. Windows
`test-and-build` includes tests, static checks, PyInstaller and packaged
application smoke. All seventeen Windows checks succeeded. Linux succeeded
on sixteen heads; #122's `3ec8bfa` failed at mypy after tests and Ruff passed.
#123 and every later head have successful Linux checks. Text I/O checks also
succeeded where present; #132 has no Text I/O check shown on its latest head.
These results are historical exact-head checks, not checks for a future
combined merge commit.

Keep the stack as Drafts while the cross-match comparison and domain
experiments are reviewed. First verify the single shared engine and frozen
application/JSON/CSV contracts at the intended integration SHA. Then review
and selectively integrate the minimum timeline, validation, viewer and
evaluation handoff. Keep opt-in clock, Map, HUD and context experiments
isolated until their interface and negative controls are checked together.
Run Linux, Windows, packaged smoke and private replay at the final exact SHA
before any merge decision. Report unmeasured accuracy and unresolved owner
correspondence explicitly; do not promote research candidates to formal
Fact/Event output.

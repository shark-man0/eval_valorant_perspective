# Self Death safety recovery

Start main: `c688206ef4b62c8f206687a1e434fe84833105df`.
Research head: `5ad180a321404333462dc3bdf5d9a322edda1d4c` (Draft #53).

## Recovered defects

* `hud/temporal.py`: legacy report + transition evidence could emit a player
  Death even when the current frame had no qualified player HUD. Recovered the
  caller guard from `4e6e02d86a9e8bb8133292832a838b0e93639cef` (#46).
  The existing `live_first_person` AND literal `player_specific_hud_valid is True`
  contract now applies to Death as it already does to other owned HUD events.
  Unknown, spectator, remote, missing and truthy non-boolean ownership cannot
  bypass it. Buy-phase suppression, round latch and confidence remain unchanged.
* `facts/builder.py`: a producer explicitly limited to `self_death_only` cannot
  establish elimination order. Recovered only the downstream consumer hunk from
  `8f24020f44bf8e73b75f2de2534d031a2533ca98` (#53). `player_died` retains its event
  PTS, confidence and provenance; `first_death_by_player` is not inferred from
  that scoped event. Legacy unscoped inputs retain their existing behavior.

No new producer, schema, qualification authority, decoder or formal event is
introduced. The scope marker restricts inference; it never authorizes an event.
This does not assert that a report is a sufficient independent Self identifier.
A future qualified subject producer can have its own contract; it is not enabled
by this legacy HUD guard.

## Verification

Unit controls cover unknown/spectator/remote/unowned frames, persistent-report
jitter, valid owned positives, duplicate suppression, buy-phase report retention,
scoped and legacy Fact behavior. Integration checks preserve event attributes,
actor, confidence and time through Fact, trace and SQLite, without an experimental
import. Existing HUD wiring and trace membership checks run unchanged.

Repository CI performs the complete fixture/regression suite and coverage,
Ruff/mypy, Windows UTF-8-disabled checks, PyInstaller and packaged smoke. Exact
terminal results are retained on the recovery PR; CI is not image qualification.
No new Full E2E is warranted: this change rejects unsupported legacy ownership
and prevents an inference, and cannot supply the missing qualified Self producer.

Recognition remains B / BLOCKED; formal Self Death 0, confirmed independent
whole-model held-out episodes 0. New-code canonical targeted/sampled/Full remain
unmeasured. Adopted baseline 23/55/4 and historical unadopted 28/50/4 are unchanged
historical results, not measurements of this recovery.

# Selective integration and ownership ledger

Base: fetched main `ef4eec376e83f5bf5345eb2fefbc4e660d4bca4a`.
New branch: `codex/shared-game-timeline-20261029`. No existing branch was rebased,
reset, deleted, merged wholesale or force-pushed. All listed PRs stay Draft.
Main merge, Production adoption and evaluation-specification changes require
supervisor approval.

| PR | Pinned head | Dependencies / selected use |
| --- | --- | --- |
| #107 | c5bdd4f | Based on main; selectively reuse life/camera/revival rules as reference and the exact one-file nested-approx compatibility patch |
| #108 | 7d39717 | Pinned HUD diagnostic supplier for the added bounded Round observation run; no reader replacement or whole merge |
| #109 | 259a051 | Based on #102 (83563a5); adapt only native identity/digest binding; preserve its unadopted center recognizer |
| #110 | 9459e0b | Based on #102; retain cache/history baseline, no whole learner/model/cache import |
| #111 | f94c31a | Based on #109; consumes selected #107/#110; reuse observation-only UI/archive output, not its second owner timeline |
| #112 | c4f1cf5 | Based on #109; selected #107/#110 components; consume frozen Map observation envelopes, not its owner-state definition |
| #113 | 5b1cbbe | Map supplier handoff based on #112; actual external-state consumer is run from a pinned separate checkout |

The HUD supplier handoff on `feat/hud-common-timeline-observations` exports
observation packets; its private export is pinned by content hash in reproduction
evidence. It is not silently imported as another authoritative state machine.
Supplier worktrees and outputs remain intact. The integration uses the locally available observation interfaces.

Runtime additions are confined to the new `temporal/` package. Two explicit
diagnostic supplier-reader CLI adapters accompany the bounded native replay. The one existing
test-file patch is byte-identical to PR107 c5bdd4f and preserves one interval,
4.0/5.0 endpoints and .001 tolerance. Existing default recognizer, Production
consumer, registry, calibration, Profile, canonical GT/fixed windows and
qualification schemas are not edited. Consequently their old fingerprints do
not qualify this new engine: it has separate implementation fingerprints and
all outputs remain development-only.

Semantic overlap occurs in native identity, life/camera carry, death/reentry,
Round transition association and Map ownership gates. These are resolved by
keeping one common inference owner and explicit observation/consumer adapters.
No textual merge conflict is resolved by silently copying a whole stacked PR.
The Draft's final diff and main merge-tree check record actual textual conflict
status. Existing PR mergeability is only the inspected GitHub snapshot, not a
promise that independently modified branches remain conflict-free.

Unrelated workflow/registry/recognizer changes in the stacks are deliberately
excluded. Referencing or replaying a supplier is not Production adoption of its
unqualified recognition. Private Source hashes, images, timestamps, coordinates,
Profiles, labels, model weights and human responses remain outside public Git.

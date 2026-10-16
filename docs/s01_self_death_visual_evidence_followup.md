# S-01 follow-up: observed Self Death role evidence across two real episodes

## What is newly established from the supplied original video

The user supplied the original 171-second `match_001` MP4 directly to the
chat. Its SHA-256 is `71d58558559d6f578433ce9f234bf176f76fd5a86657dbfe3eba1e7d36136b06`,
byte size 267056165, H.264 1920x1080 60fps. The user clarified that it was
extracted by Outplayed from a longer recording, **but contains no edits inside
the extracted interval**. Its clip endpoints cannot establish the match start
or finish; production normally uses uncut full-match videos.

At **about 74.38–74.44 seconds**, the combat-report panel first appears
after frames where it was absent. It includes a localized header meaning
**'enemy who killed you'**. The killfeed presents separate killer/victim
positions; the victim is the source player's name, not the killer. At
**about 147.70–147.80 seconds**, a second independent death episode shows
the same self-referential report semantics and a victim-position killfeed.

These are real-frame **visual-review observations**, not an OCR accuracy
result. A panel can persist after respawn or during spectator mode: the
**104.2 and 150–170-second controls** show this directly. Neither a visible
report nor spectator transition can on its own emit a new `player_death`.

The source-backed observations add important semantic distinctions to PR #47:

- the report header is explicitly **self-referential**, not a generic
  visible report fact;
- the killfeed **victim** and **killer** positions are not interchangeable;
- a new candidate needs an actual **report appearance / death-transition
  edge**, not a panel that remains visible for tens of seconds;
- a source-player name match must be supported by an independently
  qualifying identity/role reader; agreement on previously exposed frames
  is not a blind accuracy test.

## Code and verification

`experimental/self_victim_link.py` is an **offline, non-releasing** linker
between independently source-bound `SOURCE_PLAYER_BINDING` and `VICTIM`
observations from the existing PR #47 model. It requires two distinct
physical frames with matching source context, disjoint ROIs, matching
observed opaque name tokens, an explicit scoreboard-row measurement and
victim-role text, and finite confidence at least 0.90 for both.

The resulting `unqualified_self_victim_candidate` **does not change the
relation field to SELF**. It supplies no qualified identity, no player Alive,
no Death event and no formal Fact. Killer substitutions, mismatched names,
source/segment/code/profile conflicts, stale evidence, overlapping regions,
insufficient confidence and missing tokens are rejected.

The public record is
`e2e_reports/match_001/self_death_visual_role_review_20261016.json`,
containing 17 frame-index/decoded-BGR-hash bindings (no usernames, GT times,
images or private profiles). A source-verification tool is available:

```bash
python scripts/diagnostics/verify_self_death_review.py \
  --video /path/to/Valorant_09-25-2026_0-37-29-379.mp4
```

That verifies original file bytes and the exact decoded frames used for
the visual review, **not the semantic labels**. Because raster fingerprints
depend on decoder behavior, a mismatch is reported rather than accepted
silently. These frames overlap historically exposed windows; they cannot
be rebranded as unseen independent holdout.

## What remains unsolved

Despite the two real positive episodes, formal **Self Death qualification
is still missing**: there is no independently qualified victim-role reader,
source-player/scoreboard binding, temporal edge producer, blind negatives
or autonomous report-header semantic qualification in the production path.
Integration with the existing `SubjectDeathProbe` must remain candidate-only
until independent role and negative evidence is measured. If a future
source-backed positive path qualifies, run targeted and sampled validation
before any full E2E; prove negatives including 104.2 and 170.0 second
persistent-report contexts, and preserve current strict owner/attribution.

**No canonical PASS/FAIL/NE outcome was recalculated or modified.**
Previously reported candidate `28 PASS / 50 FAIL / 4 NE` and evaluator-only
timing proposal `30 PASS / 49 FAIL / 3 NE` remain distinct historical
measurements, not this experiment's results. The user requested practical
accuracy improvements, but an unqualified detector must not manufacture
extra PASS by attributing spectator/death evidence to the source player.

Follow-up priorities: 1) implement and independently qualify the semantic
victim-position + source-owner marker detectors; 2) qualify report onset
under persistent-report and spectator controls; 3) connect only qualifying
candidates to the formal Death event path through reviewed schema/ownership
policies; 4) validate output and failure delta against unchanged fixed GT.

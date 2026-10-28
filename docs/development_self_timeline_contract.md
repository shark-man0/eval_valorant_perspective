# Development-only self life / camera / minimap temporal hypothesis

Status: **research-only, not integrated into Production**. Related: #21, #97, #105.

## Design correction

For the user's unedited, ordinary own-POV VALORANT recording, infer identity **over time**, rather than demanding a complete owner-HUD proof in every single frame. Separate (1) recording owner's life state (`unknown` / `alive` / `dead` / `downed`), (2) camera mode (`self` / `spectator` / `remote` / `unknown`), and (3) which current minimap symbol is independently identified by the self UI. The camera's viewed player does **not** become the recording owner upon spectating. A temporarily hidden owner HUD alone is not a death or identity reset. The application must preserve frame/source continuity and genuinely observed UI transitions, not invent missing proof.

Normal lifecycle for a match: `alive/self` -> observed own death -> `dead` -> spectator UI -> `dead/spectator` -> verified next-round self reentry -> `alive/self`. If death onset was missed, a confirmed spectator UI can generate a **death hypothesis** for this own-POV recording; it is not a qualified death event. A combat report's **continued presence** is not a fresh death. If video continuity is unverified, reset the carried state to `unknown`.

The only within-round **life-state restoration exceptions to model initially** are positively observed revival/return mechanics, not speculative UI persistence:

- Sage's Resurrection: a previously dead player may be revived during the round.
- Clove's Not Dead Yet: self revival after death, potentially followed by a further death.
- KAY/O's NULL/cmd: `downed` is distinct from confirmed terminal death, and a teammate may revive the downed player.
- Phoenix's Run It Back: return to an ultimate anchor is **not in itself proof of a normal death**; keep it as an ability-return transition, not a general-purpose resurrection.

Abilities, modes and patches may change. The observed owner/agent/ability and transition must be verified from video/UI. The presence of a Sage, Clove, KAY/O or Phoenix icon alone is not sufficient evidence that a revival happened. Unhandled mechanics remain hypotheses/UNKNOWN, never fabricated death or revival.

## What is implemented

`src/valorant_ai_coach/visual/development_self_timeline.py` implements a deterministic opt-in **hypothesis** consumer with explicit native Source SHA, epoch, integer PTS and rational timebase. It accepts only externally established transition cues. It carries state across **verified** contiguous frames, resets on source/epoch/PTS discontinuities, recognizes spectator/remote transitions, and accepts revival only from a prior death/downed state. It releases a `self_marker_id` only if an explicit self-UI binding accompanies the marker **and** owner life and camera mode are `alive/self`.

`SelfTimelineHypothesis.qualified` is always `False`. No `Fact`, `Event`, Map zone, owned coordinate, video truth or improved recognition accuracy is produced. Inputs are hypotheses/verified observations provided by a caller; **the module does not itself detect UI pixels, prove a source is unedited, classify death animation or authorize Production**. An observed self HUD after death **without a verified revival/round transition** is conflicting evidence, not automatic resurrection. `round_reentry` without positively observed own view does not set `alive`.

## Next bounded real-data verification

1. Reuse already registered DEVELOPMENT recordings through the private source registry (#62/#84), source-bound frames and existing HUD observation/Map candidate producers. Do not use the seven protected recordings or current/future qualification/final sets.
2. Select contiguous ordinary death -> spectator -> next-round sequences, non-death camera overlays/remote-ability sequences and positive revival/return episodes where actually present. Do not invent examples. Freeze the cohort before choosing rules.
3. Review the few transition **edges**, not every intervening frame; check source-native PTS/epoch/pixel continuity separately. Bind each cue to its actual frame, UI source and confidence/review provenance.
4. Compare current-frame-only owner gating against temporal hypotheses on the exact same frames. Report missed transitions, false death, false revival, wrong spectated player ownership, false self-marker binding, UNKNOWN, processing time and manual review count. Report any absence of revival episodes rather than using synthetic ones as real accuracy evidence.
5. Only then design a qualified producer contract and separately approve integration into HUD/Map. In particular, do not bypass existing `live_identity`, `MapTimeline.resolve`, provenance or self-death qualification with these hypotheses. Preserve the existing Production behavior and prior regression tests.

No assumption is made that a self-specific minimap marker remains after death; that earlier claim had no evidence and is withdrawn. No direct Git or external-model transfer of private recording pixels is authorized by this document.

## Public mechanics references

- Sage: https://playvalorant.com/en-us/agents/sage/
- Phoenix: https://playvalorant.com/en-us/agents/phoenix/
- Clove: https://wiki.playvalorant.com/en-us/Not_Dead_Yet
- KAY/O: https://wiki.playvalorant.com/en-us/NULL-cmd

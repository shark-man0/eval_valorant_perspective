# S-01: current-frame state and identity investigation

Judgement **B**. Global evidence transport remains implemented; new Strict accuracy gains are not demonstrated. The separate follow-up branch fixes a legacy Death ownership omission without changing the identity predicate, thresholds, schema or PR #44 production code. Main remains unchanged.

## Source and measurement scope

Base S-01 commit: `a067f341a9c743c78c875bd81379c1243c2c1a49`; fetched main: `7e480c2f2f7f49aea73e1541d065d78881d2f11c`. Both remote SHAs were checked again before this report. Source SHA-256: `71d58558559d6f578433ce9f234bf176f76fd5a86657dbfe3eba1e7d36136b06`. Profile fingerprint: `60b029cb987fe0d7447853e3b4cd791d5defb0918dfaa25a401bd45d2b64c813`. Old recognizer fingerprint: `ad482fe1bae0f2c4401ce0364841f749f63c6e2230ff75c49cf853962c8eb859`; guard-code fingerprint: `6ea410098baf11bbea9df5301ed901373a025e25023c220e1db6a3c01103a6fc`.

Twenty actual matched source PTS were reserved from the original candidate, plus four previously exposed controls. No expected value, acceptance window, desired state or round ID was supplied to the analyzer. Fresh native decoding used original PTS/pixel hashes, a geometry-only prefix under the SHA-specific unedited input contract, and the unchanged recognizer. Isolated frames do not qualify continuity. No new blind holdout is claimed. All 24 pixel hashes and diagnostic records match before/after; terminal source/code/profile hashes verified.

## Actual identity requirements

`hud/identity.py:live_identity` requires calibrated geometry, three independent current-frame structures (HP, ability, weapon/ammo), each explicit true at finite confidence >=0.90, plus checked spectator exclusion and no competing view evidence. Global timer/score cannot supply any of these. The spectator exclusion is a fourth independent safety condition, not a fourth positive HUD structure.

## Twenty assertion measurements

Every row below has calibrated geometry and `player_specific_hud_valid = false`. Structure scores are posthoc calls to the unchanged configured matcher on the same hash-bound native pixels; these are structural similarity, not numeric value confidence. All unknown states have state confidence 0.0; the detected spectator has 0.90. The machine-readable companion retains full precision, confidence by reader, snapshot/trace presence, and all failed fields.

| Assertion | Source PTS | State / confidence | HP structure | Ability structure | Weapon/ammo structure | Spectator detector | First identity rejection |
|---|---:|---|---:|---:|---:|---|---|
| GT-R1-SNAP-0035 | 3.502669 | unknown / 0.00 | 0.9109 | 0.5473 | 0.0000 | panel_structure_excluded | structure_evidence_insufficient |
| GT-R1-SNAP-0415 | 4.152669 | unknown / 0.00 | 0.9695 | 0.9682 | 0.0000 | panel_structure_excluded | structure_evidence_insufficient |
| GT-R1-SNAP-475 | 47.502669 | unknown / 0.00 | 0.9958 | 0.4096 | 0.9472 | panel_structure_excluded | structure_evidence_insufficient |
| GT-R1-SNAP-585 | 58.502669 | unknown / 0.00 | 0.5192 | 0.9952 | 0.7118 | panel_structure_excluded | structure_evidence_insufficient |
| GT-R1-SNAP-595 | 59.502669 | unknown / 0.00 | 0.9661 | 0.8784 | 0.0000 | panel_structure_excluded | structure_evidence_insufficient |
| GT-R1-SNAP-728 | 72.802669 | unknown / 0.00 | 0.9814 | 0.6079 | 0.9871 | panel_structure_ambiguous | spectator_exclusion_unverified |
| GT-R1-SNAP-733 | 73.302669 | unknown / 0.00 | 0.9277 | 0.9256 | 0.9843 | panel_structure_mismatch | spectator_exclusion_unverified |
| GT-R1-SNAP-734 | 73.402669 | unknown / 0.00 | 0.9886 | 0.1414 | 0.9727 | panel_structure_excluded | structure_evidence_insufficient |
| GT-R1-SNAP-7425 | 74.252669 | unknown / 0.00 | 0.9363 | 0.5823 | 0.9815 | panel_structure_excluded | structure_evidence_insufficient |
| GT-R1-SNAP-7438 | 74.386003 | unknown / 0.00 | 0.9925 | 0.7643 | 0.9656 | panel_structure_excluded | structure_evidence_insufficient |
| GT-R1-SNAP-7440 | 74.402669 | unknown / 0.00 | 0.0000 | 0.0000 | 0.0000 | panel_structure_ambiguous | spectator_exclusion_unverified |
| GT-R1-SNAP-7445 | 74.452669 | unknown / 0.00 | 0.1207 | 0.0048 | 0.0000 | panel_structure_ambiguous | spectator_exclusion_unverified |
| GT-R2-SNAP-11145 | 111.452669 | unknown / 0.00 | 1.0000 | 0.9929 | 0.0000 | panel_structure_excluded | structure_evidence_insufficient |
| GT-R2-SNAP-143 | 143.002669 | unknown / 0.00 | 0.9759 | 0.5623 | 0.9944 | panel_structure_ambiguous | spectator_exclusion_unverified |
| GT-R2-SNAP-1475 | 147.502669 | unknown / 0.00 | 0.9608 | 0.8712 | 0.9918 | panel_structure_ambiguous | spectator_exclusion_unverified |
| GT-R2-SNAP-1476 | 147.602669 | unknown / 0.00 | 0.9490 | 0.9976 | 0.9898 | panel_structure_ambiguous | spectator_exclusion_unverified |
| GT-R2-SNAP-1477 | 147.719336 | unknown / 0.00 | 0.0000 | 0.0000 | 0.0000 | panel_structure_ambiguous | spectator_exclusion_unverified |
| GT-R2-SNAP-149 | 149.002669 | unknown / 0.00 | 0.0000 | 0.0000 | 0.0000 | panel_structure_excluded | competing_view_evidence |
| GT-R2-SNAP-151 | 151.002669 | unknown / 0.00 | 0.9931 | 0.1166 | 0.9942 | panel_structure_ambiguous | spectator_exclusion_unverified |
| GT-R2-SNAP-170 | 170.002669 | spectator_first_person / 0.90 | 1.0000 | 0.0223 | 0.9971 | panel_structure_present | spectator_exclusion_unverified |

The 15 current-state rows split into **8 insufficient structure**, **6 unverified spectator exclusion**, and **1 competing-view rejection**. The five life rows split into three ambiguous spectator exclusions, one insufficient-structure row, and one positively detected spectator. At 170.002669, `spectator_detector_checked=true` and `panel_present=true`: the generic live-identity reason must not be interpreted as an unchecked detector. The spectator observation does not prove the source player is dead.

At 73.302669 and 147.602669 all three positive structures exceed 0.90, but spectator exclusion remains unverified. Lowering its threshold or removing that independent check is not an acceptable repair. At 4.152669 the inspected image shows a knife and no ammunition counter: the existing weapon/ammo structural model does not establish identity. At 58.502669, visible first-person UI still produces subthreshold HP/weapon structural matches; this is reference discrimination/generalization, not missing geometry. A visible UI alone does not qualify ownership.

## Observation → Snapshot → Fact → Trace

For each of the 20 IDs, the original hash-verified Full contains the matched main observation, a native snapshot and a trace snapshot at the selected PTS. The companion records aggregate confidence, per-field confidence, fact keys/confidence and trace owner. It labels these as **original Full artifacts**, never new-code recognition. The fresh diagnostic records capture raw accepted reader candidates before owned-field masking. Several HP numeric candidates have high value confidence, but identity remains unqualified: masking them is correct. No qualified owned observation was demonstrated to be lost by transport.

Failure decomposition: structure/exclusion/competing UI prevents current identity; owned-value masking follows intentionally; snapshots preserve independently qualified global values; alive/death and semantic fields are absent/unqualified upstream. Fixing state alone would still leave reload, nonself killfeed, muzzle, subject, location/map or life predicates for the relevant IDs. See the exact failed-field lists in [the matrix](s01_semantic_evidence_root_cause_matrix.md).

## Controls and changes

Four reviewed controls were remeasured at 83.419336 (buy menu), 157.302669 (ambiguous spectator context), 141.936003 (visually first-person witness), and 104.219336 (persistent report). Output: buy-menu / unknown / unknown / unknown, with no owned qualification. The visually first-person witness has three positive structures but ambiguous spectator exclusion and remains unknown. Historical scene labels are not runtime authority.

No identity, geometry, numeric reader, map, threshold, source-continuity or temporal-qualification criterion was changed. No template was fitted or resurrected. The implementable defect was downstream in the legacy Death event caller; see [Death investigation](death_subject_evidence_investigation.md).

## Next producer task

Prepare a separately reviewed identity/reference qualification task, preserving the independent structures and spectator safety: weapon/ammo structural coverage for no-ammo-counter views; ability layout variations; ambiguous spectator negatives; report/remote/menu controls. Freeze development and source-disjoint review cohorts before fitting, retain historical exposure, and reserve genuinely unseen material for final qualification. New templates/criteria are not introduced in this PR. Without such qualification, no state/life PASS gain is guaranteed.

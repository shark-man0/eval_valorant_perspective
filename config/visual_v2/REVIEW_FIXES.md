# Visual Analyzer v1 Review Fixes Applied in v2

This document records the changes made from the external review of Visual Analyzer v1.

## High priority

1. **PEEK-04 exposure count**
   - Removed VLM as a valid authoring source.
   - Added static peek-exposure registry policy.
   - Unmatched positions produce null.

2. **Preaim back-projection**
   - Removed homography/back-projection from MVP.
   - Deterministic timing is limited to near-static / trustworthy-reference windows.
   - Moving cases use low-confidence semantic fallback only.

3. **Map zone dependency**
   - Added runtime map-zone provider contract.
   - Added coarse-zone test fixture and explicit feature-unavailable behavior.
   - Added optional low-confidence A/B site-anchor fallback.

4. **Shot trigger bootstrap**
   - Pass B is now an always-on 5 fps trigger scan.
   - Ammo ROI must be sampled at >=5 fps while live first-person.
   - Cheap recoil/muzzle score is a redundant Pass C trigger.

5. **Visual confidence**
   - Added `visual_confidence_policy_v1.json` with tier-specific thresholds and independent-source requirements.

## Medium priority

- Split macro movement evidence priority from shot-time movement priority.
- Defined shot event granularity as burst/trigger start, not every bullet.
- Added `primary_target_ref` for multi-enemy head-alignment semantics.
- Added cross-Agent remote-view fallback and ambiguity-to-unknown policy.
- Added strict projection policy for intermediate spatial fields.
- Clarified logical ability slots are independent of user keybind text.
- Added per-round/per-match semantic call budgets and API-context isolation.
- Added missing logic tests requested by review.

## Low priority / compatibility

- Preserved `rotation_started.delay_since_enemy_info_sec` because the base deterministic rule engine consumes it despite the current registry omission.
- Clarified `detection_id` is a short-lived tracker ID, not permanent identity.
- Documented that Cypher/Sova/Skye remote views remain real-video validation tasks.

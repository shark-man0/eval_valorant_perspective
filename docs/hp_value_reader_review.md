# HP value reader evidence review

## Scope and decision

IMPLEMENT BOUNDED OPT-IN HP VALUE READER. This is numeric value reading, not HP identity detection. Preserve HP + Ability + Weapon + checked Spectator exclusion, current-frame identity, UNKNOWN and all existing value-clearing rules. No threshold relaxation, Agent/GT/state/timestamp features, OCR fallback or temporal positive persistence is introduced. The production contract supports only observed two/three-component numeric fields; one-component values remain UNKNOWN because their font/placement lacks independent HP evidence.

## Reproducibility and cohort provenance

Starting analyzer is `84ffd0c1b85f7602c76f12d044fe718aa8ab8405`, evaluated clean. Video SHA256 is `71d58558559d6f578433ce9f234bf176f76fd5a86657dbfe3eba1e7d36136b06`; private profile fingerprint is `7c40cf8b719689173b9012ee33c4eb5bfda29619b8eb507e26bacfb68b712b27`. Original odd midpoint role crops were exposed in the early shared visual review and are development data. Forty-six odd-quarter HP regions exclude the entire previously viewed block31 and have no exact HP-crop hash overlap with prior midpoint/even training sources. Their timer regions were previously reviewed. All samples are from one recording and temporally correlated; they are HP-role confirmation, not globally pristine or independent-recording holdout.

Freeze source, geometry, references and policy before blind HP-only transcription; freeze annotations before evaluation. HP candidate manifest SHA256 is `0543612295f8fb398c986848f3aeed0f19afbe0766a02eb53560da77c295a893`. The semantic timer base-policy SHA is `1fa5f1809e181415f928de4f46f38f066b9680f6b37e5d0467248368e014c7c4`; the serialized policy file, including its own stored hash, has distinct byte SHA `7fb0c42f47c5aa1491be3df5d6b75edc88598cbe6d52c5ff612184ce6ca1531a`. These hashes are different representations of unchanged policy, not evidence of modification. References and detailed pixels remain private.

## Mechanism and frozen candidate

Timer fonts alone accept none of 58 extracted HP training glyphs at unchanged .90/.04. HP stroke/raster characteristics differ. Add only recurrent individual HP medoids for classes 0/1/8, supported by 19/16/5 distinct training blocks; retain the full ten-class competitor bank. There are no whole-value templates or allowed-value whitelist. Unsupported HP font variants must fail their glyph score rather than be forced to a class.

The label-blind parser reads the calibrated profile-owned field, uses raw grayscale→2x cubic→normal Otsu, includes every foreground component, rejects crop-boundary foreground, applies complete-bank signed NCC >=.90 with distinct-class margin >=.04, and checks numeric range/leading zeros. Glyph recognition alone is insufficient: 34/49 whole-component removals yield plausible wrong shorter values. Training-only centered typography and interglyph-gap envelopes, expanded by exactly one original pixel, reject all 49 deletions without losing the 16 accepted natural fields. Production geometry belongs to the calibration profile, not recording-specific source coordinates. Single-digit geometry has no support.

## Positive and negative evidence

Training: 16 correct / 0 wrong / 5 UNKNOWN in 21 visible fields. Frozen role confirmation: 26 correct / 0 wrong / 16 UNKNOWN among 42 visible fields; one partially obscured field rejects; three no-glyph fields reject. Other visible numeric styles remain UNKNOWN. Parent independently inspected all confirmation sheets.

Full native counterfactual replay uses exact frame/image joins and the active calibrated ROI, with no search or expected values: 2,417 raw reader accepts among 4,081 observations. Exactly 130 survive the existing analyzer's player-specific validity clearing; 2,287 clear. World-view trust is a separate downstream rule: 123 of these 130 meet it, seven do not. No raw reading in UNKNOWN, Spectator or remote views establishes player ownership. The native baseline itself has no configured HP reader and returns zero HP values; these are counterfactual outputs, not production results.

Forty additional accepted live-region samples, deduplicated against prior source hashes, were independently read by the parent from HP-only sheets before comparing predictions: 40/40 correct. This audits only these accepted candidates and does not establish accuracy for all 2,417 raw reads. Fixed erasure/extra-mark stress produces 1,592 effective trial entries, excluding 18 no-ops. Exact mask deduplication per source field yields 1,522 unique modified masks: zero wrong values, 1,520 UNKNOWN and two still-correct values. Seventy repeated entries include old/new mark duplicates; duplicate outcomes agree. All 20 fixed inner-bar erasures of glyph 8 reject as complete fields, with no glyph 0 flips. These trials derive from 21 source fields and are not independent recordings.

## Integration boundary

Implement a dedicated opt-in HP value-reader contract and explicit profile subregion. Require complete competitor assets and fixed score/margin; malformed explicit configuration rejects without OCR fallback. Return only HP, with minimum current accepted-glyph NCC as confidence. Never call this number probability or identity evidence. Unconfigured profiles and existing HP/Weapon/Ability/Spectator/Map/Visual behavior remain unchanged.

Required integration checks include actual production-class parity, role/malformed-asset/geometry rejection, missing/extra/clipped glyphs, current-frame rejection after acceptance, non-live value clearing, existing tests/static checks, and a committed-source clean E2E with negative 20/0. Production-class and Clean E2E results remain pending; do not substitute offline replay for them. Aggregate evidence is `docs/hp_value_reader_metrics.json`.

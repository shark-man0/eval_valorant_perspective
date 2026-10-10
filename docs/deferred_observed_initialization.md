# Deferred image-supported observed initialization

## Problem / hypotheses / target assertions

The default observer permanently terminates on its first unsupported image, even before any scene history exists. This prevents evaluating an otherwise successful native source chain when a continuous decoder window starts slightly earlier. Separate uninitialized acquisition from failure of an established scene episode. Target remains source continuity upstream of GT-R1-ROUND-START/END and GT-R2-ROUND-START; no GT/timer/phase/round IDs enter the observer. HEAD e9ecaf8f2f0f0dfa1f9433d40a598ec8909e9ce3.

## Contract change

`ObservedSceneChain(..., deferred_initialization=True)` is explicit diagnostic opt-in, defaultFalse. Before successful image-supported initialization, an unsupported image returns `image_supported_initialization_pending`; it retains only PTS/epoch/pixel-hash metadata for native protocol validation. It stores no previous gray frame, tracked world identities or scene history. Subsequent acquisition must pass the existing stateless bootstrap and original-reference identity binding at unchanged conditions.

The actually supported image starts history at its own PTS. It emits no temporal link, backdated start or linkage to earlier pending frames/reference assets. The next successful native observation can link only to this observed seed. Pending gap/epoch/duplicate/discontinuity/malformed input terminates the episode and clears pending metadata. Once a chain is established, any existing failure terminates permanently, including with opt-in enabled. There is no retry/rejoin of an established failed episode and no new producer epoch inferred from appearance.

Reference-identity binding failure remains terminal. This option changes pre-initialization acquisition behavior only; it changes no bootstrap/current-domain/chain/NCC/joint gates, no production pipeline and no runner default. It does not qualify source/UI evidence or prove hidden uninterrupted game time. Player-owned evidence receives no authorization.

## Independent image evidence / native replay

Frozen code/profile/assets/nativePNG/pixel hashes and previously saved native-PTS provenance are recorded before measurement and verified at termination. All frames are exposed development data. Native source spacing256ticks at1/15360is maintained across the6frame prefix and30original frames.

| Replay | Previous | Current | Delta |
| --- | ---: | ---: | ---: |
| Default original30frames supported links |22|22|0; all output dictionaries exactly equal|
| Default prefix+original36frames links |0|0|0|
| Deferred prefix+original36frames links |0default|19|+19development links only|
| Critical R1transient links |0default|5/5|+5development links only|
| Qualification/runtime events |0/0|0/0|0/0|
| Canonical PASS/FAIL/NE |Historical23/55/4|Not rerun|Unmeasured|

The opt-in holds5unsupported images, initializes at native tick59689(3.886003seconds)and links through the same measured R1transient. The first failed established link is tick64809(4.219336seconds), `seed_model_incoherent`; all subsequent frames remain terminated. No source episode restarts and no time from pending images is inherited. Seed PTS is a measured diagnostic result, never a production constant or candidate-selection input. Compared with the previous non-self seed replay,19links/5critical links are unchanged; the new result is acquisition from an earlier unknown prefix, not more accepted continuity after that seed.

Replay wall-clock96.532649seconds includes three verification replays; it is not a canonical E2E speed figure. Terminal bindings match and original30default outputs are exactly equal.

## Tests

30observer tests PASS in31.74seconds. New coverage includes pending-to-native seed without inherited history; pending native gap/epoch/duplicate/cut rejection; explicit boolean option validation; and no reacquisition after established failures in both modes. Existing decoder/source provenance safety remains covered. Ruff PASS; mypy PASS on104production source files; diff checks PASS. No source production code or all82assertion entries changed. Windows/OpenCV execution unverified.

## Continuity decision / remaining blocker

This produces exposed descriptive scene links, not qualified runtime continuity or canonical boundary PASS. Pending unknown observations are not classified as cuts or joined across content edits. Independent current source-world/continuous/negative qualification and paired UI evidence still have to be assessed. No standard targeted/sampled/full E2E was run because production is inactive and qualification incomplete.

Next integrate this explicit option into the frozen native cohort runner, requiring reservation before decode and default compatibility, then test the complete delayed-acquisition path on previously unexposed continuous episodes and negative controls. Never treat this successful exposed replay or synthetic unknown-to-seed test as independent holdout. R1end/R2start/package/trace/canonical completion remains outstanding.

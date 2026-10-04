# HUD evidence follow-up: geometry, numeric labels and portrait presence

## Provenance and scope

Starting shared commit: `f8ba07a`. Production analyzer remains `3e9df3dab16d6dce83f3973f0386638d11286c0c`; native pixel probes use the preceding `4f142acd50eebf6d956893fe3f9c47b4b9bbda7b` replay. Their observations are equal after removing the later HP-reader confidence field. The source video SHA256 remains `71d58558559d6f578433ce9f234bf176f76fd5a86657dbfe3eba1e7d36136b06`. No source, active profile, identity gate or threshold is changed. Raw crops, source timestamps, individual labels and frame dumps remain private. This report contains aggregates only.

## Score: coverage and extraction have distinct failure modes

On the same 48 even-training fields, wider whole-field Otsu retains 16 correct values, local background normalization retains 19, and the earlier narrow candidate retains 38. Each wider candidate has zero wrong accepts in this training set; this is not a negative-separation guarantee. Both reject all nine visible three-digit compositions. The improvement of local normalization is small and does not justify activation.

The extra components are mostly small world/HUD marks. Twenty-one of 26 enemy extra components have area at most 16 pixels after 2x scaling; all eleven ally extras have area at most 16 and height at most three. Numeral height is about 40 pixels. These measurements suggest a bounded extraction experiment, not permission to delete unexplained ink arbitrarily. Numeral fragments and visible multi-digit words must remain observable contradictions to a single-digit interpretation.

A training-derived genuine single digit and the complete erasure of outside digits from a three-digit composition produce byte-identical full inputs. Raw matching accepts both; local normalization rejects both because NCC is low. Neither can recover hidden digits. This intrinsic ambiguity must not be claimed as successful contradiction rejection.

## Purchase-title replay provenance

The native replay has 279 rounded-time joins with multiple cached image paths. All 279 alternative groups have identical decoded pixels; zero groups have conflicting pixels, and zero title-hit decisions change. The 344 literal-title hits are therefore insensitive to this path ambiguity. The matcher remains presence-only; a failed title match does not certify title absence or authorize phase/round inference.

## Map: annulus morphology is measurable, ownership remains unlabelled

Appearance-only review of 32 predeclared even samples finds exactly one clear gold portrait annulus in 30, no multiple clear gold annuli, and two smoke-obscured samples. This is a morphology count, not a self-player count. No odd holdout is opened and no self/ally HSV profile is fitted.

In one fixed illustrative patch, portrait-excluded eight-sector shells have full angular support for both gold and teal portrait annuli (8/8 sectors), versus 4/8 for a yellow angular overlay. Both portrait borders are about two to three source pixels thick. Thus ring versus overlay shape can be distinguished locally, while the historical thicker-self-border cue remains unconfirmed. Multiple colours have real annuli; assigning ownership by colour or uniqueness would exceed the evidence.

## Ammo: audit labels before fitting a role reader

All original 72 and expanded 96 training crops were independently reviewed in ID-only raw sheets. Four original and seven expanded complete-pair labels disagree with the earlier annotations. One apparent accepted `10 -> 12` error is an incorrect diagnostic label: the exact image shows `12`. Superseded annotations and frozen predictions are preserved; correctness counts require rejoining the authoritative pixel labels before any safety conclusion.

Two additional low-level-selected 64-crop training pools were reviewed. Their 22 exact overlaps leave 274 unique crops across the four reviewed pools. A subsequent frozen 24-crop even-training novelty batch adds 24 unique crops, for 298 total, without adding a new clear rare digit class. Three same-image certainty/transcription disagreements were adjudicated by exact single-image review; none remains unresolved. Clear full-word current digit 3 has zero training blocks; its two partial/dimmed appearances cannot establish complete-field evidence. Current digit 6 has one clear block. Reserve digits 2, 7 and 9 have zero full-word support. Block counts describe one recording and do not establish independent recording generalization.

The first field grammar wrongly expected three disconnected separator components. A visible three-column separator often consists of six components, three caps and three stems. The current-number field also includes a neighbouring angular HUD baseline. Correcting those diagnostic assumptions is distinct from lowering the .90/.04 glyph gates. Reserve extraction still requires separate role-font and completeness evidence.

The frozen corrected candidate, rejoined with exact image integrity checks, accepts 25/92 visible current words correctly, zero incorrectly, and leaves 67 UNKNOWN. It accepts zero of 92 visible reserve words. All twelve uncertain/partial cases and all 64 numeric-absence cases abstain; the joint current/reserve/separator candidate accepts zero full pairs. The earlier HP-augmented transfer subset contains 39 visible words plus one absent crop, not 40 visible words: current accepts 11/39 correctly, zero wrongly; reserve accepts zero. Those selected predictions omit one newly corrected positive and are not a replay on the entire 40-positive cohort. Full role geometry and font generalization remain unproven.

Before reader activation, audit downstream confidence: Visual currently derives Ammo confidence from overall HUD confidence. Existing shot inference excludes known weapon switches and reloads, and caps Ammo-only inference for unknown weapon state; a new reader must preserve its numerical confidence and current/prior ownership through that path. Numeric values never provide HUD identity evidence.

## Spectator: global obscuration suppresses locally visible positive evidence

On 4,081 exact native frames, reconstructing the actual pre-template context reproduces all baseline icon results: 461 checked absence, 335 presence, 1,681 globally obscured, 1,551 locally unobservable, 53 ambiguous. Disabling only the global obscured hint diagnostically yields 859 presence hits. The additional 524 all come from globally obscured baseline UNKNOWN frames; none comes from the locally unobservable or ambiguous cohorts.

The 524 suppressed candidates have close-X-only context in 134, buy-grid-only in 106, both in 283, and spike plus close-X in one. These are global context heuristics, not a measurement that the portrait ROI itself is hidden. No newly inferred absence is used and none of these frames becomes live or self-owned.

A randomized ID-only mixed review contains 24 candidates and 24 metric-matched checked-absence controls. The parent independently sees a clear HUD portrait in every candidate and none in the controls. Some portraits persist during the purchase menu. This supports a presence-versus-global-obscuration hypothesis, not accuracy for all 524 candidates or ownership of any portrait. Classification precedence, menu/report/remote interactions and hard negatives must be replayed before a production decision.

## Decision and continuation

`NEED MORE EVIDENCE` for the candidate readers and portrait change. The next experiments are frozen-prediction rejoining, remaining even-training glyph novelty sampling, and a presence-only classification replay with hard negatives. The largest newly measurable blocker is spectator presence suppressed by unrelated global context; checked absence must retain every current strict visibility gate. No arbitrary threshold relaxation or unsafe temporal persistence is proposed.

Current production verification remains 830 pytest passes / two environment skips, Ruff pass, mypy pass (86 files), and diff check pass. The existing committed-source Clean E2E remains 22 passed / 56 failed / four not evaluated, negative 20 passed / zero failed. A diagnostic-only report does not create a new E2E result.

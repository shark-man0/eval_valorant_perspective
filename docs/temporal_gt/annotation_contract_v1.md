# Temporal source annotation contract v1

This is a data-integrity and annotation contract, not a recognizer qualification. No production reader, confidence, timer horizon, canonical GT or default sampler is changed. The existing canonical23 PASS /55 FAIL /4 NE baseline remains historical and unchanged. PR48's separate±0.1s policy is not imported.

## Observable targets

Internal game End, the first screen-observable change, score change, clock change, complete-caption onset, recognizer candidate and recognizer confirmation are separate quantities. This video-only version never asserts internal game End. Label `internal_game_end` unknown/unscorable unless a future separately versioned nonvideo evidence contract exists.

For `display_score_change`, record actual source pixels of the last positively readable old score and first positively readable new score. Consecutive native frames establish an exact visible transition bracket; otherwise retain the real wider bracket and uncertainty. Do not move a label to match prediction or infer an unreadable score. For `display_end_episode`, separately record clock type/literal, first fully displayed caption, actual active Start, next Round and reviewed continuity. These observations are not automatically an internal End timestamp.

All coordinates are original integer source ticks with the exact rational timebase and decoder epoch. Seconds are a display conversion only. No rounding, midpoint truth, interpolation, fabricated epoch continuity or backdating. A missing witness is null plus a reason. Unknown is never negative. Round context can be unknown; a local fragment must not be renumbered to match canonical Round2.

## Required distinctions

Caption types: LOST, WON, CLUTCH, TEAM ACE, NONE, UNKNOWN. Caption state: complete, partial, absent, unknown. `NONE/absent` is positive source review of absence, not an OCR/template nonmatch. A line, animation fragment or partly formed word is partial. Only literal fully displayed text supports `first_complete_caption_pts`; later reader acceptance is not its visual GT. Record actual `last_partial_caption_pts`; do not substitute an earlier entirely absent frame or the last reader rejection.

Clock types: numeric countdown, Spike icon, decimal literal, unknown, occluded. Decimal DD.DD remains a literal and is not converted to countdown seconds. Numeric and decimal values must come from the current image, never expected Round or GT. Score_before/after are readable integers or null. Record source discontinuities, gaps, repeated rasters and unsupported view/context explicitly.

## Independent allocation and review

Before any new source discovery, freeze evaluation-only pool reservations, acquisition grid/budget, this contract/schema/policy hashes, current recognizer code and exposure audit checkpoint. All discovered episodes/outcomes stay enrolled. Source truth may classify a reserved candidate positive/negative/unknown; recognition predictions may not select, relabel or remove it. Physical-event identity is verified from context and represented by a stable key, not by counting nearby frames as independent events. Development/evaluation intervals and reference parents may not overlap or leak across splits; use a declared adjacency guard and keep boundary-adjacent uncertain events unknown.

A human curator views source images without predictions and confirms the bracket/content. AI source transcription is a candidate until reviewed. Every label binds source SHA, epoch, timebase, actual frame hashes, raw request/response artifacts, reviewer, chronological order, uncertainty and evidence hashes. Review of selected images does not prove an entire unviewed interval negative or continuous. Historical source reviews are retained as development regression and never new blind holdout.

Opening for source curation is journaled distinctly from prediction opening. Prediction requires the recorded opening authorization and a method frozen before allocation. Opened or consumed holdout may not be reset to fresh for another method. Hash anchoring detects modifications relative to the retained trusted freeze; a self-reported JSON flag alone cannot prove independence, truth or OS-level access control. Undeclared external activity remains a provenance limitation.

## Natural controls and readiness

Review these natural threat classes independently: normal countdown, score-only, clock-only, Spike-only, decimal-only, partial caption, stale previous-Round caption, buy, menu/scoreboard, spectator, source break, PTS gap and repeated raster. Count distinct reviewed physical episodes per class, not frame repetitions. A mixed positive/negative window is not a pure negative. A detector nonmatch is never a negative label.

At least two distinct unseen Spike→Decimal episodes are an engineering replication minimum when available, not a statistical guarantee. Readiness requires traceable independent allocation and review, current source/preflight bindings, method/profile/assets/policy frozen before prediction, complete temporal context for the declared scope and all required natural-negative coverage. Missing conditions mean BLOCKED with exact counts and acquisition needs. Partial score-display GT may be complete for that narrow target while full End temporal GT remains incomplete. Qualification-ready never means Formal End PASS or authorization to release events. No recognition or Full E2E is performed by these tools.

## Privacy and freeze

Private recordings, frames, source paths, raw human responses, detailed PTS/score/caption labels, exposure rows and frozen dataset stay outside Git. Public outputs are a fixed whitelist of anonymous counts, hashes, rule names and readiness. Freeze canonical UTF-8 JSON and retain an external trusted SHA anchor. Revalidate artifact/source/contract hashes with shared `UneditedInputContract`, `NativeSourceFrame` and PR55 preflight. The validator does not reimplement decoding, retune readers or certify semantic truth from file presence.

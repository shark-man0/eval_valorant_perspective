# Practical shared timeline development

The existing `DevelopmentGameTimeline` remains the only game-state engine.
Research state estimates and formal qualification remain separate.

The development `temporal.match` and `temporal.application generate` CLIs accept
exact `--coarse-seconds`, `--dense-seconds`, `--max-refinement-seconds`, and
`--max-refinement-windows` settings. The historical defaults remain available,
but are not research limits. For example, compare current `1 / 1/5 / 240 / 40`
with expanded `1 / 1/5 / 2000 / 400` observation settings.

`--full-density --dense-seconds 1/5` observes the entire recording at approximately
0.2-second cadence in addition to retaining the normal coarse points. This mode
explicitly bypasses adaptive window/duration budgets. Native PTS and actual
selected samples remain authoritative; the requested cadence is not an assertion
that every native frame or precisely every fifth-second was recorded. It is still
projected into the existing one-second timeline. Checkpoints bind all settings.

Use only registered DEVELOPMENT recordings and new private output/cache paths.
Freeze code, observer/model/reference configuration and comparison conditions
before acquisition. Keep old predictions and evaluation labels unchanged. Never
reuse an incompatible checkpoint or count another sampling of one match as a new
physical match. Local resource permission does not authorize media uploads, paid
services, protected recordings or main merges.

Full-density observations can be subset retrospectively using only the original
coarse pixel measurements and the existing adaptive selector. This comparison
holds the recognizer and native pixel grid fixed while changing available input
density. Dense-grid phase can differ from a separately decoded adaptive pass;
report this distinction and retain historical actual-acquisition results.

`--practical-visual-state` connects existing composite-view and Round visual
observations to the shared engine's research estimates. Each revision retains
the previous estimate, competing hypotheses and native evidence. A current HUD
component plus a prior recorder signature can support SELF/ALIVE; an agent name
alone cannot. Remote, downed, death and spectator evidence veto self promotion.
The default recognition path and formal qualification gates remain unchanged.

The optional image-only `valorant_ai_coach.temporal.screen_cues:ScreenCueObserver`
wraps a configured parent using `parent_observer`, `parent_config` and `tessdata`
JSON keys. Local OCR reads purchase captions, English VICTORY/DEFEAT result text
and HUD location names. A native pale-blue veil measurement can support a Round
start when it disappears after an observed BUY with a compatible map view.
Blue sky persistence, a failed OCR scan and source end do not start/end a match.
These cues are research candidates; the world-barrier heuristic is not a general
barrier segmentation model. Map and Zone readers can return empty candidates.

Current-view marker rankings are joined to Camera/agent candidates and retained
as `research_view_position_hypotheses` in JSON, CSV and the viewer. They do not
become strict recorder positions, paths or qualified Map ownership. SPECTATOR
positions describe possible viewed actors and exclude the recorder-self role.
An older reference catalog covers only its listed maps/version; it is not proof
of support for every current map. Downstream evaluation consumes the same
application bundle with zero qualified Facts/Events.

## Running a registered recording

Use the existing private DEVELOPMENT registry/admission policy. Supply the same
observer configuration for each physical match; Source IDs select admitted input
and are never passed to the image observer. No roster, first state or known event
time is required. Required local OCR models and existing HUD/profile assets must
already be configured. An optional public-reference Map wrapper can be omitted;
empty Map/Zone observations do not prevent timeline generation.

```bash
python -m valorant_ai_coach.temporal.application generate \
  --policy "$TIMELINE_POLICY" --source-id "$TIMELINE_SOURCE" \
  --reader-config "$TIMELINE_READER_CONFIG" \
  --observer valorant_ai_coach.temporal.screen_cues:ScreenCueObserver \
  --output "$TIMELINE_OUTPUT" --checkpoint-dir "$TIMELINE_CHECKPOINT" \
  --coarse-seconds 1 --dense-seconds 1/5 \
  --refinement-policy evidence --max-refinement-windows 400 \
  --max-refinement-seconds 2000 --refinement-padding-seconds 4 \
  --report-view-bridge --buy-clock-expiry --active-clock-bridge \
  --return-display-tail --buy-clock-tail --current-hp-return-candidate \
  --current-menu-return-candidate --provisional-map-roles --practical-visual-state
```

Add `--full-density` for the entire approximately 0.2-second observation pass.
For a configuration change, use a new output/checkpoint directory. To resume an
interrupted compatible acquisition, keep its checkpoint but use a fresh output
directory; the verified native prefix is replayed, not treated as completed state.
An output completion receipt, not a progress message, establishes completion.

The output contains the full `timeline_PRIVATE.json`, one JSON-valued CSV row per
recording second in `timeline_1s_PRIVATE.csv`, `evaluation_PRIVATE.json` from the
existing review consumer, and hashed completion/provenance receipts. Exact native
samples remain available alongside the one-second view. Keep these artifacts
private. Open the local viewer and use its recording-time control to seek the
unchanged original recording:

```bash
python -m valorant_ai_coach.temporal.viewer \
  --bundle "$TIMELINE_OUTPUT/timeline_PRIVATE.json" \
  --policy "$TIMELINE_POLICY" --port 8783
```

The deterministic evaluation package remains empty
of qualified Facts/Events while the development consumer uses state/candidate data.

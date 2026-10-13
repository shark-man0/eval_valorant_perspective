# Issue #16: current-main source preflight and qualification blockers

## Decision

**C: unqualified / blocked on private recognition evidence.** This checkpoint
does not establish current-code Round lifecycle qualification. It supplies a
reproducible source preflight, a production-path audit and safety regression.
No recognizer, threshold, GT, sampler, ownership policy or qualification bundle
is changed. No standard full E2E, targeted recognition or sampled recognition
is run. The adopted canonical result remains historical **23 PASS / 55 FAIL /
4 NE**; the earlier native **27 / 51 / 4** is not a current measurement.

Latest main was fetched before starting. Both starting HEAD and origin/main were
`c11ec6d333957cccb270417bc95a8a57f433e6ad`; the checkout was clean. The dedicated
branch is `codex/round-boundary-requalification`. No other AI branch was changed.
The checkpoint was measured on macOS arm64, Python 3.12.15, FFmpeg/ffprobe 9.0.2,
OpenCV 4.14.0 and NumPy 2.5.4. This differs from the historical Linux environment.

## Current production recognition path

| Stage | Actual entrance / contract | Release status and limits |
| --- | --- | --- |
| Native source | `video/native.py:decode_native_window`; `video/native_replay.py:decode_native_replay` | Source SHA, exact integer PTS/timebase, frame order and decoded pixels verified. Each window owns a new decoder epoch. Storage replay preserves the logical epoch, checking every decoder pass. |
| HUD observations | `hud/analyzers.py:RealHudAnalyzer.observe_frames` | Current calibrated ROIs, configured timer/score/phase/result readers; unknown remains unknown. |
| System projection | `hud/native_system_input.py:collect_native_system_observations` | Source-bound global values and original display strings only. Player-owned facts are cleared; projection alone supplies no qualification or continuity proof. |
| Diagnostic transport | `bind_native_ui_measurements`; unqualified UI/start/end diagnostics | Diagnostic measurements and candidates cannot be published as formal events. Calibration prefixes are geometry-only, not temporal support. |
| Qualification | `global_lifecycle.py:GlobalLifecycleQualification.load`; `native_assured_start.py:current_assured_qualification` | Requires current profile/assets/code binding, reviewed support and disjoint component splits. Injected readers cannot inherit qualification. Admission is distinct from independent temporal accuracy. |
| Paired scene route | `native_lifecycle.py:collect_qualified_native_lifecycle` | Explicit opt-in; producer-owned scene and positive UI absence evidence joined at exact source identity. Missing paired scene/UI qualification rejects. |
| Source-assured route | `RealHudAnalyzer.observe_qualified_unedited_native_start_frames` → `collect_qualified_assured_start` | Explicit source-specific unedited contract plus current timer/phase/UI qualification. Assurance does not exclude repeated pixels or hidden capture loss. |
| Start/end decision | `UneditedUiStartTracker` → `UneditedRoundLifecycle` / `UneditedUiEndTracker` | Preparation and coherent subsequent clocks confirm starts. Delayed end requires separately qualified timer/score/result/UI-end support in one segment. Exact original score-change time and later confirmation time stay separate. |
| Formal event | `replay_assured_starts` / `_join_native_lifecycle` | System actor, source frame identity, code/profile/qualification and segment attached. No player identity is inferred. |
| Application merge | `HudVideoProcessor` → `validated_native_boundaries`, `native_source_breaks`, `merge_native_boundaries`, `merge_native_timer_displays` | Actual lifecycle is replayed at admission/completion. Conflicts, source/qualification drift and unsupported break consumers reject. Global clocks merge only at exact source ticks. |
| Package | `rounds/builder.py:RoundPackageBuilder` | Segment-local start/end membership, preparation before the next start, duplicate/conflicting boundary guards, schema validation. Duration sentinel for an open package is not a detected end or observation coverage. |
| Trace | `tests/e2e/trace_adapter.py:to_e2e_trace` | Preserves event actor/type/time/confidence/attributes and explicit package membership. GT is evaluator-only. |
| Practical route | `practical_lifecycle.py`, processor `boundary_mode="practical"` | Opt-in provisional evidence stays provisional; it cannot satisfy Strict qualification or create a scored complete round. |

The standard sampled analyzer does not automatically install an experimental
qualification bundle. System events are production-capable only through the
qualified entrance with current inputs; the historical native report is not an
active runtime proof. The broad recognizer fingerprint includes HUD, native
decoder/service, application merge, package builder and visual consumers.

## Source-backed measurements

`scripts/e2e/preflight_round_source.py` uses the unchanged production native-window
decoder. It has no Validation Pack input, recognition call, GT time correction,
event injection, bundle writer or qualified-output route. Optional profile and
bundle arguments invoke the actual source-assured loader; even accepted admission
is labelled **not temporal qualification**. Terminal source/code/contract and,
when supplied, profile/bundle changes withhold the result.

Verified source SHA256:
`71d58558559d6f578433ce9f234bf176f76fd5a86657dbfe3eba1e7d36136b06`.

Current recognizer fingerprint:
`5b32ea0c5be3d23aadd5e1ef4057619c10c7104d3d210a69d39433bffea6dfc8`.

Input-contract SHA256:
`8f26e53ddf2c11c30e8d4651e3f93a66f48de7793036588ee10514925f6e8a87`.

The complete source **metadata probe**, not complete recognition, contains
10,259 frames, timebase `1/15360`, first tick `553`, last tick `2626601` and
10,258 adjacent steps of 256 ticks. Last frame PTS is `171.00266927083334`.
Uniform PTS cannot attest uninterrupted recording or visual scene continuity.

| Separately decoded window | Frames | Actual first–last PTS | Retained PNG bytes | Adjacent raster repeats |
| --- | ---: | --- | ---: | --- |
| Source origin–0.1 sec | 4 | 0.036002604–0.086002604 | 8,016,954 | 0 |
| 81.70–81.90 sec | 12 | 81.702669271–81.886002604 | 25,748,283 | 2 |

Both windows match the whole-source probe's ticks exactly, with encoded/pixel
hashes rechecked before reporting. Each owns a different epoch; they were never
concatenated into a recognition sequence. The measured raster repeats are:

| Previous tick | Repeated tick | Repeated frame PTS |
| ---: | ---: | ---: |
| 1255977 | 1256233 | 81.78600260416667 |
| 1256745 | 1257001 | 81.83600260416667 |

These independently reproduced source facts preserve the known reset requirement
between R1 and later preparation. They do not prove no additional source breaks
outside the decoded windows, or certify either boundary. Source preflight took
48.946 seconds including complete metadata probe, bounded decode and terminal
checks. Maximum measured retained window PNG payload was 25,748,283 bytes under
the explicit 256 MiB per-window ceiling; temporary images were deleted on context
exit. Decoder logs/overhead and process peak memory were not measured. There was
no extrapolation to full-video recognition runtime or storage.

The machine-readable sanitized result is
`e2e_reports/match_001/round_boundary_requalification_preflight.json`.

## Components, independence and missing inputs

| Component | Current source reader replay | Real bundle admission | Independent temporal qualification |
| --- | --- | --- | --- |
| timer | Not measured | Not attempted | Not established |
| purchase_phase | Not measured | Not attempted | Not established |
| ui_transition | Not measured | Not attempted | Not established |
| score | Not measured | Not attempted | Not established |
| round_result | Not measured | Not attempted | Not established |
| ui_end_transition | Not measured | Not attempted | Not established |

The current guarded profile, associated reference/glyph bytes, source-reviewed
original labels, physical/pixel split inventory and exposure ledger are not
available in this clone or the inspected local Codex asset locations. The
historical reports locate them in a private Linux investigation tree. Local
legacy calibration profiles are not equivalent to that frozen guarded profile.
Public report hashes and counts do not reconstruct original source review or
independence; no bundle was re-signed or synthesized from those counts.

The original experimental qualification bundle is also unavailable, so its
**actual** stale-loader rejection was not replayed here. Synthetic tests exercise
the real loader and receiver's stale-code/profile/qualification rejection. That
contract verification is not a real-component or historical-bundle audit.

The repository already tracks a v3 Validation Pack and assertions. None was
passed to this preflight or to a recognizer, changed or added in this PR. Their
identity with the original private adopted evaluation pack is not established
by this run. No assertion result is newly measured. Match_002 GT was not used.

There is no new training, holdout or negative recognition cohort. Re-decoding
the source origin and known duplicate window does not make them new blind
holdout data. All historical development exposure remains historical. Adjacent
support frames from the single known end must not be counted as independent
end episodes. The earlier failed early-caption variants, frozen timer profiles
with wrong readings, fixed-ROI universal scene proof and PNG-budget workaround
were reviewed in the required documents; none was repeated or adopted.

## Round and safety results

| Target | Detection time | Confirmation time | GT result | Confidence | Qualification |
| --- | --- | --- | --- | --- | --- |
| R1 Start | Not measured | Not measured | Not evaluated | Unknown | Unqualified |
| R1 End | Not measured | Not measured | Not evaluated | Unknown | Unqualified |
| R2 Start | Not measured | Not measured | Not evaluated | Unknown | Unqualified |
| R2 End | Not measured | Not measured | Not evaluated | Unknown | Unqualified |

No current real native event, package or trace was produced. This does not mean
zero false positives, missing boundaries or package errors. Real-video false
positive, duplicate-boundary, source-crossing, player-misattribution, package
membership and trace-error rates are **not evaluated**. In particular the
16 decoded integrity frames cannot establish no R2 end over the remaining video.

Previous R1-end time `74.486003`, confirmation `75.369336` and approximately
3 ms GT miss remain historical. There is no new physical timing evidence or
claimed delta. No event is rounded, backdated or moved to the GT window.

## Validation

- Dataset validation: **38 cases PASS**, schemas and selection contract valid.
- Required lifecycle/native/Strict/Practical modules: **341 PASS**, 26.49 seconds.
  These cover stale binding, missing/weak evidence, duplicate starts/ends, exact
  source PTS/epoch, gaps/repeated pixels/cuts, system-only actor, preparation,
  delayed boundary/confirmation separation, package/trace transport and refusal
  to promote provisional end evidence through start-only qualification.
- New preflight tests: **14 PASS**, 0.16 seconds. Nonzero origin, variable cadence,
  no capture/scene qualification from uniform PTS, adjacent raster repeats,
  mixed epochs/source/geometry, changed encoded assets and source SHA rejection.
- Package/lifecycle/fixture regression: **115 PASS**, 5.91 seconds (overlaps with
  the related-module run; these counts must not be added as distinct tests).
- Ruff: PASS on `src tests scripts/e2e`.
- mypy: PASS on all 131 production source files.
- Full pytest/coverage: launched after this source checkpoint; the final local
  result is recorded in the PR description. Linux/Windows results are attached
  to the exact pushed commit in PR checks. Starting-main SHA has successful
  Linux run `38382176934` and Windows run `38382176853`; later cancelled runs do
  not add verification. No Qt exit abort has been observed at this checkpoint.

The first related-test launch failed collection because this workstation's
inherited `PYTHONPATH` selected another project's `tests` package. Re-running
with `env -u PYTHONPATH` resolves the environment collision. The failed log is
retained locally; no test predicate or source contract was changed.

## Reproduction and next action

Run from a Python 3.12 project environment with FFmpeg/ffprobe on PATH:

```bash
env -u PYTHONPATH python scripts/e2e/preflight_round_source.py \
  --video '<private match_001 video path>' \
  --source-sha256 71d58558559d6f578433ce9f234bf176f76fd5a86657dbfe3eba1e7d36136b06 \
  --input-contract datasets/input_contracts/match_001.unedited.json \
  --window 0 0.1 --window 81.70 81.90 \
  --max-png-bytes 268435456 --output work/source-preflight.json
```

To audit loader admission, additionally supply the **actual** frozen layout via
`--profile` and its original bundle via `--qualification`, preserving the
relative reference assets. A stale bundle must fail; supplying a new fingerprint
without fresh recognition is prohibited. Accepted counts alone do not qualify
the whole temporal path.

Next obtain the guarded layout/template/asset tree, original split/source labels
and exposure ledger, and original bundle for rejection comparison. Verify all
asset/source ancestry and pixel hashes; freeze current code/profile/method before
new recognition. Then execute fixed components, separate continuous native
windows and negative/discontinuity controls, followed by qualified real entrance
and package/trace verification if the evidence warrants admission. Keep R1 End
unqualified where independent temporal support or timing fails.

A new video is not yet demonstrated necessary: first inspect the available
match_001 evidence and unused data. However, the one previously exposed end
episode cannot alone establish independent end-event generalization. Issue #20
full E2E handoff requires current qualification, independent evidence, fixed
source, negative regression, resource estimates and comparable evaluation
conditions; those gates remain unmet. This PR is a preparatory checkpoint, not
an Issue #16 completion or a qualification merge candidate.

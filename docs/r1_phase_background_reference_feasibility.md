# R1 phase-background reference feasibility

## Problem / target

R1 scene transport still lacks a qualified current UI-disappearance producer. A potential implementation is to match the background revealed in the purchase-panel ROI rather than infer absence from a failed text match. Target: `GT-R1-ROUND-START` and downstream count/order/package dependencies. This investigation tests feasibility of that specific reference approach; it does not generate or adopt a recognizer.

HEAD `e9ecaf8f2f0f0dfa1f9433d40a598ec8909e9ce3`.

## Evidence / hypothesis

The existing panel-removal and background-reveal diagnostics provide corroboration but no absence authorization. Color agreement also occurs with an artificial opaque surrounding-color cover. A genuinely textured background reference might add positive structural evidence while rejecting flat covers.

[The fixed probe](../e2e_reports/match_001/r1_phase_background_support.json) uses the already investigated native3–6s sequence, original panel bounds[738,135,1183,281], and the reviewed first panel-gone frame tick63017 as a development proposal. Neither GT, expected timer/score/round ID nor acceptance window is read by the script. Tick selection is an explicit offline image input, never a production condition.

The panel is divided into three fixed non-overlapping horizontal portions, columns[0,149),[149,297),[297,445). No contrast-selected pixel mask is mined. All180 encoded and decoded native source hashes, source report and scoring code are verified before/after measurement. This entire sequence is exposed development data; none is promoted to independent holdout.

## Independent image evidence

At4.086003s the actual phase-present panel has gray standard deviation31.793936, with group contrasts33.993607/32.782590/27.333418. At4.102669s, after the observed panel removal, total standard deviation is1.200509 and the fixed group contrasts are:

| Group | Gray standard deviation | Existing masked NCC contrast floor |
| --- | ---: | ---: |
| Left | 0.850787 | 5 |
| Middle | 1.650267 | 5 |
| Right | 0.530326 | 5 |

`weapon_identity.masked_score`, reused by existing semantic text matching, returns unknown score0 when either selected image has standard deviation<5. All three proposed reference groups fail this prerequisite. All-group support is0/180 under unchangedNCC≥0.90 and contrast floors, including reference-self evaluation. This is a failed reference-support test, not a measured phase-absence recall rate.

The shadow whole-ROI NCC at the first transient frame is0.995611 and later at4.202669s remains0.905897. These high whole-crop scores do not override the absent group contrast. A full-crop scalar can conceal which portions lack usable structure. The low-contrast background is compatible with an actually removed panel but cannot by itself establish an independent semantic absence reference.

## Continuity decision

This investigation addresses UI evidence only. It neither classifies content cuts nor changes the previous distributed-background analysis. Phase absence remains unknown. Neither failed positive text matching nor high low-contrast whole-crop similarity supplies a qualified UI-transition proof.

## Contract change

None. Reject the specific fixed background-reference proposal before asset generation or qualification. No profile/reference/mask bundle is created, no existing contrast/NCC threshold is reduced, and no synthetic report is installed. The result does not prove that every possible UI-transition design is infeasible; it rules out treating this near-flat revealed ROI as a supported three-part masked-NCC reference. Existing player identity, ownership, spectator, geometry, OCR, map, discontinuity and full-sampler policies remain unchanged.

## Tests

The existing semantic reference/context suite passes29tests in0.74s. Ruff passes over `src tests scripts/e2e` and the new diagnostic script. Production source hashes in the preceding native guard remain unchanged. Mypy was previously green on the same113productionfiles; this follow-up changes only diagnostic/report/documentation files. These tests verify existing contrast/presence contracts, not real absence qualification.

Reproduce with a new output path:

```bash
python3 scripts/diagnostics/audit_phase_background_support.py \
  --source-report e2e_reports/match_001/r1_continuous_source.json \
  --reference-tick 63017 --panel-box 738 135 1183 281 \
  --output /tmp/r1-phase-background-support-new.json
```

## Previous / Current / Delta

| Metric | Previous | Current | Delta |
| --- | ---: | ---: | ---: |
| Fixed background-reference feasibility evaluated | No | Yes | New rejection evidence |
| Supporting frames for this proposal | Unmeasured | 0 / 180 | Not comparable |
| Adopted UI-disappearance qualification | 0 | 0 | 0 |
| Runtime UI-transition proofs created | 0 | 0 | 0 |
| Canonical PASS / FAIL / NE | 23 / 55 / 4 archived | Unmeasured | Unmeasured |

No new targeted/sample/full canonical run is claimed. Full E2E is not justified without independently qualified R1/R2 starts and R1 end. All82archived assertion entries remain unchanged. No canonical negative/discontinuity regression measurement is invented.

## Remaining blocker / next implementation

A current UI-transition producer needs positive independent evidence beyond text nonmatch, surrounding-color extrapolation or a near-flat background template. Investigate other visible global lifecycle structures and temporal corroboration in the existing video, preserving unknown whenever their qualification is absent. Keep every transient observed clock display; do not reinterpret2:25as an OCR error or special-case its value. Native system lifecycle/event/package/trace integration and canonical acceptance remain unfinished. Windows runtime is still unverified.

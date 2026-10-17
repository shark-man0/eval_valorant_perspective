# Self Death: measured rifle-reference coverage

Status: **development/regression improvement; not independent qualification**.
The resumed investigation starts from main
`7e480c2f2f7f49aea73e1541d065d78881d2f11c` and reader branch
`556dbac594bec11fb584bbf39d6e7d935885997d`.

## Failure localization

The fixed nine-frame confirmation probe previously found numeric weapon
support on two frames and only geometric support on seven. Measuring every
existing reference within the reader's actual same-row search region showed:

- All three reference dimensions fit each search region.
- None of the seven unsuccessful frames had any NCC location at or above
  0.90, even before the independent team-plate check.
- Their best NCC across the existing bank ranged from 0.603532 to 0.749064.

This establishes missing reference coverage for these measured frames. It does
not establish the weapon class or failure cause for every other episode.
Removing the plate check, changing transport, or relaxing NCC cannot be justified
by these measurements.

## One frozen development change

One previously exposed development frame supplied the already measured white
weapon component, with a fixed three-pixel surrounding plate border. Its crop
contains the icon and plate, excluding player text, portrait and result labels.
No resizing, scale search, threshold search or GT input was used. The resulting
28-by-82 reference was appended to the existing bank; all original arrays were
preserved byte for byte. The recognizer implementation was unchanged.

The complete nine-frame comparison set was fixed before evaluating this bank.
One frame is training; the remaining eight are previously exposed regression
frames. **None is a fresh blind holdout.**

| Confirmation-frame measure | Previous | Current | Delta |
| --- | ---: | ---: | ---: |
| Numeric victim support, all nine frames | 2 | 5 | +3 |
| Numeric victim support, eight regression frames | 2 | 4 | +2 |
| Training-frame support | 0 | 1 | +1 |

The two additional regression matches have actual NCC 0.990943 and 0.994402.
The training-frame self-match is excluded from evidence of generalization.
Four regression frames still lack numeric support. They remain unqualified;
no further reference tuning was performed in this experiment.

## Continuous comparison and negative controls

Both profiles were rerun over the same 181 native frames, at the original
cadence, with the same source cache, OCR/toolchain, runtime code and one OpenCV
thread. The older four-thread results are not used as the timing baseline.
Each run verifies the original source hash and all input/dependency hashes at
termination. No source video was copied and no new Full E2E was run.

| Measure | Previous bank | Expanded bank | Delta |
| --- | ---: | ---: | ---: |
| Processed native frames | 181 | 181 | 0 |
| Frames with numeric victim support | 0 | 83 | +83 |
| Diagnostic death predictions | 1 | 1 | 0 |
| Source-blocked frames | 0 | 0 | 0 |
| Formal Death events | 0 | 0 | 0 |
| Recognition time, seconds | 204.572 | 207.510 | +2.938 |
| Wall time, seconds | 350.002 | 353.305 | +3.303 |
| Peak RSS, bytes | 99,463,168 | 99,454,976 | -8,192 |

The single candidate retained its original onset and later confirmation. The
83 correlated frames are not 83 independent successful deaths. The change
adds numeric evidence to a candidate already found by the geometric path;
it does not increase event detection count.

The expanded profile also processed all 98 native frames from two existing
nonself/spectator negative windows. Both produced zero predictions and zero
source-blocked frames. Recognition took 85.454 seconds; total wall time was
222.082 seconds. Terminal hashes passed. These limited negative controls do
not establish a whole-match false-positive rate or replace the previous,
longer negative suite under the new profile.

## Reproducibility and private artifacts

Images, reference assets, profiles, player text and detailed source records
remain private. The following artifact names are relative to the existing
private `self-death-positive-20261016` investigation directory:

- `frozen-separator-failure-localization.json`: unchanged-bank score diagnosis.
- `source2-rifle-coverage-development-v1-freeze.json`: source/crop binding,
  exposure classification and immutable profile/asset hashes.
- `source2-rifle-coverage-development-v1-role-comparison.json`: fixed nine-frame
  field comparison; no temporal qualification claim.
- `source2-rifle-coverage-development-v1-before-continuous.json`: old bank,
  SHA-256 `0f1afbd1a6c4519f054445d149e795ae23a8af8cffdd65f7214b1a0deed779c0`.
- `source2-rifle-coverage-development-v1-continuous.json`: expanded bank,
  SHA-256 `4e34288504c1e8c31971acfe88b22aa99e86a9f593dff7c0056762b1d1a74203`.
- `source2-rifle-coverage-development-v1-negatives.json`: negative controls,
  SHA-256 `85e2dfb87fa9945bf40064d96174ef48897ae8127215fa1274bb4f05432778ed`.

The expanded profile fingerprint is
`7b94e3e04c7530ed168c9107f1b82073be9aea62b3872908bfbdd4730a61beb8`.
Its asset digest is
`596f0ea7cd817042bf0dd0b9e99a47834c55c61d7e06de00f043a3da65733586`.
The reader runtime fingerprint remains
`0ffe0bf9e5e1b26baad437a8dac235fd3ec453fae8262847ea6a0e0aff304832`.
Both continuous comparison runs use dependency fingerprint
`c762f7e7d72d81378630da7054f0faab59a76256fc924dba24bf7719550474d7`
and reader code fingerprint
`62e973fc991a496de7a889c7f9cb41b79d23e0e8339dda8c6c9216d1260529c2`.
The earlier four-thread dependency fingerprint is deliberately not relabeled.

## Qualification and next action

No new qualification certificate was issued. No source evidence was changed
to reviewed Self, and no formal Event, player-owned Fact or HUD identity was
enabled. Strict canonical PASS/FAIL/NE was not rerun: adopted 23/55/4 and the
archived unadopted 28/50/4 remain separate historical results.

Before release, freeze a source-backed evaluation split outside all development
exposures, qualify the actual owner/victim/transition witnesses, and rerun the
required continuous and negative suites under this exact profile. Global
exposure history for the second match remains uncertain; existing development
images cannot be renamed blind holdout. Supplemental recordings are optional
possible material, not a prerequisite: their useful contents have not been
verified. No transfer is requested on the capacity-constrained device.

This experiment changes the next action from investigating a transport loss
to qualifying improved reference coverage. It is not Strict E2E FAIL reduction
or completion of the Self Death goal. Production code and test files are
unchanged; the prior code CI results remain historical results at `556dbac`.

## Frozen continuous follow-up

With the same reference bank and no intervening tuning, a second previously
exposed episode was rerun over 181 native frames. It produced one diagnostic
candidate, 60 frames with actual numeric victim support, no source-blocked
frames and no formal events. Its confirmation-frame weapon NCC was 0.994402.
Recognition took 193.978 seconds; wall time was 339.352 seconds and peak RSS
94,064,640 bytes. This extends the single-frame match to a continuous episode;
it remains a known regression case, not independent qualification.

The identical expanded asset bank was then bound to the existing match_001
source profile and freshly evaluated over all 171 cached inputs of the original
positive/short-negative suite. All input source PTS/pixel hashes and both
candidate onset/confirmation pairs were compared with the original frozen
result and matched exactly. The two genuine episodes each retained one
diagnostic prediction, while both stale-report/spectator controls retained none.
The initial short R1 window still has no prediction because it ends before
corroboration; the extended window supplies the single R1 candidate. They are
not counted as separate episodes.

| Follow-up measure | Previous result | Expanded bank | Delta |
| --- | ---: | ---: | ---: |
| match_001 cached input rows, including overlap | 171 | 171 | 0 |
| match_001 diagnostic episode predictions | 2 | 2 | 0 |
| match_001 short-negative predictions | 0 | 0 | 0 |
| match_001 source-blocked frames | 0 | 0 | 0 |
| match_001 formal Death events | 0 | 0 | 0 |

The match_001 run took 197.561 seconds for recognition, 206.004 seconds wall
time, and peak RSS 94,420,992 bytes. Timing deltas against its archived run are
not claimed: that older result used four OpenCV threads and a different
dependency fingerprint. The newly generated results use the one-thread
fingerprint recorded above and pass terminal source/dependency/config hashes.

Private follow-up evidence:

- `source2-rifle-coverage-development-v1-extended-plan.json`: frozen input and
  profile hashes, expected positive/negative counts and stop conditions.
- `source2-rifle-coverage-development-v1-second-continuous.json`, SHA-256
  `c7e56c60547ae94887172921a5834be21b110a24c8c22aa08a3311f053b4fb3e`.
- `source2-rifle-coverage-development-v1-match001.json`, SHA-256
  `ac09ffdd6ab993ebe283c782da8ab8609f9b7409c8ba5e8859e11da3aef12548`.

The second-source continuous episodes together contain 143 numeric victim
support frames (83 plus 60), which are correlated evidence for two known
episodes, not 143 independent successes. No expanded-bank full-length negative
suite, blind-positive qualification, new canonical evaluation or formal release
is claimed. No additional videos were transferred or decoded-frame caches
created for this follow-up.

At documentation commit `406ea1bb4225c65ebe819ba3b616c91d28e8bae6`, both Linux
checks, both Windows test-and-build checks and the text-I/O audit subsequently
completed successfully. The follow-up changes only this report; it does not
claim those checks ran on a later documentation commit or qualify the private
reference assets. No production-code change required a new local pytest,
Ruff or mypy run in this follow-up.

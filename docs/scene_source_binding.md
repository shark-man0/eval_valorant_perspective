# Source profile binding and native lifecycle delivery contract

## Problem

The common source acquisition path now lives in production modules, but its
reviewed source profile and reference images previously had no entrance into the
HUD qualification fingerprint. Binding only HUD templates would allow a future
scene producer to inherit a report for different source assets.

Target assertions remain `GT-R1-ROUND-START`, `GT-R1-ROUND-END`,
`GT-R2-ROUND-START` and their event-count/ordering constraints. This change does
not claim a new boundary or an assertion gain.

## Evidence and root cause

HEAD is `e9ecaf8f2f0f0dfa1f9433d40a598ec8909e9ce3` on main. The adopted archived
full run remains 23 PASS / 55 FAIL / 4 NE; no new full run was executed.
The actual local reviewed-domain profile loads under the common validation,
including encoded image SHA256, decoded pixel SHA256, relative path containment,
review provenance and excluded HUD domains. It is still explicitly unqualified.
Its SHA256 is
`32606afdf1d6b49dd136a37cfa2576af7d3a0bfc297982e78e20bca25da0b6ff`.

## Change

`SceneSourceBinding.load()` uses the actual `WorldDomainBootstrap` validation,
captures the source JSON and referenced asset hashes, and verifies them again
after loading. `RealHudAnalyzer` accepts an optional explicit
`scene_reference_profile_path`. Its base fingerprint includes this source binding
before qualification loads. Existing calls without this option retain their
previous base fingerprint calculation. No automatic source-profile discovery is
added.

Changing the profile, review provenance or an image invalidates qualification.
Mutation after initialization is rejected before observation and whenever the
fingerprint is requested. Invalid explicit configuration raises an error rather
than inheriting the HUD-only qualification. Absolute host paths are excluded from
the digest; identical profile-relative assets have identical source fingerprints
after relocation.

This configuration does not install a scene/UI producer, qualify world labels or
convert appearance measurements into trusted evidence. The existing paired-route
missing-producer diagnostic remains applicable. Recognition thresholds, identity,
ownership, sampler and evaluator policies are unchanged. All HUD Python modules
are included in the recognizer code fingerprint, so old code-bound qualification
cannot authorize the new code.

## Independent native delivery evidence

The archived full run contains 4,634 observations and 4,633 consecutive observation
pairs. Converting its six-decimal actual timestamps to the source timebase
1/15360 yields 2,380 pairs at the native 256-tick step and 2,253 pairs (48.63%) with
larger gaps. These are gaps between selected observations, **not evidence of a
content discontinuity**. The complete spacing histogram and source-file digest
are in [the audit](../e2e_reports/match_001/scene_source_binding_audit.json).

Around the R1 transition the archived observations go from 4.086003 to 4.152669.
They omit the previously reviewed native phase disappearance at 4.102669 and
both transient timer frames at 4.119336/4.136003. The existing scene contract
requires previous PTS and pixel identity to match the lifecycle's previous
observation. A proof for the immediately preceding native frame cannot therefore
be attached to a later sampled observation by relabeling its previous PTS/pixels.
Similarly, a native UI transition cannot be moved to a later observation time.

## Contract decision

Keep full sampling behavior intact. The future qualified system lifecycle route
must receive a separately owned native sequence with actual decoder ticks,
source epochs, full-frame pixel identities and independently qualified global
readers. It must preserve the native candidate timestamp, duplicate suppression
and fail-closed discontinuity reset when merging resulting system events into
packages. Sampled player-owned observations retain their existing identity and
ownership requirements. No proof bridge or synthetic observation is introduced
by this change.

## Tests

69 related unit tests pass in 31.04 seconds: source binding, global lifecycle,
HUD replay/trace and reviewed source loaders. Tests include byte/pixel mutation,
missing/escaped assets, changed provenance, relocation, old-report rejection and
the fact that a binding never installs or qualifies a producer.
`ruff check src tests scripts/e2e` passes; mypy passes for 110 source files.
The actual local source profile also loaded and verified at audit completion.
No targeted/sampled/full E2E was launched: there is no qualified adoption candidate.

## Previous / Current / Delta

| Metric | Previous | Current | Delta |
| --- | ---: | ---: | ---: |
| Source assets bound into configured HUD qualification | absent | present | added |
| Installed qualified scene/UI producer | 0 | 0 | 0 |
| Canonical PASS / FAIL / NE | 23 / 55 / 4 | unmeasured | unmeasured |

The cadence audit measures an existing archived run; it is not an E2E improvement
or a new negative-assertion/discontinuity result. All 82 stored assertion entries
remain byte-equivalent under sorted JSON hashing.

## Remaining blocker

Independently qualified source/world continuity and current-frame phase absence
are still missing. Native decoder delivery is a distinct integration requirement;
common source tracking alone is insufficient. Windows execution remains untested;
the relocation test verifies path-independent binding, not Windows/OpenCV runtime.

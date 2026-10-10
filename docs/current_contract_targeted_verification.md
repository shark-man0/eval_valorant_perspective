# Current contract targeted verification and main integration

The standard targeted runner processes the unchanged37-point manifest with the
adopted profile13. This tests current production contracts with that profile;
it does not activate the unqualified global lifecycle development profile.
The runner finishes with exit1 because existing expected numeric values remain
unavailable. All failure records and state counts exactly match the previous
targeted baseline; terminal artifact SHA256 checks pass.

| Metric | Previous | Current | Delta |
| --- | ---: | ---: | ---: |
| Targeted PASS | 12 | 12 | 0 |
| Targeted FAIL | 13 | 13 | 0 |
| Targeted NE | 12 | 12 | 0 |
| Processed frames | 37 | 37 | 0 |
| Live / spectator / menu / unknown | 6 / 6 / 3 / 22 | 6 / 6 / 3 / 22 | 0 |
| Wall seconds | 710.903 | 550.047 | -160.856 (-22.63%) |

Runtime includes different cache conditions; no analyzer speedup is established.
These isolated points cannot evaluate temporal lifecycle, full negative
assertions or discontinuity assertions. The canonical full baseline remains
23PASS/55FAIL/4NE; no new full result or PASS gain is claimed. Full is withheld
because independent lifecycle qualification is still incomplete.

The run starts at commit `e9ecaf8f2f0f0dfa1f9433d40a598ec8909e9ce3`
with the recorded dirty-code fingerprint. The user subsequently authorizes
commit, main integration and push. Updated remote main
`ce70cf3` adds28commits and merges without conflicts. The resulting merge
commit is `0e64aae`; it retains both the native lifecycle contracts and main's
non-video application features. Post-merge related unit tests120PASS in73.31s,
RuffPASS and mypy125source filesPASS. Full pytest is not repeated here.
This merged code is not misrepresented as the code of the earlier targeted run.

Source images, generated profiles, video and OCR binaries remain Pi-local.
Tracked changes include source, tests, schemas, documents, the explicit source
assurance contract, and hash/statistic/provenance diagnosticJSON. Windows native
execution remains unverified.

Private run: `outputs/recognition-investigation/current-contract-targeted-20261010`.
Shared summary: `e2e_reports/match_001/current_contract_targeted_verification.json`.
Next priority remains independently qualifying actual start transitions and
addressing the separate R1 end result-reference/timing blocker.

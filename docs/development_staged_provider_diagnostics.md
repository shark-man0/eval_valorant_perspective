# Staged Map and HUD provider diagnostics

This development addition keeps the existing Map pool, weak current-view
associations, Credits observer, and formal state boundaries. It uses only
previously retained native development observations. It does not read new
staging videos or change the state engine.

## Map candidate ranking

`correspondence_review` accepts optional `ui_rows` from the exact Map native
observation. For every provisional highlight, it reports the score order among
candidates with the same appearance reference. The archived UI score measures
rim shape and color. It is separate from normalized cross-correlation (NCC)
appearance similarity. The diagnostic also reports overlap of each candidate's
appearance footprint with the highlighted footprint. A zero overlap means two
proposal footprints are spatially separate; overlap alone cannot establish
whether they depict one physical marker. Missing UI scores leave the family
unranked. `project_current_map` supplies these rows only when the native Map
sample has exactly one original Map observation.

The UI score was already part of highlight selection. Ranking the 16 existing
highlights first by that score is therefore an internal consistency check, not
independent confirmation that the selected marker belongs to the recorder.
`ownership`, strict recorder marker count, Zone authority, and temporal path
eligibility remain unchanged.

A separate fixed pixel experiment used five exact archived Map control frames.
It measured high-saturation directional support outside the appearance and UI
rim footprint. The existing highlighted candidate ranked first among
same-appearance alternatives in only one of four recorder-self controls; the
nonself UI control had no highlight. The feature was rejected for candidate
selection. All five controls came from one physical match, so this is a
descriptive failure, with no held-out-match accuracy claim.

## Credits contrast experiment

`CreditsCandidateReader.measure_research_inverted` reads the same fixed ROI
with a contrast inversion at threshold 160. It returns a research measurement
with explicit `independent_value_witness=False` and `state_authority=False`.
The ordinary observer still calls only `measure`; it does not consume this
variant. The reader keeps the original numeric format, 0.90 OCR confidence,
and fixed frame geometry. The contrast variant does not calibrate the ROI or
identify the player whose value is displayed.

On the retained 51 images, the ordinary reader returned 11 display candidates.
The contrast variant returned 9; it gained one candidate in an older tuning
match and lost three ordinary candidates. It added none in the five comparison
matches, so it was not adopted as a Credits supplier. The research gain was
visually consistent with the displayed digits, but visual inspection is not
human ground truth or an ownership label.

Existing 51-image HUD measurements retain 4 Armor, 7 current Ammo, 7 reserve
Ammo, and 3 visible inventory weapon labels. Each weapon label retains
`current_weapon_selection=UNKNOWN`. These candidate counts do not imply value
accuracy or recorder ownership. The configured readers for this 51-image set
did not emit an HP measurement; HP remains unavailable in this experiment.

## Reproduction

Run the focused tests from the repository root:

```sh
python -m pytest -q tests/unit/test_map_correspondence_competitors.py tests/unit/test_credits_provider.py
```

The private experiment plan, per-sample observations, physical-match split,
input hashes, and non-adoption decision are kept outside public Git in
`outputs/staged_providers_phase1_PRIVATE` in the task workspace.

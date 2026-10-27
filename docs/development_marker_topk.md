# Development marker retrieval and Top-K views

`development_marker_topk.py` adds a bounded loose-circle/component search.
`development_template_candidates.py` compares native train-template retrieval
and optional unlabeled controls selected with domain SSL features. Both APIs
are opt-in. Existing producers/defaults, Profile thresholds, reference assets,
HUD, Registry and formal Fact/Event contracts are unchanged.

Stages are deliberately separate: current native pixels → broad hypotheses →
features → rank view → independent source/build/geometry/ownership gates.
A rank view does not pass the final gates. It never produces a player-owned
position, Death, trajectory, event or coaching assessment.

## Input and output contract

The caller verifies accepted DEVELOPMENT source admission, physical-match split
and Exposure against independently pinned private ledgers, then loads a native
frame. APIs verify its complete frozen source/SHA/PTS/acquisition epoch/pixel
identity. ROI and Profile fingerprint enter the result. A SHA is not proof of
physical-match independence or a correct Map build. Unknown builds stay unknown.

Parent coordinates and raw geometry form an unchanged prefix. Shape search adds
at most 128 loose Hough windows and 64 chromatic component alternatives, for at
most 320 windows including parents. This is a new low-threshold research search,
not a threshold change to the existing recognizer. Color is not a player label.
Close windows are retained separately and have UNKNOWN physical equivalence.
Overflow/unprocessed counts are explicit; no center averaging or interpolation.

Train retrieval validates human-positive references using the existing supervised
training contract. Unlabeled references use the SSL contract and retain UNKNOWN
semantics. Each bank contains at most 24 hash-bound native 25px patches. Search
uses their central 17px region, three fixed scales and at most two peaks per
reference/scale, with fixed NCC minimum .45. No external download. Constant
spatial templates have no NCC evidence. Reference bytes are verified again after
search. Human and SSL banks are validated jointly for physical/source/frame/pixel
split conflicts; separate bank admission cannot conceal cross-bank leakage. Parent-first output is capped at320;
raw search evidence and overflow remain available. This trial uses the shape
API's validation envelope, whose execution cost is included even though its
extra shape windows belong to a separate comparison.

Ranking checks the complete current pool hash, exact current patch bindings,
feature and classifier fingerprints. Cosine positive-minus-negative support is
an uncalibrated score, not a probability. Rank indices and class UNKNOWN are
retained; there is no implicit acceptance threshold. Feature extraction identity
remains a caller responsibility beyond the supplied fingerprints/binding.
The model/pool bound API cannot authenticate arbitrary caller-supplied features.

## Correct comparison

Keep candidate-set recall separate from Top-1/3/5 recall and selected-output
precision. Top-K here means the first K **windows in one ROI**, with one-to-one
matching, not K oracle windows around each annotation. Nearby alternative
windows can occupy several slots; they are not distinct physical players.
Complete-ROI FP counts include duplicate/unmatched windows. Unmatched windows
must not be automatically called UI/background. Partial annotations support
known-point recall only. UNKNOWN/exclusions retain their previous scope.

The unchanged 2px criterion measures agreement with uncertain manual clicks,
not certified true-center or world-coordinate accuracy. Rank views may lose
old agreements even while the complete pool preserves every original point.
Neither source repetition nor labeled-crop resubstitution is independent
qualification. Domain SSL controls are unlabeled; cluster labels are not GT.

## Actual study outcome

Two candidate mechanisms and rule/local-feature/domain-SSL/pseudo-model rank
ablations were fixed before the known comparison replay. The study reused24
TRAIN,9validation and14previously exposed comparison labels; no new human
review was requested. Private media, centers, aliases, native times, Source IDs,
references, weights and review responses remain outside Git. Terra materials
are local TRAIN/SSL batches; no Terra execution or image transfer is implied.
Sanitized final numbers and exact-head CI are recorded in the Draft PR.

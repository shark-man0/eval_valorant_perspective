# Development view candidate ranking probe

`development_view_reranker.py` exposes two diagnostic methods for weak current-view
observations. Neither changes the common timeline, qualifies ownership, or emits a
Fact/Event.

The first method fits one fixed, class-balanced L2 logistic model to limited
pseudo labels from current UI cues. Its input features contain only signed margins
from two weak view classifiers and their adjacent native observations. HP, owner,
report, spectator, source identity, and absolute recording time are absent from
the feature vector. The caller must validate that adjacent observations belong
to the same source and epoch, have continuity, and lie within two seconds.
Training and comparison are separated by physical match. A pseudo label records
agreement with a restricted UI cue, not human truth. The returned score and
diagnostics have no authority to select a life or camera state.

The second method checks whether a confident numeric HP display repeats in an
adjacent observation under the same caller-validated continuity contract.
Matching values are limited support for a current visual component. A mismatch
may reflect damage or a view change; missing and mismatching values are never
negative life or camera labels.

On nine exposed DEVELOPMENT matches, the pseudo class counts were 10,951 and
3,933. Leave-one-physical-match-out pseudo balanced agreement ranged from
0.992 to 1.000. The pseudo cue and the classifiers share the same recognition
pipeline, so this agreement cannot establish visual accuracy. The learned score
accepted 173 of 176 return-tail candidates at a fixed threshold of 0.5; it did
not distinguish the uncertain tail population. Repeated current HP supported
81 of those 176 candidates. An exact-frame human control audit covered 69 of
83 known attributes; the remaining 14 were not observed at those native frames.
The baseline retained 67 correct, zero incorrect, and two abstentions. No
candidate score was applied to state. The methods remain research diagnostics
until separately reviewed evidence supports a safe improvement.

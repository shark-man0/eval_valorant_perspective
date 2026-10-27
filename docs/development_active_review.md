# Development-only semantic review queues

`development_active_review` proposes at most ten items. It combines uncertainty,
importance flags and diversity caps for hard examples, and draws a separate uniform
random audit sample before hard ranking. The audit inclusion probability and the
original annotation status remain in the receipt. Importance flags are caller-supplied
hypotheses, not verified mistakes or class labels.

Exact patch duplicates and near appearances within a native acquisition/time window
reduce the proposed review queue. They do not merge physical markers, remove
recognition coordinates or propagate a representative's label. Cluster identifiers
are appearance groups with no semantic or ownership meaning. Validation/frozen
observations are rejected; semantic hard examples must be DEVELOPMENT_TRAIN.

Existing human labels can be hidden from the learner in an explicit retrospective
reveal simulation. Such a run is not a new human review or a measurement of saved
human time. A proposed queue, a completed review and an error-rate estimate are
separate outcomes. Audit errors remain unmeasured until actual human responses exist.

## Optional private review UI

`development_active_review_ui` renders five choices: normal PLAYER, death marker,
UI, background and UNKNOWN. A selection is automatically saved by a loopback-only
server; reload restores the saved choice. No center clicks or manual Source/hash
entry are required. A read-only HTML preview disables submission explicitly.

The server accepts only manifest-bound item identifiers, labels and a CSRF token.
It validates host/origin, bounded payloads, native frame provenance and immutable
revision hashes, and writes outside the Git repository. Prediction-blind review
hides teacher predictions, rankings and queue channels. Prediction-exposed correction
is recorded separately. Source acceptance and human review authenticity must still
be verified by the caller when importing responses; metadata hashes alone are not
proof of independent human review. The importer must verify the original dataset
split and Exposure journal as well.

Synthetic UI exercises have a distinct dataset kind and `synthetic_test` origin;
they cannot be imported as HUMAN_CONFIRMED training examples. A saved semantic
label does not validate a candidate center, physical identity, Map accuracy or
recorder ownership. Manual click uncertainty remains UNMEASURED.

These APIs do not change the detector default, Production registry, Fact/Event
contracts or gameplay evaluation. Ownership remains UNKNOWN and formal outputs
remain zero. Private crops, responses, coordinates, Source identifiers and manifests
must not be committed. Safe defaults do not constitute recognition qualification.

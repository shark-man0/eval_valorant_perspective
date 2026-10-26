# Simple development display review

`render_simple_display_review(packet, unanswered_template,
trusted_packet_sha256=anchor)` returns a private local HTML page using the
v2.1 contract. It asks three short questions: Result appearance, separately read
before/after Score values, and Result disappearance. Technical provenance stays
in the source-bound packet; predictions are never shown or prefilled.

The two cases must be bounded acquisitions of one registered DEVELOPMENT source
and episode target. Each needs an all-native-images review view of at most two
seconds, with local file image URIs and continuous native metadata. The renderer
refuses sparse views, gaps, epoch cuts and mixed sources. Keep discontinuous or
unavailable material UNKNOWN using the existing metadata review contract.

Callers use the existing registry, native acquisition, source/frame verification,
exposure and chronology paths. Supply an externally frozen packet hash, preserve
the HTML version and raw submitted response, and validate actual frame bytes
again when importing reviewed points. The renderer only reads repository assets;
it does not admit sources, decode video, save labels or append exposure.

An explicit "new in the later image" answer is a paired-state boundary claim.
"Present in both" and "absent in both" are point reports and cannot establish
an interval negative. Score digits alone do not create a change event: the user
must explicitly affirm the change. Digits accompanying "unknown" remain raw
unconfirmed input. Complete-display timing stays UNKNOWN when not reviewed.

Images must finish decoding before corresponding answers can be recorded.
Stale asynchronous loads cannot enable answers for a different frame. Optional
full review is disabled until every original image in that native view has
decoded, and still needs an explicit human attestation. An interval negative
also needs a separate explicit no-change answer and v2.1 validation. Decode logs
are not proof of human attention or semantic correctness.

An UNKNOWN interval answer remains unknown even when its reviewed endpoints
show a change; those points do not contradict an unknown answer. A YES interval
answer is not evidence of an interval negative and does not create a boundary.
Only an explicit NO can conflict with a change seen in reviewed points. These
diagnostic reasons leave boundary, scope and negative eligibility unchanged.
Keep original responses and previous validation receipts; store any later
revalidation separately with the validator version.

The page remains a development tool. Two endpoint observations can give a wide
boundary interval; they do not supply an exact internal End time or a population
accuracy measure. Separate acquisition epochs must not be fused. Physical
episode grouping is an external review plan, not a count inferred from frames.
No GT writer, production event producer, model, threshold or qualification is
changed. Never publish generated HTML, packets, frames or responses.

Python contract tests and dependency-free Node tests cover the renderer,
source/scope rejection, image-load races, explicit answers and wizard wire
format. Browser rendering and actual human attention remain separate checks.

# Cross-match development timeline review

This consumer compares existing full-recording application bundles. It reuses
`DevelopmentGameTimeline`, the application projection, the original-media
localhost viewer, and the existing candidate-review/evaluation handoff. It does
not create a second state machine, qualify ownership or score research events.

## Input and API

Keep the manifest, bundles, Sources, Profiles, observations, labels and generated
reports outside Git. A manifest has this structure (hashes below are placeholders):

```json
{
  "version": "development_timeline_comparison_manifest_v1",
  "results": [
    {
      "id": "match_a_before",
      "label": "Before",
      "primary": false,
      "bundle": "before/timeline_PRIVATE.json",
      "bundle_sha256": "<complete file SHA256>",
      "policy": "policy_PRIVATE.json",
      "policy_sha256": "<complete policy SHA256>",
      "conditions": {"acquisition": "saved automatic full acquisition"}
    },
    {
      "id": "match_a_after",
      "label": "After",
      "primary": true,
      "bundle": "after/timeline_PRIVATE.json",
      "bundle_sha256": "<complete file SHA256>",
      "policy": "policy_PRIVATE.json",
      "policy_sha256": "<complete policy SHA256>",
      "conditions": {"acquisition": "same native inputs plus advisory sidecar"},
      "compare_to": "match_a_before"
    }
  ]
}
```

Only one result per physical match may be primary. Alternate configurations and
before/after versions do not increase the match or primary-second denominator.
Relative paths resolve against the manifest directory. Bundle receipts, explicit
SHA bindings, existing DEVELOPMENT admission, Source identity and full ordered
second grids are verified. The original recording is hashed again before the
existing media viewer serves it. Catalog generation does not decode media.

`comparison.build_catalog(Path)` returns a compact catalog with per-match and
overall coverage, state counts, UNKNOWN reasons, acquisition/configuration and
observed producer identities, timeline lanes and evidence-linked review intervals.
Different conditions are separate review cohorts. A configuration digest alone
never establishes equal-condition accuracy or independent evaluation.

`comparison.compare_versions(before, after)` requires the same Source and recording
clock. It counts changed one-second estimates and separately compares native
samples with identical Source, rational PTS, pixels and dimensions. Epoch aliases
are not independent confirmations. Without labels, previous-correct losses and
accuracy remain null; changed known estimates are not called lost correct answers.

## CLI, viewer and desktop

```console
python -m valorant_ai_coach.temporal.comparison --manifest /private/comparison.json --output /private/new-report
python -m valorant_ai_coach.temporal.comparison_viewer --manifest /private/comparison.json
```

The first command writes comparison JSON/CSV, the existing per-result evaluation
reviews and a hash receipt. The second prints a tokenized `127.0.0.1` URL. Both
work from the same manifest. The desktop menu **開発用: 試合横断比較** opens this
manifest through the same validated factory. **開発用: 共通タイムライン** opens
one bundle plus its Source policy. Closing/replacing the GUI viewer closes its
servers. GUI tests exercise both routing and the actual catalog factory.

The list exposes domain coverage and UNKNOWN fractions. Whole-recording lanes
show Round, life, camera, HUD, Map and Zone; white ticks mark event candidates.
Gray observed-but-unresolved, dark unobserved and purple conflicting UNKNOWN
remain distinct. Enable alternate results to inspect a different acquisition or
configuration. Filters and paged review suggestions retain native evidence refs.
Select a result/time, then **元動画・native根拠を開く**. A lazy child of the existing
viewer checks the registered original recording and seeks the requested second.
Selecting evidence seeks its rational native PTS relative to recording origin;
the original sample and epoch remain visible. No edited recording is generated.

Review triggers include long UNKNOWN, competing states, long BUY estimates,
uncertain continuation, incomplete lifecycle links, life/camera tension, HUD
available with unresolved states, unassigned Map candidates, and configuration
or observation-density changes. Thresholds select review work, not recognition
truth. A final death hypothesis without a linked return may simply coincide with
the recording ending; it is not a claimed missed resurrection.

## Advisory HUD and location connection

`ValueSupplementObserver` retains parent observations and now transports optional
Ammo-current/reserve and Credits readers alongside Armor and visible inventory
labels. Existing acceptance and geometry gates remain. Missing/unconfigured or
unsupported geometry stays UNKNOWN. Inventory labels do not identify the equipped
weapon. All suppliers declare their fingerprints; the new value contract changes
the value fingerprint without changing parent state authority.

`application export/generate --zone-observations /private/zones.json` accepts the
existing validated HUD-location observations. `zone_projection.attach_viewed_zones`
uses the existing exact-pixel sidecar join, retaining unmatched observations and
all original epochs. Labels remain `unassigned_viewed_actor`, with no geometric
Zone, recorder ownership or movement. State, native frames, events and marker
candidates do not change. Only the shared engine may associate recorder state.

The current-Map projection adds a correspondence review contract, preserving its
v1 transport. It distinguishes unassigned candidate pools, provisional highlights
with weak view support, and current-view association. Every strict recorder count
stays zero until the existing identity/geometry/exclusion requirements are met.
Neither image coordinates nor gaps imply map coordinates or continuous paths.

## Fixed development experiment

Eight exposed physical DEVELOPMENT matches retain 17,693 primary rows. This run
reuses existing acquisitions; it is not eight fresh decodes or unseen evaluation.
The adopted advisory connection preserves every previous state/native/event and
marker field. Seven of 51 frozen images, across five matches, gain Ammo-current
and reserve candidates; prior four Armor and three inventory-label candidates
survive. AI pixel inspection supports those displayed numbers, not human accuracy.
Credits remains geometry-unsupported. Existing location readings add six
candidate-containing seconds across two primary recordings; a separate Map
configuration has six Zone seconds, 140 original Map packets and 16 provisional
highlight samples. These conditions are kept separate.

Actual full-input state experiments were also performed. Blanket demotion of
weak elimination hypotheses removes 4,175 selected DEAD seconds and increases
life UNKNOWN from 4,278 to 8,453. Two explicitly reviewed ALIVE frames change
from incorrect DEAD to abstention, without recovering ALIVE. The nine scoped
camera labels remain seven matches/two abstentions. This is rejected because
it loses specificity broadly, without sufficient recognition improvement.
Adding the existing offline Round-gap marker then increases Round UNKNOWN from
6,015 to 6,065, with 22 ACTIVE and 28 BUY seconds becoming unresolved. That mode
also remains unadopted. Camera UNKNOWN remains 3,495. No shared state rule is
changed by the adopted application connection. Previous wider-acquisition
comparisons remain separate, unadopted experiments.

Open work includes direct current-recorder evidence, stale elimination continuity,
full-match return coverage, Credits geometry, current weapon selection, generic
map-name recognition, geometric Zones and independent accuracy evaluation.
Optional providers can improve these through existing observation interfaces;
none blocks the cross-match review application. See the desktop bridge and
Draft integration audit documents for handoff and review order.

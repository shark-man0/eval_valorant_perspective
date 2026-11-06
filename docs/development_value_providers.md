# Separate Armor and inventory-label providers

`ValueSupplementObserver` appends configured value observations to an existing
pixel observer. It reuses `ProfileHudObserver`, numeric-field OCR, text OCR,
geometry checks, the existing acceptance floor and native supplier transport.
It does not add another state machine or replace the parent's HP/Profile.

The separate private Profile configures the Armor field within the existing
HP/Armor ROI. Only Armor and Weapon measurements are exported by this supplier;
an unread value remains UNKNOWN, never zero. The Weapon reader measures a
visible inventory label. It splits current text-sized lines, reuses configured
OCR and accepts only an exact normalized alias at confidence >=.90. Skin names,
substrings, low-confidence lines and competing distinct labels do not select a
weapon. All attempted lines remain in raw evidence.

Inventory-label recognition does not establish the selected/held weapon. Its
candidate explicitly carries `value_scope="visible_inventory_label"` and
`current_weapon_selection="UNKNOWN"`; application JSON/CSV preserve these and
the viewer displays that selection remains unresolved. Recorder ownership also
stays unresolved, including spectator/remote HUD readings.

## Configuration and API

The trusted local configuration has exactly these fields (all assets stay private):

```json
{
  "parent_observer": "PRIVATE_MODULE:ExistingObserver",
  "parent_config": "/PRIVATE/parent.json",
  "value_reader_config": "/PRIVATE/value-reader.json",
  "inventory_labels": {"EXACT_VISIBLE_ALIAS": "CONFIGURED_WEAPON_LABEL"},
  "tessdata": "/PRIVATE/tessdata"
}
```

`value_reader_config` is the existing common Profile reader configuration, pointing
to a separate Profile and layout with `optional_hud_values=true`. It should
configure Armor independently of the old HP reader. Aliases are a Profile
vocabulary, not Source/time/roster conditions. Public Japanese names used in the
local experiment were checked against the [official arsenal](https://playvalorant.com/ja-jp/arsenal/).
This does not claim exhaustive weapon/locale support.

The supplier receives native BGR pixels only. Its bindings include parent,
Profile/assets, OCR binary/languages, alias/configuration and code fingerprints.
Every emitted producer is declared for native admission; the baseline producers
are all original parent suppliers so acquisition comparisons isolate added values.
The original parent measurement and supplier claims are preserved.

```python
from valorant_ai_coach.temporal.value_provider import ValueSupplementObserver

observer = ValueSupplementObserver(private_config_path)
values_only = observer.inspect_values(native_bgr)
with_parent = observer.inspect(native_bgr)
```

Existing automatic generation can select the composite:

```sh
python -m valorant_ai_coach.temporal.application generate \
  --policy /PRIVATE/policy.json --source-id REGISTERED_SOURCE \
  --reader-config /PRIVATE/value-supplier.json \
  --observer valorant_ai_coach.temporal.value_provider:ValueSupplementObserver \
  --output /PRIVATE/NEW-output
```

Existing exact-native sidecar export remains available with `--hud-values`.
Source/PTS/timebase/pixel hashes and epochs are preserved by the existing
transport, not supplied to the value recognizer. Values have empty state signals
and no Map candidate/ownership authority. Defaults and Production gates are unchanged.

## Measurement and limits

A fixed cohort contains the existing24 HUD frames,22 context centers and5 Map
controls from eight exposed DEVELOPMENT matches. The separate Profile and line
reader produce4 Armor and3 inventory-label candidates across6 records. AI visual
inspection supports those displayed numbers/names; it is not human GT, selected
weapon truth or general accuracy. Other visible values are still missed. The
cohort has been used for development/tuning, not unseen evaluation.

All51 advisory records join existing full application views (eight recordings,
17,693 second rows). Original HP, Round/number/life/camera, Map, events, native
frames and UI visibility are unchanged. This is saved-image analysis/application
replay, not eight new full-video recognition runs. A real CLI export with the
140-packet Map cohort also retains Armor/label candidates and original-video seek.
Two separate automatic60-second smokes start at each source beginning with the
same configuration, no labels/manual initialization, and preserve parent
Round/life/camera values. These are bounded smokes, not full acquisitions.

The first automatic smoke exposed an undeclared-supplier fingerprint error;
the wrapper declaration was corrected and the two-source smoke rerun. Failed
attempts and original native decode logs are preserved privately. No transport
or Source admission gate was weakened.

## Map ownership repair is still incomplete

Four separate private Profile experiments changed calibration masks and the
agent-independent ability-key scaffold, including a rejected foreground-anchor
variant. The reference was a fixed native image from a different exposed
physical match than the Map controls; no role answers were fed to recognition.
Existing .90 geometry/structure and spectator-exclusion gates were retained.
Every variant still fails current strong owner support at the four recorder
controls. None is adopted; experimental foreground code/assets stay private.

The strict Map channel still abstains4/4. Original140 packets, the reviewed
marker objects and separate provisional hypotheses are retained. This PR does
not call the strict loss repaired. Improving current calibration and verified
spectator exclusion remains necessary. No formal Fact/Event, coordinates/Zone
accuracy, path or all-match precision is claimed. Main remains unmerged.

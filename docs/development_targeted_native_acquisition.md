# Targeted DEVELOPMENT native observations

`python -m valorant_ai_coach.temporal.acquire` can retain a short admitted
recording window at an exact cadence from one second down to `1/5` second:

```sh
python -m valorant_ai_coach.temporal.acquire \
  --policy /private/source-policy.json \
  --source-id registered-development-match \
  --start 100 --end 110 --retention-seconds 1/5 \
  --output /private/new-native-window
```

The chosen window, Source and cadence must be fixed before inspecting its new
images. The transport verifies registered DEVELOPMENT admission and the source
byte hash before and after decode, probes every native PTS in the window, checks
the retained exact PTS and image dimensions, and stores native and pixel hashes
with a new acquisition epoch. A window may span at most 180 seconds and at most
300 retained points. The decoder's PNG memory budget remains in force. This is
for representative short intervals around observed Round and recorder-state
changes; repeat selected intervals across physical matches before considering
another full-file acquisition.

The default one-second behavior is unchanged. The cadence is a sampling choice,
not proof of continuous gameplay or a recognition rule. Different cadences
change the observation population; compare state outputs at common native
points and retain changed known values for review. Cached pixel measurements
may be reused only through the existing `CachedPixelObserver` with exact pixel
and recognizer bindings. Native decoding and Source admission still occur.
Acquired PNGs, exact PTS and receipts remain private. The acquisition output is
candidate evidence, not qualified Fact/Event or interval ground truth.

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
300 retained points, counting both endpoints when selected. The decoder's PNG
memory budget remains in force. This is
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

## Fixed five-window check

After the domain-balanced issue review selected targets, five short windows
from five admitted DEVELOPMENT physical matches were fixed before decoding:
one Round candidate window, two life/camera issue windows, and two existing
exact-frame ALIVE control windows. Their durations were 7, 7, 7, 9 and 8
seconds. All used `1/5`-second retention. The windows yielded 195 retained
native points after checking 2,285 decoded native PTS; no full match was
decoded. Every run verified Source bytes before and after, retained native
PTS/pixel identity, dimensions and separate acquisition epochs. The control
labels applied only to their original exact frames, never to all seconds in the
new windows or to recognition input.

The existing exact-pixel cache was exercised with the same 195 retained images:
195 cold measurements and 195 warm hits, with identical measurement payloads.
The five-window process took 98.1 seconds and its recorded Python peak RSS was
162.5 MiB; this excludes child-process peak memory and is not a comparative
speed claim. These results prove acquisition and cache reuse. They do not yet
show a state or accuracy improvement; candidate/state comparisons must keep
the new sampling condition and existing one-second/full-context results
separate.

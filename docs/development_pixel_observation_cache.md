# Private pixel-measurement reuse for matched development acquisition

`temporal.pixel_cache.CachedPixelObserver` wraps a **stateless image-only**
observer. It is optional development infrastructure; acquisition, inference and
Production defaults are unchanged. It is unsuitable for observers whose output
depends on earlier calls, Source identity, time, roster or initialization.

The caller still admits the registered DEVELOPMENT Source, decodes the original
native frames and binds their original pixels/PTS/timebase/epoch. The cache only
avoids repeating pixel recognition for exactly equal BGR arrays. It does not
cache or initialize game states. Labels, audit references and inferred events
are not cache inputs. Duplicate pixels do not establish semantic continuity.

For an existing source-blind observer factory:

```python
from pathlib import Path
from valorant_ai_coach.temporal.match import run_match
from valorant_ai_coach.temporal.pixel_cache import CachedPixelObserver

cache_path = Path("/private/work/pixels.sqlite")

def factory(config_path):
    return CachedPixelObserver(ExistingPixelObserver(config_path), cache_path)

run_match(
    policy_path=Path("/private/work/policy.json"),
    source_id="REGISTERED_SOURCE",
    reader_config=Path("/private/work/reader.json"),
    output=Path("/private/work/new-acquisition"),
    observer_factory=factory,
)
```

Keep the database private, outside Git. Use a single writer per database; create
a new observer instance when its configuration/assets change. Close used cache
instances when the experiment finishes. `stats` reports hits/misses outside the
observations. No hit/miss marker is inserted into pixel measurements or signals.

The namespace binds the complete parent observer fingerprint/bindings and cache
implementation hash. Keys bind array shape, dtype and SHA256 of decoded pixels;
they do not contain a Source ID, timestamp or roster. Equal pixels may be reused
only after the caller's independent Source admission. Measurements are canonical
JSON on both cache misses and hits, matching their on-disk transport. Returned
objects cannot mutate stored results. Stored payload hashes detect corruption;
a mismatch stops acquisition. A changed live parent identity is rejected. This
is an integrity check for a private trusted database, not authentication of an
untrusted external database.

For padding comparisons, fix two conditions before media analysis, keep the
same observer/weights/state engine/cadence/budget and change only padding. Pilot
before whole-match runs. In each condition, decode from the beginning to the end
and select dense windows automatically from that condition's coarse
measurements. Compare exact coarse pixels **and** measurements afterward. Keep
existing exact-frame audit references in the evaluation-only sidecar; never use
them to choose automatic dense windows or seed the operational state series.

Report cache warmth explicitly. A cold baseline followed by a warm wider run
does not measure an isolated speed effect of padding. Record actual execution
times, memory scope, hit/miss counts and observation counts without inventing a
normalized speedup. The cache's mutable end-of-run database hash is a snapshot,
not an immutable prior-condition input. Sealed raw observation archives and
their hashes remain the reproduction evidence.

Separate automatic exact-frame evaluation, practical one-second queries and
audit-assisted exact-frame evaluation. A missing exact native target is
NOT_OBSERVED. A sparse human answer does not label a whole second, an interval,
an internal event time, or training data. More UNKNOWN after dense sampling may
expose previously unobserved subsecond ambiguity; it is not automatically a
semantic regression, just as fewer UNKNOWN rows do not prove improved accuracy.

## Fixed whole-recording padding experiment

After two 60-second pilots, two distinct already-exposed DEVELOPMENT matches
were each decoded from beginning to end under both padding conditions. The
same observer, weights, shared engine, one-second coarse cadence, one-fifth
second dense cadence, balanced selector and 240-second dense budget cap were
fixed before decoding. No per-match initial state, known Round time or roster
was supplied. All 3,135 coarse native pixels and measurements match between
conditions. Both conditions produce full application JSON/CSV and evaluation
handoff, 3,135 one-second rows each. These are four whole acquisitions of two
physical recordings, not four independent matches or unseen evaluation.

| Match | Rows | Round UNKNOWN 1s / 6s | Life UNKNOWN 1s / 6s | Camera UNKNOWN 1s / 6s |
|---|---:|---:|---:|---:|
| A | 1610 | 648 / 639 | 420 / 369 | 320 / 315 |
| B | 1525 | 505 / 500 | 344 / 343 | 281 / 286 |
| Total | 3135 | 1153 / 1139 | 764 / 712 | 601 / 601 |

Fewer UNKNOWN values in the unlabelled regions are candidate-coverage changes,
not newly measured correct predictions. Match B has five more camera UNKNOWN
seconds, so the wider setting is not adopted as the default.
On common native points, 25 previously known Round predictions, 12 life and
16 camera predictions change value. They are unlabelled, including transitions
between known Round values; zero scoped control loss is not a claim that all
these revisions are safe or correct. New DEAD candidates remain unqualified.

Automatic exact-native controls preserve four matching Round points and two
matching life/camera points each. One additional Round and seven life/camera
targets each are NOT_OBSERVED by the automatic path. Evaluation-only audit
frames allow separate exact-frame comparisons: Round 5/5 and life/camera each
9/9 in both conditions, zero previous scoped correct lost. Audit-assisted
matches do not become automatic-native successes or qualification evidence.
Population false events, attribution error and precise boundary error remain
unmeasured; there is no new interval GT or training.

Acquisition wall time / Python peak RSS were A: 953.13s / 591.56 MiB at one-second
padding and 833.45s / 667.13 MiB at six seconds; B: 776.49s / 522.25 MiB and
849.06s / 619.06 MiB. They exclude decoder/OCR child RSS and were run on a shared
host, with cold versus warm caches, so they do not establish a padding speedup.
Actual dense-window duration was A 118s / 221s and B 120s / 221s despite the same
240-second cap. The tradeoff includes more observed input and fewer wider
proposals, not a same-input inference-only comparison.

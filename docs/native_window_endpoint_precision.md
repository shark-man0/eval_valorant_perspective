# Inclusive native windows on integer source PTS

Recovery of PR #54 (`212dee0656e52191f0cbb3947e77f390594862c3`, final research
head `cf4f712ce146ec575720596b157fbf979280eedc`) onto main `f7210cfd`.

FFmpeg's floating-point `t` comparison could drop an exact decimal endpoint
while the Python probe expected that frame. A generated 60fps video with
nonzero PTS origin and timebase 1/15360 reproduces this on current main:
the inclusive 220.8–221.6 window should contain 49 frames, but decoding rejects
its sequence. The open-ended 220.8→EOF case fails for the same reason.
The two near-endpoint controls already pass.

The decoder now converts the supplied decimal start/end to `Fraction(str(...))`,
computes ceil/floor source ticks, and uses those ticks for both expected frames
and FFmpeg selection. It keeps the exact original integer PTS, timebase and
decoder epoch. No epsilon, timestamp snapping, resampling or GT input is added.
Interior probe coverage, at least two frames, strict monotonicity, exact decoded
sequence, encoded/pixel hashes, geometry, terminal source hash, PNG budget and
temporary-file cleanup remain mandatory. Existing EOF/origin behavior remains.

The four real-codec regressions cover exact inclusive endpoints, points just
inside/outside those endpoints, and EOF. On current Mac main, two failed and
two passed before the fix; all four pass after it. Related native/source,
bounded-window, lifecycle transport, ownership and Fact safety tests are run
against the recovery. CI evidence belongs to the new integration HEAD, not to
the original PR's older green commit.

This is source acquisition correctness. Decoder code fingerprints change;
prior recognition qualification must not be re-signed or carried over solely
because these tests pass. It establishes no Self Death/Round End qualification,
canonical improvement, or cross-window continuity. See the
[research phase handoff](research_phase_convergence.md).

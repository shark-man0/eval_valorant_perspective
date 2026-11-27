"""Resumable bit-exact H.264 decode of canonical samples to YUV minimap crops (VM side).

For recordings whose timeline was acquired on another platform: the H.264 decode is
bit-exact everywhere, only the RGB conversion differs. Each batch writes the
yuv420p crop (ROI plus a 16 px margin) of every requested sample; the conversion to
BGR and the check against the timeline's recorded minimap hash happen where the
original conversion ran.
"""
import json
import subprocess
import sys
import time
import zlib
from multiprocessing import Process
from pathlib import Path

import numpy as np

from valorant_ai_coach.temporal.camera_panel import NATIVE_TIME_BASE, native_decode_command
from valorant_ai_coach.temporal.match import _native_audit_batches
from valorant_ai_coach.video.native import decoded_source_ticks
from valorant_ai_coach.video.service import _subprocess_environment

W, H = 1920, 1080
X0, Y0, X1, Y1 = 4, 32, 492, 492  # ROI (20,48,475,475) with a 16 px margin, even-aligned
FS = W * H * 3 // 2

def batches(job):
    by = {}
    for f in job["native_frames"].values():
        s = f["sample"]; by.setdefault(int(s["native_pts_tick"]), []).append(s)
    return [(t, [s for k in t for s in by[k]]) for t in _native_audit_batches(sorted(by), NATIVE_TIME_BASE)]

def crop(frame):
    y = np.frombuffer(frame[:W*H], np.uint8).reshape(H, W)
    u = np.frombuffer(frame[W*H:W*H*5//4], np.uint8).reshape(H//2, W//2)
    v = np.frombuffer(frame[W*H*5//4:], np.uint8).reshape(H//2, W//2)
    return (y[Y0:Y1, X0:X1].tobytes() + u[Y0//2:Y1//2, X0//2:X1//2].tobytes()
            + v[Y0//2:Y1//2, X0//2:X1//2].tobytes())

def run(job_path, video, out, deadline, part, parts):
    job = json.load(open(job_path))
    for n, (ticks, samples) in enumerate(batches(job)):
        marker = out / "yuv" / f"{ticks[0]}.json"
        if n % parts != part or marker.exists():
            continue
        if time.time() > deadline:
            return
        cmd = [str(video) if c == "{video}" else c for c in native_decode_command("ffmpeg", ticks)]
        i = cmd.index("-c:v"); cmd = cmd[:i] + ["-pix_fmt", "yuv420p", "-f", "rawvideo", "pipe:1"]
        r = subprocess.run(cmd, capture_output=True, env=_subprocess_environment())
        if r.returncode:
            raise SystemExit("decode failed")
        got = decoded_source_ticks(r.stderr.decode("utf-8", "replace"), NATIVE_TIME_BASE)
        if len(got) * FS != len(r.stdout):
            raise SystemExit("frame count mismatch")
        rows, blob = [], b""
        want = {int(s["native_pts_tick"]): s for s in samples}
        for k, tick in enumerate(got):
            s = want.pop(tick, None)
            if s is None:
                continue
            data = crop(r.stdout[k*FS:(k+1)*FS])
            rows.append({"sample_sha256": s["sample_sha256"], "native_pts_tick": tick,
                         "offset": len(blob), "size": len(data)})
            blob += data
        rows += [{"sample_sha256": s["sample_sha256"], "native_pts_tick": t, "missing": True}
                 for t, s in want.items()]
        (out / "yuv" / f"{ticks[0]}.zz").write_bytes(zlib.compress(blob, 6))
        marker.write_text(json.dumps(rows))

if __name__ == "__main__":
    job, video, out, budget, parts = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]), float(sys.argv[4]), int(sys.argv[5])
    (out / "yuv").mkdir(parents=True, exist_ok=True)
    deadline = time.time() + budget
    ps = [Process(target=run, args=(job, video, out, deadline, p, parts)) for p in range(parts)]
    [p.start() for p in ps]; [p.join() for p in ps]
    total = len(batches(json.load(open(job))))
    print(json.dumps({"batches_done": len(list((out / "yuv").glob("*.json"))), "batches_total": total}))

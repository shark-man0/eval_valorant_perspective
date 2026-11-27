"""Convert VM YUV minimap crops with this platform's FFmpeg and verify the timeline's ROI hash."""
import hashlib
import io
import json
import subprocess
import sys
import zlib
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, '/home/claude/eval_valorant_perspective/src')
from valorant_ai_coach.temporal.match import png_frames

CW, CH = 488, 460
L, T = 20 - 4, 48 - 32  # ROI offset inside the crop
ROI_W, ROI_H = 455, 427
def convert(blob, n):
    cmd = ['ffmpeg', '-hide_banner', '-loglevel', 'error', '-threads', '1', '-f', 'rawvideo',
           '-pix_fmt', 'yuv420p', '-s', f'{CW}x{CH}', '-color_range', 'tv', '-colorspace', 'bt709',
           '-color_primaries', 'bt709', '-color_trc', 'bt709', '-i', 'pipe:0', '-threads', '1',
           '-c:v', 'png', '-compression_level', '1', '-pred', 'up', '-f', 'image2pipe', 'pipe:1']
    r = subprocess.run(cmd, input=blob, capture_output=True, check=True)
    frames = [cv2.imdecode(np.frombuffer(f, np.uint8), cv2.IMREAD_COLOR) for f in png_frames(io.BytesIO(r.stdout))]
    assert len(frames) == n
    return frames
def main(src, index, out):
    src, out = Path(src), Path(out)
    roi_hash = json.load(open(index))['minimap_roi_pixel_sha256']
    (out / 'done').mkdir(parents=True, exist_ok=True); (out / 'crops').mkdir(exist_ok=True)
    ok = bad = 0
    for meta in sorted(src.glob('*.json')):
        if (out / 'done' / meta.name).exists():
            continue
        rows = json.loads(meta.read_text()); blob = zlib.decompress((src / (meta.stem + '.zz')).read_bytes())
        present = [r for r in rows if not r.get('missing')]
        frames = convert(blob, len(present)) if present else []
        result = []
        for r, img in zip(present, frames):
            roi = np.ascontiguousarray(img[T:T + ROI_H, L:L + ROI_W])
            digest = hashlib.sha256(roi.tobytes()).hexdigest()
            same = digest == roi_hash.get(r['sample_sha256'])
            if same:
                cv2.imwrite(str(out / 'crops' / f"{r['sample_sha256']}.png"), roi, [cv2.IMWRITE_PNG_COMPRESSION, 6])
                ok += 1
            else:
                bad += 1
            result.append({'sample_sha256': r['sample_sha256'], 'native_pts_tick': r['native_pts_tick'],
                           'pixel_identical': same, 'verification': 'timeline_minimap_roi_sha256',
                           'roi_pixel_bounds': [20, 48, 475, 475], 'roi_pixel_sha256': digest})
        result += [{'sample_sha256': r['sample_sha256'], 'native_pts_tick': r['native_pts_tick'], 'pixel_identical': False}
                   for r in rows if r.get('missing')]
        (out / 'done' / meta.name).write_text(json.dumps(result))
    print(json.dumps({'roi_identical': ok, 'roi_different': bad}))
if __name__ == '__main__':
    main(*sys.argv[1:4])

import hashlib
from dataclasses import replace
from fractions import Fraction

import cv2
import numpy as np
import pytest

from scripts.diagnostics.pixel_archive_prototype import KEY_INTERVAL, NativePixelArchive
from valorant_ai_coach.video import VideoProbeError
from valorant_ai_coach.video.native import NativeSourceFrame


def source(tmp_path, index, pixels=None, **changes):
    image = (np.random.default_rng(40+index).integers(0, 256, (24, 32, 3), dtype=np.uint8)
             if pixels is None else pixels)
    path = tmp_path/f'frame_{index}.png'
    assert cv2.imwrite(str(path), image)
    frame = NativeSourceFrame(path, 553+index*256, Fraction(1, 15360), 'epoch', 'a'*64,
                              hashlib.sha256(path.read_bytes()).hexdigest(),
                              hashlib.sha256(image.tobytes()).hexdigest(), 32, 24)
    return replace(frame, **changes), image


def test_exact_sequential_backward_and_key_boundary_reads(tmp_path):
    archive = NativePixelArchive(tmp_path/'cache.bin', max_bytes=100000)
    pixels = []
    for index in range(KEY_INTERVAL+3):
        frame, image = source(tmp_path, index)
        archive.append(frame)
        pixels.append(image)
    frames = archive.seal()
    for index in [*range(len(frames)), 0, 15, 16, 2, 18]:
        assert np.array_equal(frames[index].read_image(), pixels[index])
        assert frames[index].pts_ticks == 553+index*256
        assert frames[index].source_epoch == 'epoch'
    archive.verify()
    archive.close()


def test_cached_return_mutation_does_not_change_source_pixels(tmp_path):
    archive = NativePixelArchive(tmp_path/'cache.bin', max_bytes=100000)
    frame, image = source(tmp_path, 0)
    archive.append(frame)
    cached = archive.seal()[0]
    returned = cached.read_image()
    returned[:] = 0
    assert np.array_equal(cached.read_image(), image)


def test_corrupt_ancestor_is_rejected_even_with_cached_current_pixels(tmp_path):
    archive = NativePixelArchive(tmp_path/'cache.bin', max_bytes=100000)
    for i in range(3):
        archive.append(source(tmp_path, i)[0])
    frames = archive.seal()
    frames[2].read_image()
    with archive.path.open('r+b') as stream:
        value = stream.read(1)
        stream.seek(0)
        stream.write(bytes([value[0] ^ 1]))
    with pytest.raises(VideoProbeError, match='dependency changed'):
        frames[2].read_image()
    with pytest.raises(VideoProbeError, match='terminal bytes'):
        archive.verify()


def test_appended_bytes_rejected_on_read_and_terminal_check(tmp_path):
    archive = NativePixelArchive(tmp_path/'cache.bin', max_bytes=100000)
    archive.append(source(tmp_path, 0)[0])
    frame = archive.seal()[0]
    with archive.path.open('ab') as stream:
        stream.write(b'changed')
    with pytest.raises(VideoProbeError, match='size changed'):
        frame.read_image()
    with pytest.raises(VideoProbeError, match='terminal bytes'):
        archive.verify()


@pytest.mark.parametrize('changes', [{'source_epoch': 'other'}, {'source_video_sha256': 'b'*64},
                                    {'time_base': Fraction(1, 1000)}, {'pts_ticks': 553}])
def test_source_epoch_hash_timebase_order_changes_rejected(tmp_path, changes):
    archive = NativePixelArchive(tmp_path/'cache.bin', max_bytes=100000)
    archive.append(source(tmp_path, 0)[0])
    with pytest.raises(VideoProbeError, match='one ordered source epoch'):
        archive.append(source(tmp_path, 1, **changes)[0])
    with pytest.raises(VideoProbeError, match='successful native archive'):
        archive.seal()
    archive.close()


def test_disk_budget_failure_cannot_seal_partial_output(tmp_path):
    archive = NativePixelArchive(tmp_path/'cache.bin', max_bytes=1)
    with pytest.raises(VideoProbeError, match='budget exceeded'):
        archive.append(source(tmp_path, 0)[0])
    assert archive.path.stat().st_size == 0
    with pytest.raises(VideoProbeError, match='successful native archive'):
        archive.seal()
    archive.close()


def test_frame_metadata_forgery_and_unsealed_reads_rejected(tmp_path):
    archive = NativePixelArchive(tmp_path/'cache.bin', max_bytes=100000)
    archive.append(source(tmp_path, 0)[0])
    with pytest.raises(VideoProbeError, match='not sealed'):
        archive.read_image(0)
    frame = archive.seal()[0]
    with pytest.raises(VideoProbeError, match='binding changed'):
        replace(frame, pts_ticks=999).read_image()
    with pytest.raises(VideoProbeError, match='sealed or failed'):
        archive.append(source(tmp_path, 1)[0])


def test_source_asset_mutation_is_rejected_before_append(tmp_path):
    archive = NativePixelArchive(tmp_path/'cache.bin', max_bytes=100000)
    frame, _ = source(tmp_path, 0)
    frame.path.write_bytes(frame.path.read_bytes()+b'changed')
    with pytest.raises(VideoProbeError, match='asset changed'):
        archive.append(frame)
    archive.close()


def test_identical_frames_compress_as_exact_deltas(tmp_path):
    archive = NativePixelArchive(tmp_path/'cache.bin', max_bytes=100000)
    _, image = source(tmp_path, 0)
    for i in range(3):
        archive.append(source(tmp_path, i, pixels=image)[0])
    frames = archive.seal()
    assert archive.size_bytes < 2*len(image.tobytes())
    assert all(np.array_equal(frame.read_image(), image) for frame in frames)


def test_archive_frames_use_shared_reader_and_global_transport(tmp_path):
    from valorant_ai_coach.hud.models import HudObservationV2
    from valorant_ai_coach.hud.native_system_input import collect_native_system_observations
    from valorant_ai_coach.hud.readers import load_frame

    archive = NativePixelArchive(tmp_path/'cache.bin', max_bytes=100000)
    images = []
    for i in range(3):
        frame, image = source(tmp_path, i)
        archive.append(frame)
        images.append(image)
    frames = archive.seal()
    assert all(np.array_equal(load_frame(f), image)
               for f, image in zip(frames, images, strict=True))

    def observe(source_frames):
        return [HudObservationV2(time_sec=f.time_sec, frame_index=i).to_dict()
                for i, f in enumerate(source_frames)]

    rows = collect_native_system_observations(
        frames, native_step_ticks=256, observe=observe, fingerprint=lambda: 'b'*64,
    )
    assert [r['source_pts_ticks'] for r in rows] == [f.pts_ticks for f in frames]
    assert [r['source_pixel_sha256'] for r in rows] == [f.pixel_sha256 for f in frames]
    assert all(r['system_evidence'] == {} for r in rows)
    assert all(r['system_observation']['values']['player_specific_hud_valid'] is False
               for r in rows)


def test_any_failed_append_poisoning_prevents_truncated_source_output(tmp_path):
    archive = NativePixelArchive(tmp_path/'cache.bin', max_bytes=100000)
    archive.append(source(tmp_path, 0)[0])
    frame, _ = source(tmp_path, 1)
    frame.path.write_bytes(frame.path.read_bytes()+b'changed')
    with pytest.raises(VideoProbeError, match='asset changed'):
        archive.append(frame)
    with pytest.raises(VideoProbeError, match='successful native archive'):
        archive.seal()
    archive.close()

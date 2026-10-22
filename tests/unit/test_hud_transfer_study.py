import cv2
import numpy as np
import pytest

from scripts.diagnostics.diagnose_hud_transfer import freeze_bank, observe
from valorant_ai_coach.hud.layout import HudLayout, NormalizedRoi


def scene():
    image = np.full((240, 480, 3), 50, np.uint8)
    regions = {}
    for name, (x, y) in zip(
        ('round_timer', 'top_match_bar', 'player_hp_armor'),
        ((20, 20), (180, 20), (340, 170)), strict=True,
    ):
        patch = np.full((40, 80, 3), 40, np.uint8)
        cv2.rectangle(patch, (8, 8), (70, 32), (215,) * 3, 2)
        cv2.line(patch, (15, 12), (60, 28), (150,) * 3, 2)
        image[y:y + 40, x:x + 80] = patch
        regions[name] = NormalizedRoi(x / 480, y / 240, 80 / 480, 40 / 240)
    return image, HudLayout('3.0', True, (480, 240), regions, layout_format='v3')


def test_structure_support_and_ncc_rejection_remain_separate(tmp_path):
    image, layout = scene()
    bank, _ = freeze_bank([image.copy() for _ in range(8)], layout, {}, tmp_path)
    result = observe(255 - image, layout, bank)
    assert result['ncc_single']['geometry_consistent'] is False
    assert result['structure_multi']['geometry_consistent'] is True
    assert all(r['classification'] == 'structure_supported_ncc_rejected'
               for r in result['anchors'].values())
    assert result['production_qualified'] is False
    assert result['formal_events'] == []
    assert result['semantic_label'] == 'UNKNOWN'
    assert not (tmp_path / 'hud_layout.templates.json').exists()


def test_reference_selection_never_uses_observed_test_frames_or_mutates_assets(tmp_path):
    image, layout = scene()
    bank, _ = freeze_bank([image.copy() for _ in range(8)], layout, {}, tmp_path)
    frozen = {p.name: p.read_bytes() for p in tmp_path.glob('*.png')}
    before = [(r.template.copy(), r.mask.copy()) for refs in bank.values() for r in refs]
    for frame in [image, np.full_like(image, 70), 255 - image]:
        observe(frame, layout, bank)
    assert frozen == {p.name: p.read_bytes() for p in tmp_path.glob('*.png')}
    assert all(np.array_equal(a, r.template) and np.array_equal(b, r.mask)
               for (a, b), r in zip(before, [r for v in bank.values() for r in v], strict=True))


@pytest.mark.parametrize('kind', ['blank', 'noise', 'half_resolution', 'large_shift'])
def test_invalid_geometry_rejected_without_formal_or_identity_release(tmp_path, kind):
    image, layout = scene()
    bank, _ = freeze_bank([image.copy() for _ in range(8)], layout, {}, tmp_path)
    bad = {'blank': np.full_like(image, 70),
           'noise': np.random.default_rng(4).integers(0, 256, image.shape, dtype=np.uint8),
           'half_resolution': cv2.resize(image, (240, 120)),
           'large_shift': np.roll(image, 96, axis=1)}[kind]
    result = observe(bad, layout, bank)
    assert all(not result[k]['geometry_consistent']
               for k in ('ncc_single', 'ncc_multi', 'structure_multi'))
    assert result['semantic_label'] == 'UNKNOWN'


def test_inconsistent_high_scoring_positions_cannot_bypass_three_inliers(tmp_path):
    image, layout = scene()
    base = {'anchors': {name: {'search_region': [0, 0, 1, 1]} for name in layout.regions}}
    bank, _ = freeze_bank([image.copy() for _ in range(8)], layout, base, tmp_path)
    result = observe(image, layout, bank)
    # All three references see the same duplicated high-score pattern. Picking
    # the same spatial location is not three consistent HUD anchor positions.
    assert not result['structure_multi']['geometry_consistent']
    assert not result['ncc_multi']['geometry_consistent']


def test_flat_training_is_unknown_and_does_not_create_references(tmp_path):
    image, layout = scene()
    bank, stats = freeze_bank([np.full_like(image, 70)] * 8, layout, {}, tmp_path)
    assert not any(bank.values())
    assert all(v['reason'] == 'reference_structure_insufficient' for v in stats.values())
    assert not observe(image, layout, bank)['structure_multi']['geometry_consistent']


def test_multiple_references_cover_contrast_modes_without_relaxing_ncc(tmp_path):
    image, layout = scene()
    training = [image.copy() for _ in range(4)] + [255 - image for _ in range(4)]
    bank, _ = freeze_bank(training, layout, {}, tmp_path)
    assert all(len(refs) == 2 for refs in bank.values())
    results = [observe(frame, layout, bank) for frame in (image, 255 - image)]
    assert all(r['ncc_multi']['geometry_consistent'] for r in results)
    assert sum(r['ncc_single']['geometry_consistent'] for r in results) == 1
    assert all(ref.profile.raw['anchors'][name]['threshold'] == .90
               for name, refs in bank.items() for ref in refs)


def test_fingerprint_detects_frozen_asset_change(tmp_path):
    from scripts.diagnostics.diagnose_hud_transfer import bank_fingerprint
    image, layout = scene()
    bank, _ = freeze_bank([image.copy() for _ in range(8)], layout, {}, tmp_path)
    expected = bank_fingerprint(bank)
    asset = next(tmp_path.glob('*.png'))
    asset.write_bytes(b'corrupt private reference')
    assert bank_fingerprint(bank) != expected


def test_wrong_dtype_or_resolution_cannot_generate_a_reference_bank(tmp_path):
    image, layout = scene()
    for frame in [image.astype(np.float32), image[:, :-1]]:
        with pytest.raises(ValueError, match='reference-resolution'):
            freeze_bank([frame] * 8, layout, {}, tmp_path)
    assert not list(tmp_path.iterdir())

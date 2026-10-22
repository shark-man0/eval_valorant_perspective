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
    result = observe(image, layout, bank, reference_stats=stats)
    assert not result['structure_multi']['geometry_consistent']
    assert all(v['classification'] == 'reference_structure_insufficient'
               for v in result['anchors'].values())


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


def test_persistent_structure_with_no_nonself_ncc_support_is_not_missing_structure(tmp_path):
    image, layout = scene()
    training = []
    for code in range(8):
        frame = image.copy()
        patch = np.empty((40, 80, 3), np.uint8)
        for cell in range(8):
            tile = np.full((20, 20, 3), 40, np.uint8)
            cv2.rectangle(tile, (5, 5), (14, 14), (215,) * 3, 2)
            if (code & cell).bit_count() % 2:
                tile = 255 - tile
            row, col = divmod(cell, 4)
            patch[row * 20:(row + 1) * 20, col * 20:(col + 1) * 20] = tile
        for roi in layout.regions.values():
            x, y, r, b = roi.pixel_bounds(480, 240)
            frame[y:b, x:r] = patch
        training.append(frame)
    bank, stats = freeze_bank(training, layout, {}, tmp_path)
    assert all(not refs for refs in bank.values())
    assert all(v['mask_population'] >= 64 and v['reason'] == 'training_support_missing'
               for v in stats.values())
    result = observe(image, layout, bank, reference_stats=stats)
    assert all(v['classification'] == 'reference_training_support_missing'
               for v in result['anchors'].values())
    assert not result['structure_multi']['geometry_consistent']


def structural_modes():
    image, layout = scene()
    training = []
    for code in range(8):
        patch = np.empty((40, 80, 3), np.uint8)
        for cell in range(8):
            tile = np.full((20, 20, 3), 40, np.uint8)
            cv2.rectangle(tile, (3, 3), (16, 16), (215,) * 3, 1)
            cv2.line(tile, (5, 5), (14, 14), (180,) * 3, 1)
            if (code & cell).bit_count() % 2:
                tile = 255 - tile
            row, col = divmod(cell, 4)
            patch[row * 20:(row + 1) * 20, col * 20:(col + 1) * 20] = tile
        frame = image.copy()
        for roi in layout.regions.values():
            x, y, r, b = roi.pixel_bounds(480, 240)
            frame[y:b, x:r] = patch
        training.append(frame)
    return training, layout


def test_structure_selection_removes_ncc_gate_without_calling_ncc(tmp_path, monkeypatch):
    from scripts.diagnostics import diagnose_hud_transfer as diagnostic
    training, layout = structural_modes()
    legacy, stats = freeze_bank(training, layout, {}, tmp_path)
    assert not any(legacy.values())
    assert all(s['reason'] == 'training_support_missing' for s in stats.values())

    def forbidden(*args, **kwargs):
        raise AssertionError('NCC must never participate in structural selection')

    monkeypatch.setattr(diagnostic, 'raw_scores', forbidden)
    monkeypatch.setattr(diagnostic, 'edge_candidate', forbidden)
    dest = tmp_path / 'structure'
    dest.mkdir()
    bank, stats = freeze_bank(training, layout, {}, dest, selection='structure',
                              training_groups=['a', 'b'] * 4)
    assert all(len(refs) == 1 for refs in bank.values())
    assert all(not s['ncc_used_for_selection'] and s['eligible_candidates'] == 8
               for s in stats.values())
    result = observe(training[1], layout, bank, reference_stats=stats)
    assert result['structure_multi']['geometry_consistent']
    assert not result['ncc_multi']['geometry_consistent']
    assert result['semantic_label'] == 'UNKNOWN'
    assert not result['production_qualified'] and not result['formal_events']


@pytest.mark.parametrize('kind', ['rectangle', 'one_line', 'blank', 'noise'])
def test_structure_selection_rejects_generic_or_absent_reference_features(tmp_path, kind):
    image, layout = scene()
    for roi in layout.regions.values():
        x, y, r, b = roi.pixel_bounds(480, 240)
        patch = np.full((b - y, r - x, 3), 50, np.uint8)
        if kind == 'rectangle':
            cv2.rectangle(patch, (8, 8), (70, 32), (220,) * 3, 1)
        elif kind == 'one_line':
            cv2.line(patch, (4, 20), (75, 20), (220,) * 3, 1)
        image[y:b, x:r] = patch
    training = ([np.random.default_rng(i).integers(0, 256, image.shape, dtype=np.uint8)
                 for i in range(8)] if kind == 'noise' else [image] * 8)
    bank, stats = freeze_bank(training, layout, {}, tmp_path, selection='structure',
                              training_groups=['a', 'b'] * 4)
    assert not any(bank.values())
    assert all(s['reason'] in {'reference_structure_insufficient',
                              'reference_structure_nonspecific'} for s in stats.values())
    assert not observe(image, layout, bank, reference_stats=stats)[
        'structure_multi']['geometry_consistent']


def test_structure_selection_requires_cross_source_support_and_rejects_bad_positions(tmp_path):
    training, layout = structural_modes()
    for groups in [None, ['a'] * 8, ['a', 'b']]:
        with pytest.raises(ValueError, match='training groups'):
            freeze_bank(training, layout, {}, tmp_path, selection='structure',
                        training_groups=groups)
    base = {'anchors': {name: {'search_region': [0, 0, 1, 1]} for name in layout.regions}}
    bank, _ = freeze_bank(training, layout, base, tmp_path, selection='structure',
                          training_groups=['a', 'b'] * 4)
    result = observe(training[0], layout, bank)
    assert not result['structure_multi']['geometry_consistent']
    assert not result['ncc_multi']['geometry_consistent']


def test_structure_selection_is_training_only_frozen_and_write_once(tmp_path):
    from scripts.diagnostics.diagnose_hud_transfer import bank_fingerprint
    training, layout = structural_modes()
    bank, stats = freeze_bank(training, layout, {}, tmp_path, selection='structure',
                              training_groups=['a', 'b'] * 4)
    before = bank_fingerprint(bank)
    for image in [training[0], np.full_like(training[0], 70), 255 - training[0]]:
        observe(image, layout, bank, reference_stats=stats)
    assert bank_fingerprint(bank) == before
    assert all(ref.profile.raw['anchors'][name]['threshold'] == .90
               for name, refs in bank.items() for ref in refs)
    with pytest.raises(FileExistsError):
        freeze_bank(training, layout, {}, tmp_path, selection='structure',
                    training_groups=['a', 'b'] * 4)


def test_structure_support_from_only_one_source_cannot_select_a_reference(tmp_path, monkeypatch):
    from scripts.diagnostics import diagnose_hud_transfer as diagnostic
    modes, layout = structural_modes()
    training = [modes[0]] * 4 + [modes[1]] * 4
    # Each pattern has three non-self supporters, all from its own source.
    monkeypatch.setattr(diagnostic, 'measure', lambda a, b, m: {
        'score': 1. if np.array_equal(a, b) else 0.,
    })
    bank, stats = freeze_bank(training, layout, {}, tmp_path, selection='structure',
                              training_groups=['a'] * 4 + ['b'] * 4)
    assert not any(bank.values())
    assert all(s['reason'] == 'structural_training_support_missing' for s in stats.values())
    result = observe(modes[0], layout, bank, reference_stats=stats)
    assert all(a['classification'] == 'reference_structural_support_missing'
               for a in result['anchors'].values())


def test_structural_selection_cannot_relax_ncc_matching_threshold(tmp_path):
    training, layout = structural_modes()
    base = {'anchors': {name: {'threshold': .89} for name in layout.regions}}
    with pytest.raises(ValueError, match='unchanged NCC threshold'):
        freeze_bank(training, layout, base, tmp_path, selection='structure',
                    training_groups=['a', 'b'] * 4)
    assert not list(tmp_path.iterdir())

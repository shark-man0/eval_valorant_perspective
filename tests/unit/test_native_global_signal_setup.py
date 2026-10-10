"""A zero match count must not hide missing/invalid global reference setup."""
from scripts.diagnostics.probe_native_end_inputs import global_signal_setup
from valorant_ai_coach.hud.templates import HudTemplateProfile


def test_absent_profile_and_omitted_result_signal_are_unconfigured(tmp_path):
    for profile in (None, HudTemplateProfile(tmp_path / 'profile.json',
                                            {'schema_version': '1.0'})):
        setup = global_signal_setup(profile)
        assert setup['round_end_template']['status'] == 'not_configured'
        assert not setup['round_end_template']['semantic_matcher_loaded']


def test_invalid_semantic_assets_are_distinct_from_no_configuration(tmp_path):
    profile = HudTemplateProfile(tmp_path / 'profile.json', {
        'schema_version': '1.0', 'signals': {'round_end_template': {
            'roi': 'round_end_banner', 'matcher': 'semantic_text_ncc_v1',
            'template': 'missing.png', 'mask': 'missing-mask.png',
        }},
    })
    setup = global_signal_setup(profile)['round_end_template']
    assert setup['configured'] and setup['status'] == 'semantic_matcher_unavailable'
    assert setup['diagnostics']


def test_valid_reference_is_loaded_without_claiming_runtime_match_or_qualification(tmp_path):
    from tests.unit.test_semantic_text import _profile
    path, _, _ = _profile(tmp_path, signal='round_end_template', roi='round_end_banner')
    profile = HudTemplateProfile.load(path)
    setup = global_signal_setup(profile)['round_end_template']
    assert setup['configured'] and setup['semantic_matcher_loaded']
    assert setup['status'] == 'loaded'
    assert 'matched' not in setup and 'qualification_created' not in setup

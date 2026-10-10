import hashlib

import pytest

from scripts.diagnostics.validate_native_scene_entrance import verify_files


def test_terminal_file_binding_rejects_mutation(tmp_path):
    source = tmp_path / 'reference.json'
    source.write_bytes(b'original source')
    bindings = {str(source): hashlib.sha256(source.read_bytes()).hexdigest()}
    verify_files(bindings)
    source.write_bytes(b'changed source')
    with pytest.raises(ValueError, match='frozen dependency changed'):
        verify_files(bindings)


def test_terminal_file_binding_rejects_missing_source(tmp_path):
    with pytest.raises(FileNotFoundError):
        verify_files({str(tmp_path / 'missing'): '0'*64})

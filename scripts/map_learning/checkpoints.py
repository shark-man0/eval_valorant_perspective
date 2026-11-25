"""Reuse completed Map stages only when their exact output bytes still match."""

import os
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

from valorant_ai_coach.temporal.replay import file_sha, read_json, write_private


def seal(path, value):
    # An interrupted write must leave either the prior receipt or no receipt.
    with TemporaryDirectory(dir=path.parent) as temporary:
        staged = Path(temporary) / path.name
        write_private(staged, value)
        with staged.open("rb") as handle:
            os.fsync(handle.fileno())
        staged.replace(path)


def pin(path, value):
    if path.exists():
        if read_json(path) != value:
            raise ValueError("Private Map workflow inputs changed")
    else:
        seal(path, value)


def run_stage(root, name, outputs, build, *, replace_directory=None):
    index = root / f"{name}_checkpoint_PRIVATE.json"
    paths = [root / name for name in outputs]
    if index.is_file():
        expected = read_json(index)
        if set(expected) != set(outputs) or any(
            not path.is_file() or file_sha(path) != expected[name]
            for name, path in zip(outputs, paths, strict=True)
        ):
            raise ValueError("A sealed Map checkpoint changed")
        return
    for path in [root / replace_directory] if replace_directory else paths:
        if path.exists() or path.is_symlink():
            path.rename(path.with_name(f"{path.name}.interrupted-{uuid4().hex}"))
    build()
    seal(index, {name: file_sha(path) for name, path in zip(outputs, paths, strict=True)})

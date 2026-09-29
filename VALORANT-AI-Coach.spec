# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

project = Path(SPECPATH)
bin_dir = project / "bin"
optional_binaries = [
    (str(path), "bin")
    for name in ("ffmpeg.exe", "ffprobe.exe")
    if (path := bin_dir / name).is_file()
]

a = Analysis(
    [str(project / "src" / "valorant_ai_coach" / "main.py")],
    pathex=[str(project / "src")],
    binaries=optional_binaries,
    datas=[
        (str(project / "config"), "config"),
        (str(project / "schemas"), "schemas"),
        (str(project / "tests" / "manifest.json"), "tests"),
        (str(project / "tests" / "cases"), "tests/cases"),
    ],
    hiddenimports=["keyring.backends.Windows"],
    hookspath=[],
    runtime_hooks=[],
    excludes=["mypy", "pytest", "_pytest", "ruff"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="VALORANT-AI-Coach",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="VALORANT-AI-Coach",
)


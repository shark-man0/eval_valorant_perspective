# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

project = Path(SPECPATH)
datas = []


def add_file(relative: str, destination: str | None = None) -> None:
    source = project / relative
    if not source.is_file():
        raise FileNotFoundError(f"Required runtime resource is missing: {relative}")
    target = destination if destination is not None else Path(relative).parent.as_posix()
    datas.append((str(source), target if target != "." else "."))


def add_json_tree(relative: str, *, excluded_parts: set[str] | None = None) -> None:
    root = project / relative
    excluded = excluded_parts or set()
    for source in sorted(root.rglob("*.json")):
        rel = source.relative_to(project)
        if any(part in excluded for part in rel.parts):
            continue
        add_file(rel.as_posix())


for relative in (
    "config/ability_slot_contract_v1.json",
    "config/deterministic_rule_engine_v1.json",
    "config/event_source_contract_v1.json",
    "config/hud_layout_1080p_v3.json",
    "config/role_contract_v1.json",
    "config/rule_trigger_registry_v2.json",
    "config/valorant_evaluation_rules_v4.json",
    "config/weapon_visual_registry_contract_v1.json",
):
    add_file(relative)

add_json_tree("schemas")
add_file("config/visual_v2/MANIFEST.json")
add_json_tree("config/visual_v2/config")
add_json_tree("config/visual_v2/schemas")
add_file("config/map_zone_v3/MANIFEST.json")
add_json_tree("config/map_zone_v3/config", excluded_parts={"fixtures"})
add_json_tree("config/map_zone_v3/schemas")
add_file("config/map_zone_v3/assets/summit_minimap_reference.png")

# The packaged application needs exactly one built-in Mock HUD demonstration case.
# Source tests remain outside the artifact; only the runtime input is remapped here.
add_file(
    "tests/cases/TC-029/input.json",
    "runtime/mock_cases/TC-029",
)

a = Analysis(
    [str(project / "src" / "valorant_ai_coach" / "main.py")],
    pathex=[str(project / "src")],
    binaries=[],
    datas=datas,
    hiddenimports=["keyring.backends.Windows", "keyring.backends.fail"],
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
    upx=False,
    console=False,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="VALORANT-AI-Coach",
)

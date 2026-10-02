$ErrorActionPreference = 'Stop'

$video = 'C:\Users\Owner\eval_valorant\eval_valorant_perspective\ValorantData\videos\Valorant_09-25-2026_0-37-29-379.mp4'
$pack  = 'C:\ValorantE2EClean\valorant_e2e_validation_pack_v3'
$python = '.\.venv\Scripts\python.exe'

if (-not (Test-Path $video -PathType Leaf)) { throw "Video not found: $video" }
if (-not (Test-Path $pack -PathType Container)) { throw "Pack not found: $pack" }
if (-not (Test-Path $python -PathType Leaf)) { throw "Python not found: $python" }

git pull
if ($LASTEXITCODE -ne 0) { throw 'git pull failed' }

Write-Host "`n=== HEAD ==="
git rev-parse --short HEAD

# ------------------------------------------------------------
# 1. 有効な既存auto profileを選択
# ------------------------------------------------------------

$env:PROFILE_ROOT = (Resolve-Path '.\outputs\hud_profiles').Path

$baseProfile = @'
import os
from pathlib import Path
from valorant_ai_coach.hud.templates import HudTemplateProfile

root = Path(os.environ["PROFILE_ROOT"])

candidates = sorted(
    [p for p in root.glob("auto_*") if p.is_dir()],
    key=lambda p: p.stat().st_mtime,
    reverse=True,
)

for p in candidates:
    layout = p / "hud_layout.json"
    sidecar = p / "hud_layout.templates.json"

    if not layout.is_file() or not sidecar.is_file():
        continue

    try:
        profile = HudTemplateProfile.load(sidecar)
        profile.fingerprint(layout)
    except Exception:
        continue

    print(str(p))
    raise SystemExit(0)

raise SystemExit("No valid base HUD profile found")
'@ | & $python -

if ($LASTEXITCODE -ne 0 -or -not $baseProfile) {
    throw 'Valid base HUD profile not found'
}

$baseProfile = $baseProfile.Trim()

Write-Host "`n=== BASE PROFILE ==="
Write-Host $baseProfile


# ------------------------------------------------------------
# 2. Geometry-onlyコピー作成
# ------------------------------------------------------------

$geometryBase = Join-Path (Get-Location).Path (
    'outputs\hud_profiles\geometry_only_' +
    [guid]::NewGuid().ToString('N')
)

Copy-Item $baseProfile $geometryBase -Recurse

$geometryLayout = Join-Path $geometryBase 'hud_layout.json'
$geometrySidecar = Join-Path $geometryBase 'hud_layout.templates.json'

$env:GEOMETRY_SIDECAR = $geometrySidecar

@'
import json
import os
from pathlib import Path

path = Path(os.environ["GEOMETRY_SIDECAR"])

data = json.loads(path.read_text(encoding="utf-8"))

signals = data.get("signals")
if isinstance(signals, dict):
    for name in (
        "hp_hud_structure",
        "ability_bar_structure",
        "weapon_ammo_structure",
        "spectated_player_panel",
    ):
        signals.pop(name, None)

data.pop("spectator_panel_detector", None)
data.pop("spectator_clear_reference", None)
data.pop("automatic_identity_generation", None)

path.write_text(
    json.dumps(data, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)

print("GEOMETRY-ONLY SIDECAR CREATED")
'@ | & $python -

if ($LASTEXITCODE -ne 0) {
    throw 'Geometry-only sidecar creation failed'
}


# ------------------------------------------------------------
# 3. Geometry-only profile検証
# ------------------------------------------------------------

$env:HUD_LAYOUT_TEST = $geometryLayout
$env:HUD_SIDECAR_TEST = $geometrySidecar

@'
import os
from pathlib import Path
from valorant_ai_coach.hud.templates import HudTemplateProfile

layout = Path(os.environ["HUD_LAYOUT_TEST"])
sidecar = Path(os.environ["HUD_SIDECAR_TEST"])

p = HudTemplateProfile.load(sidecar)

print("GEOMETRY PROFILE LOAD OK")
print("fingerprint:", p.fingerprint(layout))
print("diagnostics:", p.reader_diagnostics)
print("signals:", sorted(p.raw.get("signals", {}).keys()))
print("spectator detector:", "spectator_panel_detector" in p.raw)
print("old identity generation:", "automatic_identity_generation" in p.raw)
'@ | & $python -

if ($LASTEXITCODE -ne 0) {
    throw 'Geometry profile validation failed'
}


# ------------------------------------------------------------
# 4. Fresh Identity生成
# ------------------------------------------------------------

$out = Join-Path (Get-Location).Path (
    'outputs\hud_profiles\fresh_identity_' +
    [guid]::NewGuid().ToString('N')
)

Write-Host "`n=== GENERATING FRESH IDENTITY ==="
Write-Host $out

& $python `
    -m valorant_ai_coach.hud.calibrate_profile `
    --video $video `
    --layout $geometryLayout `
    --output $out `
    --samples 64

if ($LASTEXITCODE -ne 0) {
    throw 'Fresh HUD profile generation failed'
}

$newLayout = Join-Path $out 'hud_layout.json'
$newSidecar = Join-Path $out 'hud_layout.templates.json'
$newDiagnostics = Join-Path $out 'profile_diagnostics.json'

foreach ($file in @($newLayout, $newSidecar, $newDiagnostics)) {
    if (-not (Test-Path $file -PathType Leaf)) {
        throw "Generated file missing: $file"
    }
}


# ------------------------------------------------------------
# 5. Fresh診断を確認
# ------------------------------------------------------------

$env:NEW_LAYOUT = $newLayout
$env:NEW_SIDECAR = $newSidecar
$env:NEW_DIAGNOSTICS = $newDiagnostics

@'
import json
import os
from pathlib import Path
from valorant_ai_coach.hud.templates import HudTemplateProfile

layout = Path(os.environ["NEW_LAYOUT"])
sidecar = Path(os.environ["NEW_SIDECAR"])
diag_path = Path(os.environ["NEW_DIAGNOSTICS"])

profile = HudTemplateProfile.load(sidecar)
diag = json.loads(diag_path.read_text(encoding="utf-8"))

refs = diag["references"]
weapon = refs["weapon_ammo_structure"]
spectator = refs["spectator_panel"]

print()
print("=== FRESH PROFILE VERIFIED ===")
print("fingerprint:", profile.fingerprint(layout))
print("reader diagnostics:", profile.reader_diagnostics)

for name in ("hp_hud_structure", "ability_bar_structure"):
    print(name, "=", refs[name].get("status"))

print()
print("WEAPON")
for key in (
    "status",
    "candidate_count",
    "structural_rejected",
    "support_rejected",
    "training_accept_count",
    "holdout_accept_count",
):
    print(key, "=", weapon.get(key))

selected = weapon.get("selected_candidate")
if selected:
    if "structural_gates" not in selected:
        raise RuntimeError("Weapon old diagnostics detected")
    print("structural_gates =", selected.get("structural_gates"))
    print("line_count =", selected.get("line_count"))
    print("spatial_edge_spread =", selected.get("spatial_edge_spread"))
    print("edge_occupancy_grid =", selected.get("edge_occupancy_grid"))

print()
print("SPECTATOR")
for key in (
    "status",
    "candidate_count",
    "cluster_count",
    "structural_rejected",
    "support_rejected",
    "training_accept_count",
    "holdout_accept_count",
):
    print(key, "=", spectator.get(key))

if "final_rejection_counts" not in spectator:
    raise RuntimeError("Spectator old diagnostics detected")

print("final_rejection_counts =", spectator.get("final_rejection_counts"))
print()
print("FRESH DIAGNOSTICS CONFIRMED")
'@ | & $python -

if ($LASTEXITCODE -ne 0) {
    throw 'Fresh diagnostics validation failed'
}


# ------------------------------------------------------------
# 6. Full E2E
# ------------------------------------------------------------

Write-Host "`n=== FULL E2E START ==="
Write-Host "HUD PROFILE: $newLayout"

& .\run_e2e_windows.ps1 `
    -Video $video `
    -VideoId match_001 `
    -ValidationPack $pack `
    -HudLayout $newLayout `
    -ManualMapId summit

$code = $LASTEXITCODE

Write-Host "`nFULL E2E EXIT CODE: $code"
Write-Host "PROFILE USED: $out"

exit $code
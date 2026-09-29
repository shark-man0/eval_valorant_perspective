[CmdletBinding()]
param(
    [string] $Video,
    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string] $VideoId,
    [string] $ValidationPack,
    [switch] $Register,
    [string] $HudLayout,
    [string] $VisualProfile,
    [string] $ManualMapId,
    [string] $MapClientBuild,
    [switch] $IncludeEvidence,
    [ValidateRange(1, 10)]
    [int] $EvidenceLimit = 3
)

$ErrorActionPreference = "Stop"

function Stop-Runner([string] $Message, [int] $Code = 1) {
    [Console]::Error.WriteLine($Message)
    exit $Code
}

function Build-E2EArguments {
    param(
        [Parameter(Mandatory = $true)][string] $RunnerPath,
        [string] $Video,
        [Parameter(Mandatory = $true)][ValidateNotNullOrEmpty()][string] $VideoId,
        [string] $ValidationPack,
        [switch] $Register,
        [string] $HudLayout,
        [string] $VisualProfile,
        [string] $ManualMapId,
        [string] $MapClientBuild,
        [switch] $IncludeEvidence,
        [ValidateRange(1, 10)][int] $EvidenceLimit = 3
    )

    $Result = [System.Collections.Generic.List[string]]::new()
    $Result.Add($RunnerPath)
    if ($Video) { $Result.Add("--video"); $Result.Add($Video) }
    $Result.Add("--video-id")
    $Result.Add($VideoId)
    if ($ValidationPack) { $Result.Add("--validation-pack"); $Result.Add($ValidationPack) }
    if ($Register) { $Result.Add("--register") }
    if ($HudLayout) { $Result.Add("--hud-layout"); $Result.Add($HudLayout) }
    if ($VisualProfile) { $Result.Add("--visual-profile"); $Result.Add($VisualProfile) }
    if ($ManualMapId) { $Result.Add("--manual-map-id"); $Result.Add($ManualMapId) }
    if ($MapClientBuild) { $Result.Add("--map-client-build"); $Result.Add($MapClientBuild) }
    if ($IncludeEvidence) { $Result.Add("--include-evidence") }
    $Result.Add("--evidence-limit")
    $Result.Add([string]$EvidenceLimit)
    return ,$Result.ToArray()
}

function Assert-E2ESuccess([int] $ExitCode) {
    if ($ExitCode -ne 0) {
        Stop-Runner "E2E pipeline failed with exit code $ExitCode." $ExitCode
    }
}

if ([System.Environment]::OSVersion.Platform -ne [System.PlatformID]::Win32NT) {
    Stop-Runner "This E2E runner must be executed on Windows."
}

$RepoRoot = $PSScriptRoot
$PythonLauncher = Get-Command py -ErrorAction SilentlyContinue
if (-not $PythonLauncher) {
    Stop-Runner "Python Launcher (py.exe) is required to select Python 3.12."
}

Push-Location $RepoRoot
try {
    & $PythonLauncher.Source -3.12 -c "import sys; raise SystemExit(0 if sys.version_info[:2] == (3, 12) else 1)"
    if ($LASTEXITCODE -ne 0) {
        Stop-Runner "Python 3.12 is required. Install it and ensure 'py -3.12' works."
    }

    $VenvPython = Join-Path $RepoRoot ".venv\Scripts\python.exe"
    if (-not (Test-Path -LiteralPath $VenvPython -PathType Leaf)) {
        & $PythonLauncher.Source -3.12 -m venv (Join-Path $RepoRoot ".venv")
        if ($LASTEXITCODE -ne 0) {
            Stop-Runner "Could not create the project Python 3.12 virtual environment."
        }
    }
    if (-not (Test-Path -LiteralPath $VenvPython -PathType Leaf)) {
        Stop-Runner "The project virtual environment does not contain Python."
    }

    & $VenvPython -c "import sys; raise SystemExit(0 if sys.version_info[:2] == (3, 12) else 1)"
    if ($LASTEXITCODE -ne 0) {
        Stop-Runner "The existing project virtual environment must use Python 3.12."
    }

    # Reinstall only when the declared dependency inputs changed or the environment is broken.
    $ConstraintPath = Join-Path $RepoRoot "constraints-windows.txt"
    $DependencyStamp = Join-Path $RepoRoot ".venv\e2e-dependencies.sha256"
    $DependencyInputs = [System.IO.File]::ReadAllText((Join-Path $RepoRoot "pyproject.toml")) + [System.IO.File]::ReadAllText($ConstraintPath)
    $InputBytes = [System.Text.Encoding]::UTF8.GetBytes($DependencyInputs)
    $Sha256 = [System.Security.Cryptography.SHA256]::Create()
    try { $DependencyHash = [System.BitConverter]::ToString($Sha256.ComputeHash($InputBytes)).Replace("-", "").ToLowerInvariant() }
    finally { $Sha256.Dispose() }
    $NeedDependencyInstall = $true
    if ((Test-Path -LiteralPath $DependencyStamp -PathType Leaf) -and ((Get-Content -LiteralPath $DependencyStamp -Raw).Trim() -eq $DependencyHash)) {
        & $VenvPython -m pip check *> $null
        $NeedDependencyInstall = ($LASTEXITCODE -ne 0)
        if (-not $NeedDependencyInstall) {
            & $VenvPython -c "import PySide6, cv2, jsonschema, openai, shapely, keyring, valorant_ai_coach" *> $null
            $NeedDependencyInstall = ($LASTEXITCODE -ne 0)
        }
    }
    if ($NeedDependencyInstall) {
        & $VenvPython -m pip install -c $ConstraintPath -e $RepoRoot
        if ($LASTEXITCODE -ne 0) {
            Stop-Runner "Could not verify/install the project dependencies."
        }
        [System.IO.File]::WriteAllText($DependencyStamp, $DependencyHash)
    }

    foreach ($ToolName in @("ffmpeg", "ffprobe")) {
        if (-not (Get-Command $ToolName -ErrorAction SilentlyContinue)) {
            Stop-Runner "$ToolName was not found on PATH. Install FFmpeg and add its bin directory to PATH."
        }
    }

    # Explicit paths are checked here; implicit input resolution remains in Python.
    if ($Video) {
        if (-not [System.IO.Path]::IsPathRooted($Video)) {
            Stop-Runner "-Video must be an absolute path when supplied."
        }
        if (-not (Test-Path -LiteralPath $Video -PathType Leaf)) {
            Stop-Runner "The supplied video file does not exist: $Video"
        }
        try {
            $VideoStream = [System.IO.File]::Open($Video, [System.IO.FileMode]::Open, [System.IO.FileAccess]::Read, [System.IO.FileShare]::Read)
            $VideoStream.Dispose()
        }
        catch {
            Stop-Runner "The supplied video file cannot be read."
        }
    }
    $PythonArgArray = Build-E2EArguments `
        -RunnerPath (Join-Path $RepoRoot "scripts\e2e\run_dataset_case.py") `
        -Video $Video -VideoId $VideoId -ValidationPack $ValidationPack `
        -Register:$Register -HudLayout $HudLayout -VisualProfile $VisualProfile `
        -ManualMapId $ManualMapId -MapClientBuild $MapClientBuild `
        -IncludeEvidence:$IncludeEvidence -EvidenceLimit $EvidenceLimit
    & $VenvPython @PythonArgArray
    $RunnerExitCode = $LASTEXITCODE
    Assert-E2ESuccess $RunnerExitCode
}
finally {
    Pop-Location
}

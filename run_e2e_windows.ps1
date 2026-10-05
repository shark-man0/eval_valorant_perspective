[CmdletBinding()]
param(
    [string] $Video,
    [string] $VideoId,
    [string] $ValidationPack,
    [switch] $Register,
    [string] $HudLayout,
    [string] $VisualProfile,
    [string] $ManualMapId,
    [string] $MapClientBuild,
    [switch] $IncludeEvidence,
    [ValidateRange(1, 10)][int] $EvidenceLimit = 3,
    [string] $Output,
    [string] $Manifest,
    [string] $FFmpegBin,
    [string] $FFprobeBin,
    [string] $GitBin,
    [switch] $CheckEnvironment,
    [Parameter(ValueFromRemainingArguments = $true)][string[]] $ExtraArguments
)
$ErrorActionPreference = "Stop"
$PSNativeCommandUseErrorActionPreference = $false

function Stop-Runner([string] $Message, [int] $Code = 2) {
    [Console]::Error.WriteLine($Message)
    exit $Code
}

function Build-E2EArguments {
    param(
        [Parameter(Mandatory = $true)][string] $RunnerPath,
        [string] $Video,
        [string] $VideoId,
        [string] $ValidationPack, [switch] $Register,
        [string] $HudLayout, [string] $VisualProfile,
        [string] $ManualMapId, [string] $MapClientBuild,
        [switch] $IncludeEvidence, [int] $EvidenceLimit = 3,
        [string] $Output, [string] $Manifest,
        [string] $FFmpegBin, [string] $FFprobeBin, [string] $GitBin,
        [switch] $CheckEnvironment, [string[]] $ExtraArguments
    )
    $Result = [System.Collections.Generic.List[string]]::new()
    $Result.Add($RunnerPath)
    if ($Video) { $Result.Add("--video"); $Result.Add($Video) }
    if ($VideoId) { $Result.Add("--video-id"); $Result.Add($VideoId) }
    if ($ValidationPack) { $Result.Add("--validation-pack"); $Result.Add($ValidationPack) }
    if ($Register) { $Result.Add("--register") }
    if ($HudLayout) { $Result.Add("--hud-layout"); $Result.Add($HudLayout) }
    if ($VisualProfile) { $Result.Add("--visual-profile"); $Result.Add($VisualProfile) }
    if ($ManualMapId) { $Result.Add("--manual-map-id"); $Result.Add($ManualMapId) }
    if ($MapClientBuild) { $Result.Add("--map-client-build"); $Result.Add($MapClientBuild) }
    if ($IncludeEvidence) { $Result.Add("--include-evidence") }
    $Result.Add("--evidence-limit"); $Result.Add([string]$EvidenceLimit)
    if ($Output) { $Result.Add("--output"); $Result.Add($Output) }
    if ($Manifest) { $Result.Add("--manifest"); $Result.Add($Manifest) }
    if ($FFmpegBin) { $Result.Add("--ffmpeg-bin"); $Result.Add($FFmpegBin) }
    if ($FFprobeBin) { $Result.Add("--ffprobe-bin"); $Result.Add($FFprobeBin) }
    if ($GitBin) { $Result.Add("--git-bin"); $Result.Add($GitBin) }
    if ($CheckEnvironment) { $Result.Add("--check-environment") }
    foreach ($Argument in $ExtraArguments) { $Result.Add($Argument) }
    return ,$Result.ToArray()
}

function Assert-E2ESuccess([int] $ExitCode) {
    if ($ExitCode -ne 0) { Stop-Runner "E2E pipeline failed with exit code $ExitCode." $ExitCode }
}

$RepoRoot = $PSScriptRoot
$VenvPython = Join-Path $RepoRoot ".venv\Scripts\python.exe"
$PythonPrefix = @()
if (-not (Test-Path -LiteralPath $VenvPython -PathType Leaf)) {
    $Command = Get-Command python -ErrorAction SilentlyContinue
    if (-not $Command) {
        $Command = Get-Command py -ErrorAction SilentlyContinue
        $PythonPrefix = @("-3.12")
    }
    if (-not $Command) { Stop-Runner "Python runtime not found. See WINDOWS_E2E.md setup." }
    $VenvPython = $Command.Source
}
$PythonArgArray = Build-E2EArguments -RunnerPath (Join-Path $RepoRoot "scripts/e2e/run_dataset_case.py") `
    -Video $Video -VideoId $VideoId -ValidationPack $ValidationPack -Register:$Register `
    -HudLayout $HudLayout -VisualProfile $VisualProfile -ManualMapId $ManualMapId `
    -MapClientBuild $MapClientBuild -IncludeEvidence:$IncludeEvidence -EvidenceLimit $EvidenceLimit `
    -Output $Output -Manifest $Manifest -FFmpegBin $FFmpegBin -FFprobeBin $FFprobeBin `
    -GitBin $GitBin -CheckEnvironment:$CheckEnvironment -ExtraArguments $ExtraArguments
Push-Location $RepoRoot
try {
    & $VenvPython @PythonPrefix @PythonArgArray
    $RunnerExitCode = $LASTEXITCODE
}
catch { Stop-Runner "Python runtime could not be started. See WINDOWS_E2E.md setup." }
finally { Pop-Location }
Assert-E2ESuccess $RunnerExitCode
exit $RunnerExitCode

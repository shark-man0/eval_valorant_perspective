param(
    [Parameter(Mandatory = $true)][string] $RunnerPath,
    [switch] $AssertExit
)

$ErrorActionPreference = "Stop"
$Tokens = $null
$ParseErrors = $null
$Ast = [System.Management.Automation.Language.Parser]::ParseFile($RunnerPath, [ref]$Tokens, [ref]$ParseErrors)
if ($ParseErrors.Count -gt 0) { throw "Runner parse failed: $($ParseErrors[0].Message)" }

foreach ($FunctionName in @("Stop-Runner", "Build-E2EArguments", "Assert-E2ESuccess")) {
    $FunctionAst = $Ast.Find({ param($Node) $Node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $Node.Name -eq $FunctionName }, $true)
    if (-not $FunctionAst) { throw "Missing function: $FunctionName" }
    . ([scriptblock]::Create($FunctionAst.Extent.Text))
}

if ($AssertExit) {
    Assert-E2ESuccess 17
    throw "Expected Assert-E2ESuccess to exit with the pipeline code."
}

$Translated = Build-E2EArguments `
    -RunnerPath "C:\repo root\scripts\e2e\run_dataset_case.py" `
    -Video "D:\Valorant Data\match 001.mp4" `
    -VideoId "match_001" `
    -ValidationPack "D:\packs\validation pack" `
    -Register -HudLayout "hud wide" -VisualProfile "visual v2" `
    -ManualMapId "ascent" -MapClientBuild "build 10.05" `
    -IncludeEvidence -EvidenceLimit 7
$Expected = @(
    "C:\repo root\scripts\e2e\run_dataset_case.py",
    "--video", "D:\Valorant Data\match 001.mp4",
    "--video-id", "match_001",
    "--validation-pack", "D:\packs\validation pack",
    "--register",
    "--hud-layout", "hud wide",
    "--visual-profile", "visual v2",
    "--manual-map-id", "ascent",
    "--map-client-build", "build 10.05",
    "--include-evidence",
    "--evidence-limit", "7"
)
$Same = ($Expected.Count -eq $Translated.Count)
if ($Same) {
    for ($Index = 0; $Index -lt $Expected.Count; $Index++) {
        if ($Expected[$Index] -cne $Translated[$Index]) { $Same = $false; break }
    }
}
if (-not $Same) {
    throw "Argument translation did not preserve values and spaces."
}

$Implicit = Build-E2EArguments -RunnerPath "runner.py" -VideoId "from-env"
if (($Implicit -ccontains "--video") -or ($Implicit -ccontains "--validation-pack")) {
    throw "Implicit inputs must remain unresolved in the PowerShell wrapper."
}

if ([System.Environment]::OSVersion.Platform -ne [System.PlatformID]::Win32NT) {
    $PlatformTest = Start-Process -FilePath (Get-Process -Id $PID).Path `
        -ArgumentList @("-NoProfile", "-File", ('"{0}"' -f $RunnerPath), "-VideoId", "platform-check") `
        -Wait -PassThru -NoNewWindow
    if ($PlatformTest.ExitCode -eq 0) {
        throw "The production runner did not reject a non-Windows host."
    }
}

$ExitTest = Start-Process -FilePath (Get-Process -Id $PID).Path `
    -ArgumentList @("-NoProfile", "-File", ('"{0}"' -f $PSCommandPath), "-RunnerPath", ('"{0}"' -f $RunnerPath), "-AssertExit") `
    -Wait -PassThru -NoNewWindow
if ($ExitTest.ExitCode -ne 17) { throw "Expected exit code 17, got $($ExitTest.ExitCode)." }

Write-Output "Windows runner PowerShell behavior tests passed."

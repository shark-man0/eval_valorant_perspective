param(
    [string] $PythonExe = "",
    [string] $IsccPath = "",
    [switch] $SkipDependencyInstall,
    [switch] $SkipReleaseTests
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

if ([System.Environment]::OSVersion.Platform -ne [System.PlatformID]::Win32NT) {
    throw "Windows 10/11 x64で実行してください。"
}

$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
Push-Location $Root

function Invoke-Checked {
    param(
        [Parameter(Mandatory = $true)][string] $FilePath,
        [Parameter()][string[]] $Arguments = @()
    )
    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed ($LASTEXITCODE): $FilePath $($Arguments -join ' ')"
    }
}

function Resolve-Python {
    param([string] $Requested)
    if (-not [string]::IsNullOrWhiteSpace($Requested)) {
        $command = Get-Command $Requested -ErrorAction Stop
        return $command.Source
    }
    $venv = Join-Path $Root ".venv\Scripts\python.exe"
    if (-not (Test-Path $venv)) {
        & py -3.12 -m venv (Join-Path $Root ".venv")
        if ($LASTEXITCODE -ne 0) {
            throw "Python 3.12 virtual environment could not be created."
        }
    }
    return (Resolve-Path $venv).Path
}

function Resolve-Iscc {
    param([string] $Requested)
    if (-not [string]::IsNullOrWhiteSpace($Requested)) {
        return (Resolve-Path $Requested).Path
    }
    $command = Get-Command "ISCC.exe" -ErrorAction SilentlyContinue
    if ($null -ne $command) {
        return $command.Source
    }
    $programFilesX86 = [Environment]::GetEnvironmentVariable("ProgramFiles(x86)")
    $candidates = @(
        (Join-Path $env:ProgramFiles "Inno Setup 7\ISCC.exe"),
        (Join-Path $programFilesX86 "Inno Setup 7\ISCC.exe"),
        (Join-Path $env:ProgramFiles "Inno Setup 6\ISCC.exe"),
        (Join-Path $programFilesX86 "Inno Setup 6\ISCC.exe")
    )
    foreach ($candidate in $candidates) {
        if (Test-Path $candidate) {
            return (Resolve-Path $candidate).Path
        }
    }
    throw "Inno Setup ISCC.exe was not found. Install Inno Setup 6.3+ or 7.x."
}

function Invoke-PackagedSmoke {
    param(
        [Parameter(Mandatory = $true)][string] $Executable,
        [Parameter(Mandatory = $true)][string] $LocalAppDataRoot,
        [switch] $PreserveExistingData
    )
    if (-not $PreserveExistingData) {
        Remove-Item -Recurse -Force $LocalAppDataRoot -ErrorAction SilentlyContinue
    }
    New-Item -ItemType Directory -Force -Path $LocalAppDataRoot | Out-Null

    $previousLocalAppData = $env:LOCALAPPDATA
    $previousQtPlatform = $env:QT_QPA_PLATFORM
    try {
        $env:LOCALAPPDATA = $LocalAppDataRoot
        $env:QT_QPA_PLATFORM = "offscreen"
        $process = Start-Process -FilePath $Executable -ArgumentList "--smoke-test" -Wait -PassThru
        if ($process.ExitCode -ne 0) {
            $log = Join-Path $LocalAppDataRoot "ValorantAICoach\logs\valorant-ai-coach.log"
            if (Test-Path $log) {
                Write-Host "----- packaged smoke log -----"
                Get-Content -Raw -Encoding UTF8 $log
                Write-Host "----- end packaged smoke log -----"
            }
            throw "Packaged smoke test failed with exit code $($process.ExitCode)."
        }
        $data = Join-Path $LocalAppDataRoot "ValorantAICoach"
        if (-not (Test-Path (Join-Path $data "app.db"))) {
            throw "Packaged smoke test did not initialize SQLite in the user data directory."
        }
        if (-not (Test-Path (Join-Path $data "logs\valorant-ai-coach.log"))) {
            throw "Packaged smoke test did not initialize the user log directory."
        }
    }
    finally {
        $env:LOCALAPPDATA = $previousLocalAppData
        $env:QT_QPA_PLATFORM = $previousQtPlatform
    }
}

function Assert-DistributionContents {
    param([Parameter(Mandatory = $true)][string] $Path)
    $rootPath = (Resolve-Path $Path).Path
    foreach ($item in Get-ChildItem -LiteralPath $rootPath -Recurse -Force) {
        $relative = [IO.Path]::GetRelativePath($rootPath, $item.FullName).Replace("\", "/")
        if (
            $relative -match "(^|/)(tests|\.git|outputs|e2e_reports|ValorantData)(/|$)" -or
            $relative -match "(^|/)\.env($|\.)" -or
            $relative -match "\.(mp4|mkv|mov|avi|webm|sqlite|sqlite3|db|db-wal|db-shm|log|key)$"
        ) {
            throw "Forbidden release content detected: $relative"
        }
    }
}

function Invoke-Installer {
    param(
        [Parameter(Mandatory = $true)][string] $Installer,
        [Parameter(Mandatory = $true)][string] $InstallDir,
        [Parameter(Mandatory = $true)][string] $LogPath
    )
    $arguments = "/VERYSILENT /SUPPRESSMSGBOXES /NORESTART /DIR=`"$InstallDir`" /LOG=`"$LogPath`""
    $process = Start-Process -FilePath $Installer -ArgumentList $arguments -Wait -PassThru
    if ($process.ExitCode -ne 0) {
        if (Test-Path $LogPath) {
            Get-Content -Raw -Encoding UTF8 $LogPath
        }
        throw "Installer failed with exit code $($process.ExitCode)."
    }
}

try {
    $PythonExe = Resolve-Python $PythonExe
    $Version = (& $PythonExe scripts\release\release_tools.py version).Trim()
    if ($LASTEXITCODE -ne 0) {
        throw "Could not read application version."
    }
    $Names = (& $PythonExe scripts\release\release_tools.py names --json | ConvertFrom-Json)
    if ($LASTEXITCODE -ne 0) {
        throw "Could not calculate release artifact names."
    }

    if ($env:GITHUB_REF_TYPE -eq "tag") {
        Invoke-Checked $PythonExe @(
            "scripts\release\release_tools.py",
            "validate-tag",
            "--tag",
            $env:GITHUB_REF_NAME
        )
    }

    if (-not $SkipDependencyInstall) {
        Invoke-Checked $PythonExe @("-m", "pip", "install", "--upgrade", "pip")
        Invoke-Checked $PythonExe @(
            "-m", "pip", "install", "-c", "constraints-windows.txt", "-e", ".[gui,dev,build]"
        )
    }
    if (-not $SkipReleaseTests) {
        Invoke-Checked $PythonExe @(
            "-m", "pytest", "tests\unit\test_release_engineering.py", "-q"
        )
        Invoke-Checked $PythonExe @(
            "-m", "ruff", "check",
            "scripts\release\release_tools.py",
            "tests\unit\test_release_engineering.py"
        )
    }

    Invoke-Checked $PythonExe @(
        "-m", "PyInstaller", "--noconfirm", "--clean", "VALORANT-AI-Coach.spec"
    )

    $DistDir = Join-Path $Root "dist\VALORANT-AI-Coach"
    $DistExe = Join-Path $DistDir "VALORANT-AI-Coach.exe"
    if (-not (Test-Path $DistExe)) {
        throw "PyInstaller output is missing: $DistExe"
    }
    Copy-Item -Force (Join-Path $Root "docs\windows_distribution.md") (Join-Path $DistDir "README-Windows.md")
    Assert-DistributionContents $DistDir
    Invoke-PackagedSmoke $DistExe (Join-Path $Root "work\pyinstaller-smoke\localappdata")

    $ReleaseDir = Join-Path $Root "release"
    $StageDir = Join-Path $Root "work\release-stage"
    Remove-Item -Recurse -Force $ReleaseDir -ErrorAction SilentlyContinue
    Remove-Item -Recurse -Force $StageDir -ErrorAction SilentlyContinue
    New-Item -ItemType Directory -Force -Path $ReleaseDir, $StageDir | Out-Null

    $PortableRoot = Join-Path $StageDir $Names.portable_root
    New-Item -ItemType Directory -Force -Path $PortableRoot | Out-Null
    Copy-Item -Recurse -Force (Join-Path $DistDir "*") $PortableRoot
    Assert-DistributionContents $PortableRoot

    $PortableZip = Join-Path $ReleaseDir $Names.portable_zip
    Compress-Archive -Path $PortableRoot -DestinationPath $PortableZip -CompressionLevel Optimal

    $PortableSmokeDir = Join-Path $Root "work\portable-smoke"
    Remove-Item -Recurse -Force $PortableSmokeDir -ErrorAction SilentlyContinue
    Expand-Archive -Path $PortableZip -DestinationPath $PortableSmokeDir -Force
    $PortableExe = Join-Path $PortableSmokeDir "$($Names.portable_root)\VALORANT-AI-Coach.exe"
    Invoke-PackagedSmoke $PortableExe (Join-Path $Root "work\portable-smoke-data")

    $IsccPath = Resolve-Iscc $IsccPath
    Invoke-Checked $IsccPath @(
        "/DMyAppVersion=$Version",
        "/DSourceDir=$DistDir",
        "/DOutputDir=$ReleaseDir",
        "installer\VALORANT-AI-Coach.iss"
    )
    $Installer = Join-Path $ReleaseDir $Names.installer
    if (-not (Test-Path $Installer)) {
        throw "Expected installer was not created: $Installer"
    }

    $InstallerSmoke = Join-Path $Root "work\installer-smoke"
    $InstallDir = Join-Path $InstallerSmoke "app"
    $InstallerData = Join-Path $InstallerSmoke "localappdata"
    Remove-Item -Recurse -Force $InstallerSmoke -ErrorAction SilentlyContinue
    New-Item -ItemType Directory -Force -Path $InstallerSmoke, $InstallerData | Out-Null

    Invoke-Installer $Installer $InstallDir (Join-Path $InstallerSmoke "install-1.log")
    $InstalledExe = Join-Path $InstallDir "VALORANT-AI-Coach.exe"
    if (-not (Test-Path $InstalledExe)) {
        throw "Installer did not place the application executable."
    }
    Invoke-PackagedSmoke $InstalledExe $InstallerData

    $UserData = Join-Path $InstallerData "ValorantAICoach"
    $Sentinel = Join-Path $UserData "preserve-on-upgrade-and-uninstall.txt"
    "release-engineering-sentinel" | Set-Content -Encoding UTF8 $Sentinel

    Invoke-Installer $Installer $InstallDir (Join-Path $InstallerSmoke "install-2-upgrade.log")
    if (-not (Test-Path $Sentinel) -or -not (Test-Path (Join-Path $UserData "app.db"))) {
        throw "Reinstall/upgrade simulation modified user data."
    }
    Invoke-PackagedSmoke $InstalledExe $InstallerData -PreserveExistingData

    $Uninstaller = Get-ChildItem -LiteralPath $InstallDir -Filter "unins*.exe" |
        Select-Object -First 1
    if ($null -eq $Uninstaller) {
        throw "Inno Setup uninstaller was not created."
    }
    $uninstallProcess = Start-Process -FilePath $Uninstaller.FullName -ArgumentList (
        "/VERYSILENT /SUPPRESSMSGBOXES /NORESTART"
    ) -Wait -PassThru
    if ($uninstallProcess.ExitCode -ne 0) {
        throw "Uninstaller failed with exit code $($uninstallProcess.ExitCode)."
    }
    if (Test-Path $InstalledExe) {
        throw "Uninstaller left the installed application executable behind."
    }
    if (-not (Test-Path $Sentinel) -or -not (Test-Path (Join-Path $UserData "app.db"))) {
        throw "Uninstaller removed user data."
    }

    $Dependencies = Join-Path $ReleaseDir "DEPENDENCIES.txt"
    $dependencyLines = & $PythonExe -m pip list --format=freeze
    if ($LASTEXITCODE -ne 0) {
        throw "Could not record the resolved dependency set."
    }
    $dependencyLines | Sort-Object | Set-Content -Encoding UTF8 $Dependencies

    $Commit = (& git rev-parse HEAD).Trim()
    if ($LASTEXITCODE -ne 0) {
        throw "Could not determine the release commit."
    }
    $PythonVersion = (& $PythonExe --version 2>&1 | Out-String).Trim()
    Invoke-Checked $PythonExe @(
        "scripts\release\release_tools.py",
        "build-info",
        "--output", (Join-Path $ReleaseDir "BUILD-INFO.json"),
        "--commit", $Commit,
        "--python", $PythonVersion,
        "--dependencies", $Dependencies,
        "--build-command", ".\scripts\release\build_release.ps1"
    )

    Copy-Item -Force ".github\RELEASE_NOTES_TEMPLATE.md" (
        Join-Path $ReleaseDir "RELEASE_NOTES_TEMPLATE.md"
    )
    Invoke-Checked $PythonExe @(
        "scripts\release\release_tools.py",
        "checksums",
        "--output", (Join-Path $ReleaseDir "SHA256SUMS.txt"),
        $PortableZip,
        $Installer
    )

    Write-Host "Windows release artifacts:"
    Get-ChildItem -LiteralPath $ReleaseDir | Select-Object Name, Length
}
finally {
    Pop-Location
}

$ErrorActionPreference = "Stop"

if ([System.Environment]::OSVersion.Platform -ne [System.PlatformID]::Win32NT) {
    throw "このスクリプトはWindows 10/11で実行してください。"
}

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    & py -3.12 -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw "Python 3.12仮想環境を作成できませんでした。" }
}

$PythonExe = ".venv\Scripts\python.exe"
function Invoke-ProjectPython {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]] $PythonArgs)
    & $PythonExe @PythonArgs
    if ($LASTEXITCODE -ne 0) {
        throw "Pythonコマンドが失敗しました: $($PythonArgs -join ' ')"
    }
}

Invoke-ProjectPython -m pip install --upgrade pip
Invoke-ProjectPython -m pip install -c constraints-windows.txt -e ".[gui,dev,build]"
Invoke-ProjectPython tests\validate_dataset.py
Invoke-ProjectPython -m pytest --cov=valorant_ai_coach --cov-report=term-missing --cov-fail-under=75
Invoke-ProjectPython -m ruff check src tests\unit tests\integration
Invoke-ProjectPython -m mypy src\valorant_ai_coach
Invoke-ProjectPython -m PyInstaller --noconfirm --clean VALORANT-AI-Coach.spec

$PreviousQtPlatform = $env:QT_QPA_PLATFORM
try {
    $env:QT_QPA_PLATFORM = "offscreen"
    & "dist\VALORANT-AI-Coach\VALORANT-AI-Coach.exe" --smoke-test
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller成果物の起動確認に失敗しました。" }
}
finally {
    $env:QT_QPA_PLATFORM = $PreviousQtPlatform
}

Write-Host "Built: dist\VALORANT-AI-Coach\VALORANT-AI-Coach.exe"

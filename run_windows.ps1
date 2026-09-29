$ErrorActionPreference = "Stop"

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    & py -3.12 -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw "Python 3.12仮想環境を作成できませんでした。" }
}

& .venv\Scripts\python.exe -m pip install -c constraints-windows.txt -e "."
if ($LASTEXITCODE -ne 0) { throw "依存関係をインストールできませんでした。" }
& .venv\Scripts\python.exe -m valorant_ai_coach.main
if ($LASTEXITCODE -ne 0) { throw "VALORANT AI Coachが異常終了しました。" }

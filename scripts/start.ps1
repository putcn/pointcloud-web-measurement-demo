$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$Python = if ($env:PYTHON) { $env:PYTHON } else { 'python' }
if (-not (Get-Command $Python -ErrorAction SilentlyContinue)) {
    throw 'Python 3.11+ is required. Set $env:PYTHON to a Python executable if needed.'
}

if (-not (Test-Path '.venv')) {
    & $Python -m venv .venv
}

& .\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
$Port = if ($env:PORT) { $env:PORT } else { '8000' }
uvicorn server:app --host 0.0.0.0 --port $Port --reload

# Sobe o ambiente e abre o painel.
# Uso:  .\run.ps1
#       .\run.ps1 -Reinstalar

param([switch]$Reinstalar)

$ErrorActionPreference = "Stop"
$venv = ".venv-app"
$python = "$venv\Scripts\python.exe"

if ($Reinstalar -and (Test-Path $venv)) {
    Write-Host "Removendo ambiente antigo..." -ForegroundColor Yellow
    Remove-Item -Recurse -Force $venv
}

if (-not (Test-Path $python)) {
    Write-Host "Criando ambiente virtual em $venv..." -ForegroundColor Cyan
    python -m venv $venv
    & $python -m pip install --upgrade pip
    & $python -m pip install -r requirements.txt
}

Write-Host "`nVerificando o ambiente..." -ForegroundColor Cyan
& $python scripts/verificar.py

Write-Host "`nAbrindo o painel em http://localhost:8501" -ForegroundColor Green
& $python -m streamlit run app/main.py

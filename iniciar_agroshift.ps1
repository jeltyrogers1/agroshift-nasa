$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "=== Verificando dependencias de AgroShift ===" -ForegroundColor Cyan
python -c "import fastapi, uvicorn" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Instalando dependencias desde requirements.txt..." -ForegroundColor Yellow
    python -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) { Write-Error "Error instalando dependencias."; exit 1 }
}

Write-Host "Iniciando AgroShift en http://localhost:8000 (red local: http://IP-DE-TU-LAPTOP:8000)" -ForegroundColor Green
python -m uvicorn server:app --host 0.0.0.0 --port 8000

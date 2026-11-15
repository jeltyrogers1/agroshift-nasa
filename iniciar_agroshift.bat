@echo off
cd /d "%~dp0"
echo === Verificando dependencias de AgroShift ===
python -c "import fastapi, uvicorn" >nul 2>&1
if errorlevel 1 (
    echo Instalando dependencias desde requirements.txt...
    python -m pip install -r requirements.txt
    if errorlevel 1 (
        echo Error instalando dependencias.
        pause
        exit /b 1
    )
)
echo Iniciando AgroShift en http://localhost:8000 (red local: http://IP-DE-TU-LAPTOP:8000)
python -m uvicorn server:app --host 0.0.0.0 --port 8000

@echo off
echo ========================================================
echo Creando entorno virtual (venv) para VoIP Backend...
echo ========================================================
python -m venv venv
if %errorlevel% neq 0 (
    echo Error al crear el entorno virtual. Asegurate de tener Python instalado y en tu PATH.
    pause
    exit /b %errorlevel%
)

echo Activando entorno virtual e instalando dependencias...
call venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt

echo ========================================================
echo Entorno virtual configurado exitosamente.
echo.
echo Para activarlo manualmente en tu terminal CMD usa:
echo     venv\Scripts\activate
echo.
echo Para ejecutar el servidor localmente usa:
echo     uvicorn main:app --reload
echo ========================================================
pause

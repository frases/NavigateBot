@echo off
setlocal

cd /d "%~dp0"

if exist ".venv\Scripts\activate.bat" (
    call ".venv\Scripts\activate.bat"
)

if exist "main.py" (
    python main.py
    goto :end
)

if exist "navigatebot.py" (
    python navigatebot.py
    goto :end
)

echo Nenhum arquivo de inicializacao encontrado.
echo Esperado: main.py ou navigatebot.py
pause

:end
endlocal

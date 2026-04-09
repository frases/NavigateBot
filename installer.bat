@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title navigatebot installer

echo ======================================
echo        navigatebot - installer
 echo ======================================
echo.

where py >nul 2>&1
if %errorlevel%==0 (
    set "PY=py -3"
) else (
    set "PY=python"
)

%PY% --version >nul 2>&1
if errorlevel 1 (
    echo Python 3 nao foi encontrado no sistema.
    echo Instale o Python 3.11+ e marque a opcao de adicionar ao PATH.
    echo.
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo Criando ambiente virtual...
    %PY% -m venv .venv
    if errorlevel 1 (
        echo Nao foi possivel criar o ambiente virtual.
        echo.
        pause
        exit /b 1
    )
)

call ".venv\Scripts\activate.bat"
if errorlevel 1 (
    echo Nao foi possivel ativar o ambiente virtual.
    echo.
    pause
    exit /b 1
)

echo Atualizando pip...
python -m pip install --upgrade pip setuptools wheel
if errorlevel 1 (
    echo Falha ao atualizar o pip.
    echo.
    pause
    exit /b 1
)

if exist "requirements.txt" (
    echo Instalando dependencias pelo requirements.txt...
    pip install -r requirements.txt
) else (
    echo Instalando dependencias base do projeto...
    pip install discord.py python-dotenv aiohttp
)

if errorlevel 1 (
    echo.
    echo Ocorreu um erro durante a instalacao.
    pause
    exit /b 1
)

if not exist ".env" if exist ".env.example" (
    copy /y ".env.example" ".env" >nul
    echo .env criado a partir do .env.example
)

echo.
echo Instalacao concluida.
echo Para iniciar o bot, use:
echo .venv\Scripts\activate
echo python main.py
echo.
pause
endlocal

@echo off
chcp 65001 >nul
title Instalar a IA local do JARVIS
cd /d "%~dp0"

echo ==========================================================
echo   INSTALAR A IA LOCAL DO JARVIS (funciona sem internet)
echo ==========================================================
echo.
echo   1 = leve    (Llama 3.2 1B, ~0,8 GB) - mais rapido
echo   2 = esperto (Llama 3.2 3B, ~2 GB)   - mais inteligente (recomendado)
echo.
set /p ESCOLHA=Digite 1 ou 2 e aperte ENTER: 
set MODELO=esperto
if "%ESCOLHA%"=="1" set MODELO=leve

REM Mesmo jeito de achar o Python do iniciar.bat
set PY=
if exist "%LOCALAPPDATA%\Programs\Python\Python314\python.exe" set PY="%LOCALAPPDATA%\Programs\Python\Python314\python.exe"
if not defined PY (
    where py >nul 2>nul
    if not errorlevel 1 set PY=py -3
)
if not defined PY (
    where python >nul 2>nul
    if not errorlevel 1 set PY=python
)
if not defined PY (
    echo Python nao encontrado!
    pause
    exit /b 1
)

echo.
echo Baixando e instalando (%MODELO%). Pode demorar varios minutos, deixe a janela aberta...
echo.
%PY% -X utf8 -m core.ia_local %MODELO%
echo.
pause

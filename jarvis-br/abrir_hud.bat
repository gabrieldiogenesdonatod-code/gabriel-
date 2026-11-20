@echo off
title J.A.R.V.I.S BR 3.9.1 - HUD 3.9
REM Abre so o HUD 3.9 (o painel animado), sem abrir o assistente.
REM Para o HUD com voz e comandos, abra o JARVIS pelo iniciar.bat: o HUD ja aparece na tela principal.
cd /d "%~dp0"

REM Mesmo Python do iniciar.bat: 1) o 3.14 do seu usuario, 2) o lancador "py", 3) o "python" do PATH.
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
    echo Python nao encontrado! Instale o Python e marque "Add Python to PATH".
    pause
    exit /b 1
)

if not exist "hud39\static\hud.jpg" (
    echo ERRO: falta a pasta hud39. Extraia o ZIP completo do J.A.R.V.I.S BR de novo.
    pause
    exit /b 1
)

echo =================================
echo    HUD 3.9 - J.A.R.V.I.S BR
echo =================================
echo O HUD abre numa janela em tela cheia (Esc fecha os paineis, F sai da tela cheia).
echo Para fechar o HUD, feche esta janela preta.
echo.
%PY% -X utf8 -m hud39 %*
pause

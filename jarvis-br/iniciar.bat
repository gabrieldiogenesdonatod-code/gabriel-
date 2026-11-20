@echo off
title JARVIS BR 3.9.3
cd /d "%~dp0"

echo =================================
echo       INICIANDO JARVIS BR
echo =================================

REM Procura o Python nesta ordem:
REM   1) o Python 3.14 instalado para o seu usuario (o mesmo caminho que voce usava)
REM   2) o lancador "py" do Windows
REM   3) o "python" do PATH
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

REM Fork PT-BR 2.12: abre a tela de login; ao entrar ela mesma roda o main.py
%PY% login.py
set CODIGO=%ERRORLEVEL%

echo.
echo JARVIS encerrou. Codigo: %CODIGO%
REM Fork PT-BR 2.7.2: mostra o motivo (o fim de memory\erros.log) para nao fechar "do nada".
if exist "memory\erros.log" (
    echo.
    echo ---- ultimas linhas de memory\erros.log ----
    powershell -NoProfile -Command "Get-Content -Path 'memory\erros.log' -Tail 25 -Encoding UTF8"
    echo --------------------------------------------
    echo Se ele fechou sem voce pedir, mande o arquivo memory\erros.log.
)
REM Fork PT-BR 2.8.1: explica em portugues POR QUE fechou (erros.log + registro de erros do Windows)
echo.
echo ---- POR QUE O JARVIS FECHOU ----
%PY% -X utf8 -m core.por_que_fechou
echo ---------------------------------
echo Voce tambem pode perguntar depois: "Jarvis, por que voce fechou?"
pause

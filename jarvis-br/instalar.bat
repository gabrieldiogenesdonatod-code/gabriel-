@echo off
REM J.A.R.V.I.S BR - instalacao com dois cliques (Windows)
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
    echo Python nao foi encontrado. Instale o Python 3.12 ou 3.13 em
    echo https://www.python.org/downloads/ e marque "Add Python to PATH".
    pause
    exit /b 1
)

if not exist "hud39\static\hud.jpg" (
    echo ERRO: esta pasta esta incompleta - falta a pasta hud39 do HUD 3.9.
    echo Extraia o ZIP completo do J.A.R.V.I.S BR de novo.
    pause
    exit /b 1
)

if not exist "memory\memory_manager.py" (
    echo ERRO: esta pasta esta incompleta - falta memory\memory_manager.py.
    echo Extraia o ZIP completo do J.A.R.V.I.S BR de novo.
    pause
    exit /b 1
)

%PY% setup.py
if not %errorlevel%==0 (
    echo.
    echo A instalacao encontrou um erro. Leia a mensagem acima.
    pause
    exit /b 1
)

echo.
echo Conferindo o projeto...
%PY% -m unittest discover -s tests
echo.
echo Pronto! Para abrir o JARVIS, de dois cliques em iniciar.bat
echo (o HUD 3.9 ja aparece na tela principal).
echo Para abrir so o HUD 3.9, sem o assistente, use abrir_hud.bat
pause

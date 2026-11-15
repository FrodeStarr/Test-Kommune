@echo off
chcp 65001 >nul
setlocal
title Hent møtedokumenter - Brønnøy kommune
cd /d "%~dp0"
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

rem --- Finn Python -------------------------------------------------------
set "PY="
where py >nul 2>&1 && set "PY=py -3"
if not defined PY (
    where python >nul 2>&1 && set "PY=python"
)
if not defined PY goto :ingen_python
%PY% --version >nul 2>&1 || goto :ingen_python

rem --- Installer nødvendige pakker første gang ---------------------------
%PY% -c "import requests" >nul 2>&1
if errorlevel 1 (
    echo Installerer nødvendige pakker ^(kun første gang^)...
    %PY% -m pip install --user -r requirements.txt
    if errorlevel 1 (
        echo.
        echo Klarte ikke å installere pakkene. Sjekk internettforbindelsen.
        pause
        exit /b 1
    )
)

:start
cls
echo ============================================================
echo   Hent møtedokumenter - Brønnøy kommune
echo ============================================================
echo.
echo Hvilket utvalg?
echo   1 = Kommunestyret
echo   2 = Formannskapet
echo   3 = Begge (kommunestyret og formannskapet)
echo   4 = Alle utvalg
echo.
set "VALG="
set "UTVALG="
set /p "VALG=Velg 1-4 [3]: "
if "%VALG%"=="" set "VALG=3"
if "%VALG%"=="1" set "UTVALG=kommunestyret"
if "%VALG%"=="2" set "UTVALG=formannskapet"
if "%VALG%"=="3" set "UTVALG=kommunestyret formannskapet"
if "%VALG%"=="4" set "UTVALG=alle"
if not defined UTVALG (
    echo Ugyldig valg.
    pause
    goto :start
)

echo.
set "AAR="
set /p "AAR=År (f.eks. 2025) [Enter = i år]: "

echo.
set "MND="
set /p "MND=Måned (1-12 eller f.eks. juni) [Enter = hele året]: "

echo.
echo Hva vil du hente?
echo   1 = Innkalling og protokoll
echo   2 = Innkalling, protokoll + saksframlegg og vedlegg for hver sak
echo   3 = Bare protokoll
echo   4 = Bare vis møtene (ingen nedlasting)
set "TYPE="
set /p "TYPE=Velg 1-4 [1]: "
if "%TYPE%"=="" set "TYPE=1"

set "ARGS=-u %UTVALG%"
if not "%AAR%"=="" set "ARGS=%ARGS% --aar %AAR%"
if not "%MND%"=="" set "ARGS=%ARGS% --maaned %MND%"
if "%TYPE%"=="2" set "ARGS=%ARGS% --med-saker"
if "%TYPE%"=="3" set "ARGS=%ARGS% --kun-protokoll"
if "%TYPE%"=="4" set "ARGS=%ARGS% --kun-liste"

echo.
echo ------------------------------------------------------------
%PY% bronnoy_moter.py %ARGS%
echo ------------------------------------------------------------

if not "%TYPE%"=="4" if exist "bronnoy_moter" (
    echo.
    set "AAPNE="
    set /p "AAPNE=Åpne mappen med dokumentene? (J/N) [J]: "
    call :aapne
)

echo.
set "IGJEN="
set /p "IGJEN=Vil du hente flere? (J/N) [N]: "
if /i "%IGJEN%"=="J" goto :start
exit /b 0

:aapne
if /i not "%AAPNE%"=="N" start "" explorer "%~dp0bronnoy_moter"
exit /b 0

:ingen_python
echo.
echo Fant ikke Python på denne maskinen.
echo.
echo 1. Last ned og installer Python fra https://www.python.org/downloads/
echo 2. Huk av for "Add Python to PATH" under installasjonen.
echo 3. Dobbeltklikk på denne filen igjen.
echo.
start "" https://www.python.org/downloads/
pause
exit /b 1

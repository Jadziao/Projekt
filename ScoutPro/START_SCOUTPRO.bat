@echo off
setlocal
cd /d "%~dp0"
title ScoutPro V5 - Europa CC0

echo ===================================
echo   SCOUTPRO V4 - URUCHAMIANIE
echo ===================================
echo.

if not exist ".venv\Scripts\python.exe" goto create_venv
goto check_packages

:create_venv
echo Tworze lokalne srodowisko Python .venv ...
where py >nul 2>&1
if not errorlevel 1 (
    py -3.12 --version >nul 2>&1
    if not errorlevel 1 (
        py -3.12 -m venv .venv
        goto venv_created
    )
    py -3.13 --version >nul 2>&1
    if not errorlevel 1 (
        py -3.13 -m venv .venv
        goto venv_created
    )
    py -3 -m venv .venv
) else (
    python -m venv .venv
)

:venv_created
if not exist ".venv\Scripts\python.exe" (
    echo BLAD: Nie znaleziono Pythona. Zainstaluj Python 3.12 lub 3.13.
    pause
    exit /b 1
)

:check_packages
".venv\Scripts\python.exe" -c "import streamlit, pandas, numpy, plotly, requests, truststore" >nul 2>&1
if not errorlevel 1 goto run_app
echo Instaluje biblioteki z requirements.txt. Wymagany internet przy pierwszym uruchomieniu.
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
    echo BLAD: Instalacja bibliotek nie powiodla sie.
    pause
    exit /b 1
)

:run_app
echo Uruchamiam ScoutPro ...
".venv\Scripts\python.exe" -m streamlit run app.py
if errorlevel 1 (
    echo.
    echo Wystapil blad uruchamiania; komunikat znajduje sie powyzej.
    pause
)
endlocal

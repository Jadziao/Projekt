@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" importuj_ligi_europy.py
) else (
  py -3 importuj_ligi_europy.py
)
echo.
echo Wynik powyzej. Nacisnij dowolny klawisz, aby zamknac.
pause >nul

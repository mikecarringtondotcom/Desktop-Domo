@echo off
rem Launch Desktop Domo (Windows). Double-click me.
rem
rem Uses pythonw.exe so no console window is left hanging around behind the
rem bubble. If the app won't start and you want to see why, use run.ps1
rem instead -- it runs on a normal console and prints the traceback.

setlocal
set "ROOT=%~dp0"

if not exist "%ROOT%.venv\Scripts\pythonw.exe" (
    echo No virtualenv found in "%ROOT%.venv".
    echo Run:  powershell -ExecutionPolicy Bypass -File "%ROOT%setup.ps1"
    pause
    exit /b 1
)

rem /D sets the working directory so "-m desktop_domo.main" can find the package.
start "Desktop Domo" /D "%ROOT%" "%ROOT%.venv\Scripts\pythonw.exe" -m desktop_domo.main %*

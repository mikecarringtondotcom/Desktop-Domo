# Launch Desktop Domo with a console attached (Windows).
#
# Same app as run.cmd, but run through python.exe instead of pythonw.exe, so
# tracebacks and any Qt warnings land in this terminal. Use it when something
# isn't working; use run.cmd for everyday launching.
#
#   powershell -ExecutionPolicy Bypass -File .\run.ps1

$ErrorActionPreference = 'Stop'

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

$VenvPython = Join-Path $Root '.venv\Scripts\python.exe'
if (-not (Test-Path $VenvPython)) {
    throw "No virtualenv found in $Root\.venv. Run .\setup.ps1 first."
}

& $VenvPython -m desktop_domo.main @args

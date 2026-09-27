# One-time setup for Desktop Domo on Windows.
#
# Creates the local virtualenv, installs the dependencies, builds the shortcut
# icon, and puts "Desktop Domo" in the Start Menu. Safe to re-run — it reuses
# an existing .venv and just refreshes the packages.
#
#   powershell -ExecutionPolicy Bypass -File .\setup.ps1
#
# Pass -NoShortcut to skip the Start Menu entry.

[CmdletBinding()]
param(
    [switch]$NoShortcut
)

$ErrorActionPreference = 'Stop'

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

$VenvPython = Join-Path $Root '.venv\Scripts\python.exe'

# --- 1. Virtualenv --------------------------------------------------------
if (-not (Test-Path $VenvPython)) {
    # "py" is the Windows launcher and is the most reliable way to find an
    # interpreter; fall back to whatever "python" resolves to.
    $Launcher = if (Get-Command py -ErrorAction SilentlyContinue) { 'py' }
                elseif (Get-Command python -ErrorAction SilentlyContinue) { 'python' }
                else { $null }
    if (-not $Launcher) {
        throw 'No Python found on PATH. Install Python 3.10+ from python.org, then re-run this script.'
    }
    Write-Host "Creating virtualenv in .venv ..."
    & $Launcher -m venv (Join-Path $Root '.venv')
    if ($LASTEXITCODE -ne 0) { throw 'Could not create the virtualenv.' }
}

Write-Host 'Installing dependencies ...'
& $VenvPython -m pip install --upgrade pip --quiet
& $VenvPython -m pip install -r (Join-Path $Root 'requirements.txt') --quiet
if ($LASTEXITCODE -ne 0) { throw 'Dependency install failed.' }

# --- 2. Shortcut icon -----------------------------------------------------
Write-Host 'Building icon.ico ...'
& $VenvPython (Join-Path $Root 'make_icon.py')

# --- 3. Start Menu shortcut ----------------------------------------------
if (-not $NoShortcut) {
    $StartMenu = Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs'
    $LinkPath = Join-Path $StartMenu 'Desktop Domo.lnk'

    # pythonw.exe is the console-less interpreter, so launching from the Start
    # Menu doesn't leave a black terminal window sitting behind the bubble.
    $Shell = New-Object -ComObject WScript.Shell
    $Link = $Shell.CreateShortcut($LinkPath)
    $Link.TargetPath = Join-Path $Root '.venv\Scripts\pythonw.exe'
    $Link.Arguments = '-m desktop_domo.main'
    $Link.WorkingDirectory = $Root
    $Link.IconLocation = Join-Path $Root 'icon.ico'
    $Link.Description = 'Floating Claude chat bubble'
    $Link.Save()
    Write-Host "Start Menu shortcut written to $LinkPath"
}

# --- 4. API key check -----------------------------------------------------
$EnvFile = Join-Path $Root '.env.local'
$HasKey = $env:ANTHROPIC_API_KEY -or
          ((Test-Path $EnvFile) -and (Select-String -Path $EnvFile -Pattern '^\s*ANTHROPIC_API_KEY\s*=' -Quiet))
if (-not $HasKey) {
    Write-Warning "No Anthropic API key found. Create $EnvFile containing:`n    ANTHROPIC_API_KEY=sk-ant-..."
}

Write-Host ''
Write-Host 'Done. Start it with .\run.cmd, or search "Desktop Domo" in the Start Menu.'

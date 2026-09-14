$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$venvRoot = Join-Path $PSScriptRoot '.venv'
py -3.12 -m venv $venvRoot
if ($LASTEXITCODE -ne 0) { throw 'Python environment creation failed' }
$pythonExe = Join-Path $venvRoot 'Scripts/python.exe'
& $pythonExe -m pip install -r (Join-Path $PSScriptRoot 'requirements-lock.txt')
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed' }
& $pythonExe (Join-Path $PSScriptRoot 'check_environment.py')
if ($LASTEXITCODE -ne 0) { throw 'Environment check failed' }

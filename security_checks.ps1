$ErrorActionPreference = "Stop"
$python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
& $python -m pytest -q
& $python -m bandit -q -r . -x .\.venv,.\tests
& $python -m pip_audit -r (Join-Path $PSScriptRoot "requirements.txt")
& $python -m ruff check $PSScriptRoot

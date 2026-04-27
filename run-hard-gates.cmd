@echo off
setlocal

set "REPO_ROOT=%~dp0"
if "%REPO_ROOT:~-1%"=="\" set "REPO_ROOT=%REPO_ROOT:~0,-1%"

set "PYTHON_EXE=%REPO_ROOT%\backend\.venv-win\Scripts\python.exe"
if not exist "%PYTHON_EXE%" set "PYTHON_EXE=%REPO_ROOT%\backend\.venv\Scripts\python.exe"
set "HARNESS=C:\Users\mac\Documents\Codex\2026-04-22-github-plugin-github-openai-curated-you\heart_transplant_private\run_private_phase_gates.py"

if not exist "%PYTHON_EXE%" (
  echo Missing Python executable: "%PYTHON_EXE%"
  exit /b 1
)

if not exist "%HARNESS%" (
  echo Missing private gate harness: "%HARNESS%"
  exit /b 1
)

"%PYTHON_EXE%" "%HARNESS%" --repo-root "%REPO_ROOT%" %*
exit /b %ERRORLEVEL%

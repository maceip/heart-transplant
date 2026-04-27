@echo off
setlocal

set "REPO_ROOT=%~dp0"
if "%REPO_ROOT:~-1%"=="\" set "REPO_ROOT=%REPO_ROOT:~0,-1%"

set "PYTHON_EXE=%REPO_ROOT%\backend\.venv-win\Scripts\python.exe"
if not exist "%PYTHON_EXE%" set "PYTHON_EXE=%REPO_ROOT%\backend\.venv\Scripts\python.exe"
if "%GOLD_SET%"=="" set "GOLD_SET=%REPO_ROOT%\docs\evals\gold_block_benchmark.json"

:parse_args
if "%~1"=="" goto parsed_args
if "%~1"=="--artifact-dir" (
  set "ARTIFACT_DIR=%~2"
  shift
  shift
  goto parse_args
)
if "%~1"=="--gold-set" (
  set "GOLD_SET=%~2"
  shift
  shift
  goto parse_args
)
if "%~1"=="--holdout-artifact-dir" (
  set "HOLDOUT_ARTIFACT_DIR=%~2"
  shift
  shift
  goto parse_args
)
if "%ARTIFACT_DIR%"=="" (
  set "ARTIFACT_DIR=%~1"
) else if "%GOLD_SET_ARG_SEEN%"=="" (
  set "GOLD_SET=%~1"
  set "GOLD_SET_ARG_SEEN=1"
) else if "%HOLDOUT_ARTIFACT_DIR%"=="" (
  set "HOLDOUT_ARTIFACT_DIR=%~1"
)
shift
goto parse_args
:parsed_args

if not exist "%PYTHON_EXE%" (
  echo Missing Python executable: "%PYTHON_EXE%"
  exit /b 1
)

if "%ARTIFACT_DIR%"=="" (
  echo Usage: run-hard-gates.cmd --artifact-dir ^<artifact-directory^> [--gold-set ^<gold-json^>] [--holdout-artifact-dir ^<artifact-directory^>]
  echo        run-hard-gates.cmd ^<artifact-directory^> [gold-set] [holdout-artifact-directory]
  echo Or set ARTIFACT_DIR, GOLD_SET, and HOLDOUT_ARTIFACT_DIR environment variables.
  exit /b 2
)

if not exist "%ARTIFACT_DIR%" (
  echo Missing artifact directory: "%ARTIFACT_DIR%"
  exit /b 1
)
if not exist "%GOLD_SET%" (
  echo Missing gold set: "%GOLD_SET%"
  exit /b 1
)

pushd "%REPO_ROOT%\backend" || exit /b 1

"%PYTHON_EXE%" -m pytest
if errorlevel 1 exit /b %ERRORLEVEL%

"%PYTHON_EXE%" -m heart_transplant.cli program-surface
if errorlevel 1 exit /b %ERRORLEVEL%

"%PYTHON_EXE%" -m heart_transplant.cli validate-gates --artifact-dir "%ARTIFACT_DIR%"
if errorlevel 1 exit /b %ERRORLEVEL%

if "%HOLDOUT_ARTIFACT_DIR%"=="" (
  "%PYTHON_EXE%" -m heart_transplant.cli maximize-gates "%ARTIFACT_DIR%" --gold-set "%GOLD_SET%"
) else (
  "%PYTHON_EXE%" -m heart_transplant.cli maximize-gates "%ARTIFACT_DIR%" --gold-set "%GOLD_SET%" --holdout-artifact-dir "%HOLDOUT_ARTIFACT_DIR%"
)
if errorlevel 1 exit /b %ERRORLEVEL%

popd
exit /b 0

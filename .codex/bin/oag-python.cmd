@echo off
setlocal

if "%~1"=="" (
  echo OAG Windows Python launcher: missing script path. 1>&2
  exit /b 64
)

set "OAG_SCRIPT=%~1"

where py.exe >nul 2>nul
if not errorlevel 1 goto :use_py

where python.exe >nul 2>nul
if not errorlevel 1 goto :use_python

echo OAG Windows Python launcher: Python 3 not found. Install Python 3 or the Windows py launcher. 1>&2
exit /b 127

:use_py
py.exe -3 "%OAG_SCRIPT%"
exit /b %ERRORLEVEL%

:use_python
python.exe "%OAG_SCRIPT%"
exit /b %ERRORLEVEL%

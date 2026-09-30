@echo off
setlocal
cd /d "%~dp0"
set "PYTHON_CMD=python"
python -c "import sys" >nul 2>&1
if not errorlevel 1 goto python_found
set "PYTHON_CMD=py -3"
py -3 -c "import sys" >nul 2>&1
if errorlevel 1 goto missing_python
:python_found
%PYTHON_CMD% -c "import struct,sys; sys.exit(0 if (3,11) <= sys.version_info[:2] < (3,15) and struct.calcsize('P') == 8 else 1)"
if errorlevel 1 goto unsupported_python
%PYTHON_CMD% -m venv .venv
if errorlevel 1 goto error
".venv\Scripts\python.exe" -m pip install --only-binary=:all: -r requirements.txt
if errorlevel 1 goto error
".venv\Scripts\python.exe" -m pip check
if errorlevel 1 goto error
".venv\Scripts\python.exe" scripts\verify_install.py
if errorlevel 1 goto error
echo Ready. Double-click Start VectorFlow.bat to open the app.
if /i not "%~1"=="--unattended" pause
exit /b 0
:missing_python
echo Python was not found. Install 64-bit Python 3.11 through 3.14 with Python on PATH, then rerun setup.
goto error
:unsupported_python
echo Setup requires 64-bit Python 3.11 through 3.14. Python 3.11 is the tested version.
goto error
:error
echo Setup failed. Check the error above and your internet connection, then rerun setup.bat.
if /i not "%~1"=="--unattended" pause
exit /b 1

@echo off
cd /d "%~dp0"
python -m venv .venv
if errorlevel 1 goto error
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto error
echo Ready. Double-click Start VectorFlow.bat to open the app.
pause
exit /b 0
:error
echo Setup failed. Install Python 3.11 or newer and check the error above.
pause
exit /b 1

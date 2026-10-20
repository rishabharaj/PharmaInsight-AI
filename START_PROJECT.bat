@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  py -3 -m venv .venv
  if errorlevel 1 goto :error
)
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -q -r requirements.txt
if errorlevel 1 goto :error
".venv\Scripts\python.exe" -m pharma_insight.setup
if errorlevel 1 goto :error
".venv\Scripts\python.exe" -m streamlit run app.py --server.address 127.0.0.1
if errorlevel 1 goto :error
exit /b 0
:error
echo.
echo Startup failed. See the error above and the README for setup guidance.
pause
exit /b 1

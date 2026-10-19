@echo off
REM Build "PSO HLS Explorer.exe" for Windows into dist\.  Run from the project folder: build_windows.bat
REM Needs Python 3.10+ from python.org (tick "Add python.exe to PATH" when installing).
cd /d "%~dp0"
if not exist .venv python -m venv .venv
.venv\Scripts\python -m pip install -q -r requirements.txt -r requirements-app.txt || goto :error
.venv\Scripts\python tools\make_icons.py || goto :error
.venv\Scripts\pyinstaller --noconfirm --clean --windowed ^
  --name "PSO HLS Explorer" ^
  --icon assets\icon.ico ^
  --add-data "inputs;inputs" ^
  --exclude-module tkinter ^
  desktop_app.py || goto :error
echo.
echo Built: dist\PSO HLS Explorer\PSO HLS Explorer.exe
goto :eof
:error
echo Build failed.
exit /b 1

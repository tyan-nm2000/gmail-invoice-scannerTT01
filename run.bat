@echo off
REM ===========================================================================
REM  Employee File Scanner - Windows launcher (no Python install required)
REM
REM  On first run this downloads a PRIVATE, self-contained copy of Python into
REM  this folder (.\python\). Nothing is installed on Windows, no admin rights
REM  are needed, and PATH is not touched. Delete this folder to remove it all.
REM ===========================================================================
setlocal
cd /d "%~dp0"
set "PYDIR=%~dp0python"
set "PYEXE=%PYDIR%\python.exe"
set "PYURL=https://www.python.org/ftp/python/3.11.9/python-3.11.9-embed-amd64.zip"
set "PIPURL=https://bootstrap.pypa.io/get-pip.py"

echo.
echo   Employee File Scanner
echo   =====================
echo.

if not exist "%PYEXE%" (
  echo   First-time setup: installing a private copy of Python inside this
  echo   folder. Nothing is added to Windows - delete the folder to undo.
  echo.

  echo   [1/4] Downloading Python...
  curl -L -o "%~dp0python.zip" "%PYURL%"
  if errorlevel 1 goto netfail

  echo   [2/4] Extracting...
  powershell -NoProfile -Command "Expand-Archive -Force -Path '%~dp0python.zip' -DestinationPath '%PYDIR%'"
  if errorlevel 1 goto extractfail
  del "%~dp0python.zip" >nul 2>nul

  REM The embeddable build disables normal imports by default; enable them so
  REM pip and installed packages work.
  powershell -NoProfile -Command "$f=Get-ChildItem '%PYDIR%\python*._pth' | Select-Object -First 1; (Get-Content $f.FullName) -replace '#\s*import site','import site' | Set-Content $f.FullName"

  echo   [3/4] Installing the package manager (pip)...
  curl -L -o "%PYDIR%\get-pip.py" "%PIPURL%"
  if errorlevel 1 goto netfail
  "%PYEXE%" "%PYDIR%\get-pip.py" --no-warn-script-location
  if errorlevel 1 goto pipfail

  echo   [4/4] Installing dependencies (a few minutes, first time only)...
  "%PYEXE%" -m pip install --no-warn-script-location -r "%~dp0requirements-web.txt"
  if errorlevel 1 goto pipfail

  echo.
  echo   Setup complete.
  echo.
)

REM --- Create .env on first run and generate a session secret ----------------
if not exist "%~dp0.env" (
  echo   Creating your settings file (.env)...
  copy /y "%~dp0.env.example" "%~dp0.env" >nul
  "%PYEXE%" -c "import secrets,pathlib;p=pathlib.Path(r'%~dp0.env');p.write_text(p.read_text().replace('SECRET_KEY=','SECRET_KEY='+secrets.token_hex(32)))"
  echo.
  echo   ============================================================
  echo    ONE-TIME STEP: a Notepad window will open. Paste your
  echo    Anthropic API key after
  echo        ANTHROPIC_API_KEY=
  echo    then SAVE and CLOSE Notepad, and run this file again.
  echo   ============================================================
  echo.
  notepad "%~dp0.env"
  pause
  exit /b 0
)

echo   Starting the scanner... open the address shown below in your browser.
echo   (Leave this window open while you use the app; press Ctrl+C to stop.)
echo.
"%PYEXE%" "%~dp0web\app.py"
pause
exit /b 0

:netfail
echo.
echo   [X] Download failed. Check your internet connection and try again.
echo       A corporate proxy or firewall can block these downloads.
pause
exit /b 1

:extractfail
echo.
echo   [X] Could not extract Python. Make sure this folder is not inside a
echo       ZIP viewer - extract the whole project to a real folder first.
pause
exit /b 1

:pipfail
echo.
echo   [X] Installing dependencies failed. Please copy the messages above
echo       and share them so it can be fixed.
pause
exit /b 1

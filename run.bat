@echo off
REM ===========================================================================
REM  Employee File Scanner - Windows launcher
REM  Double-click this file to install everything and start the app.
REM ===========================================================================
setlocal
cd /d "%~dp0"

echo.
echo   Employee File Scanner - setup and launch
echo   =========================================
echo.

REM --- 1. Check Python is installed ------------------------------------------
where python >nul 2>nul
if errorlevel 1 (
  echo   [X] Python was not found on this PC.
  echo.
  echo   Install Python 3.9 or newer from:
  echo       https://www.python.org/downloads/
  echo   IMPORTANT: on the first install screen, tick
  echo       "Add python.exe to PATH"
  echo   then re-run this file.
  echo.
  pause
  exit /b 1
)

REM --- 2. Create a private virtual environment (first run only) --------------
if not exist ".venv\Scripts\activate.bat" (
  echo   Creating virtual environment...
  python -m venv .venv
)
call ".venv\Scripts\activate.bat"

REM --- 3. Install dependencies -----------------------------------------------
echo   Installing dependencies (the first run can take a few minutes)...
python -m pip install --quiet --upgrade pip
python -m pip install --quiet -r requirements.txt
if errorlevel 1 (
  echo   [X] Failed to install dependencies. See the messages above.
  pause
  exit /b 1
)

REM --- 4. Create .env on first run and generate a session secret -------------
if not exist ".env" (
  echo   Creating your settings file (.env)...
  copy /y ".env.example" ".env" >nul
  python -c "import secrets,pathlib;p=pathlib.Path('.env');p.write_text(p.read_text().replace('SECRET_KEY=','SECRET_KEY='+secrets.token_hex(32)))"
  echo.
  echo   ============================================================
  echo    ONE-TIME STEP: a Notepad window will open with your .env
  echo    file. Paste your Anthropic API key after
  echo        ANTHROPIC_API_KEY=
  echo    then SAVE and CLOSE Notepad, and run this file again.
  echo   ============================================================
  echo.
  notepad ".env"
  pause
  exit /b 0
)

REM --- 5. Launch --------------------------------------------------------------
echo   Starting the scanner... open the address shown below in your browser.
echo.
python web\app.py
pause

@echo off
REM E.D.I Voice Assistant - Quick Start Script for Windows

echo.
echo ============================================
echo   E.D.I Smart Voice Assistant Setup
echo ============================================
echo.

REM Check Python installation
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.10+ from https://www.python.org/
    pause
    exit /b 1
)

echo ✓ Python detected
echo.

REM Create virtual environment if it doesn't exist
if not exist "venv\" (
    echo Creating virtual environment...
    python -m venv venv
    echo ✓ Virtual environment created
)

REM Activate virtual environment
call venv\Scripts\activate.bat

echo ✓ Virtual environment activated
echo.

REM Install requirements
echo Installing dependencies...
pip install -q -r requirements.txt
if errorlevel 1 (
    echo ERROR: Failed to install dependencies
    pause
    exit /b 1
)

echo ✓ Dependencies installed
echo.

REM Check for API key
echo.
echo ============================================
echo   IMPORTANT: API Key Configuration
echo ============================================
echo.
echo E.D.I uses Groq API for AI responses.
echo Get your FREE API key: https://console.groq.com
echo.
echo Then edit: Vynce/app.py
echo Look for line 20: GROQ_API_KEY = "..."
echo Replace with your actual API key
echo.
pause

REM Compile check
echo.
echo Checking application syntax...
python -m py_compile "Vynce/app.py"
if errorlevel 1 (
    echo ERROR: Application has syntax errors
    pause
    exit /b 1
)

echo ✓ Application syntax is valid
echo.

REM Launch application
echo.
echo ============================================
echo   Starting E.D.I Voice Assistant
echo ============================================
echo.
echo Tap the animated orb to speak.
echo Say: "Tell me about Python" or "Open YouTube"
echo.
echo Commands:
echo   - Information: "Tell me about [topic]"
echo   - Open apps: "Open YouTube", "Launch Chrome"
echo   - OS control: "Shutdown", "Lock screen"
echo.
pause

python Vynce/app.py

if errorlevel 1 (
    echo.
    echo ERROR: Application crashed
    echo Check requirements.txt dependencies
    pause
    exit /b 1
)

exit /b 0

@echo off
echo Starting Huma UAV Ground Control Station...
echo.

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.8+ and try again
    pause
    exit /b 1
)

REM Change to project directory
cd /d "%~dp0"

REM Check if requirements are installed
echo Checking dependencies...
python -c "import PyQt5, dronekit, pymavlink" >nul 2>&1
if errorlevel 1 (
    echo Installing required dependencies...
    python -m pip install -r requirements.txt
    if errorlevel 1 (
        echo ERROR: Failed to install dependencies
        pause
        exit /b 1
    )
)

REM Run the application
echo Starting Ground Control Station...
echo.
python main.py

if errorlevel 1 (
    echo.
    echo Application exited with error
    pause
)

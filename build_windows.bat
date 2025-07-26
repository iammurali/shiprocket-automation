@echo off
echo PDF Label Processor - Windows Build
echo ===================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo Error: Python is not installed or not in PATH
    echo Please install Python 3.8 or later from https://python.org
    pause
    exit /b 1
)

echo Python found. Installing dependencies...

REM Install required packages
pip install -r requirements.txt
if errorlevel 1 (
    echo Error: Failed to install dependencies
    pause
    exit /b 1
)

echo.
echo Dependencies installed. Building application...

REM Run the build script
python build_windows.py
if errorlevel 1 (
    echo Error: Build failed
    pause
    exit /b 1
)

echo.
echo Build completed successfully!
echo.
echo Files created:
echo - dist\PDF_Label_Processor.exe
echo - PDF_Label_Processor_Windows.zip
echo.
pause 
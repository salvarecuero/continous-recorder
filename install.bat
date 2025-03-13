@echo off
echo Continuous Audio Recorder - Installation
echo =======================================
echo.

REM Check if Python is installed
python --version > nul 2>&1
if %errorlevel% neq 0 (
    echo Python is not installed or not in PATH.
    echo Please install Python from https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH" during installation.
    pause
    exit /b 1
)

echo Python is installed. Installing required packages...
pip install -r requirements.txt

if %errorlevel% neq 0 (
    echo Failed to install required packages.
    pause
    exit /b 1
)

echo.
echo Checking for FFmpeg...
ffmpeg -version > nul 2>&1
if %errorlevel% neq 0 (
    echo FFmpeg is not installed or not in PATH.
    echo Please download FFmpeg from https://ffmpeg.org/download.html
    echo and add it to your PATH, or place ffmpeg.exe in this directory.
    echo.
    echo You can continue without FFmpeg, but MP3 conversion will not work.
)

echo.
echo Installation completed successfully!
echo.
echo To start the recorder:
echo - Run start_recorder.bat for interactive mode
echo - Run start_recorder_background.bat to start recording in the background
echo.
echo For more information, please read the README.md file.
echo.
pause 
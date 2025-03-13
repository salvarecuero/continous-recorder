@echo off
echo Fixing Continuous Audio Recorder...
echo.

if exist continuous_recorder.py (
    echo Backing up original file to continuous_recorder.py.bak
    copy continuous_recorder.py continuous_recorder.py.bak
    echo Replacing with fixed version
    copy continuous_recorder_fixed.py continuous_recorder.py
    echo.
    echo Fix applied successfully!
    echo.
    echo You can now run the recorder using start_recorder.bat
) else (
    echo Error: continuous_recorder.py not found!
)

pause 
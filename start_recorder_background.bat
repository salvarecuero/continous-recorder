@echo off
echo Starting Continuous Audio Recorder in background...
start /min pythonw continuous_recorder.py --start
echo Recorder started. Check recorder.log for details. 
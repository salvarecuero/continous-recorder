"""
File utility functions for the Continuous Audio Recorder.
"""

import os
import time
import datetime
import logging
import platform

logger = logging.getLogger("ContinuousRecorder")

def create_file_path(base_dir, block_start_time, actual_start_time=None):
    """Create a file path for a recording based on timestamp."""
    # Create directory structure based on date
    date_str = block_start_time.strftime("%Y-%m-%d")
    hour_str = block_start_time.strftime("%H")
    
    # Create directory path
    dir_path = os.path.join(base_dir, date_str, hour_str)
    os.makedirs(dir_path, exist_ok=True)
    
    # Create file name
    if actual_start_time:
        # Use actual start time for file name
        time_str = actual_start_time.strftime("%H-%M-%S")
    else:
        # Use block start time for file name
        time_str = block_start_time.strftime("%H-%M-%S")
    
    # Create file path
    file_path = os.path.join(dir_path, f"recording_{time_str}.wav")
    
    return file_path

def cleanup_old_recordings(base_dir, retention_days):
    """Delete recordings older than retention_days."""
    if not os.path.exists(base_dir):
        return
    
    # Calculate cutoff date
    cutoff_date = datetime.datetime.now() - datetime.timedelta(days=retention_days)
    cutoff_str = cutoff_date.strftime("%Y-%m-%d")
    
    # Get list of date directories
    try:
        date_dirs = [d for d in os.listdir(base_dir) if os.path.isdir(os.path.join(base_dir, d))]
    except Exception as e:
        logger.error(f"Error listing directories: {e}")
        return
    
    # Sort directories by date
    date_dirs.sort()
    
    # Delete directories older than cutoff date
    for date_dir in date_dirs:
        try:
            # Skip directories that don't match date format
            if not date_dir[0].isdigit():
                continue
            
            # Check if directory is older than cutoff date
            if date_dir < cutoff_str:
                dir_path = os.path.join(base_dir, date_dir)
                logger.info(f"Deleting old recordings from {date_dir}")
                
                # Delete directory and contents
                delete_directory(dir_path)
        except Exception as e:
            logger.error(f"Error cleaning up directory {date_dir}: {e}")

def delete_directory(dir_path):
    """Delete a directory and all its contents."""
    for root, dirs, files in os.walk(dir_path, topdown=False):
        for file in files:
            try:
                os.remove(os.path.join(root, file))
            except Exception as e:
                logger.error(f"Error deleting file {file}: {e}")
        
        for dir in dirs:
            try:
                os.rmdir(os.path.join(root, dir))
            except Exception as e:
                logger.error(f"Error deleting directory {dir}: {e}")
    
    try:
        os.rmdir(dir_path)
    except Exception as e:
        logger.error(f"Error deleting directory {dir_path}: {e}")

def setup_autostart(enable, app_path=None):
    """Configure application to run on system startup."""
    if platform.system() != "Windows":
        logger.warning("Autostart is only supported on Windows")
        return False
    
    try:
        import winreg
        
        # Get path to current executable
        if app_path is None:
            app_path = os.path.abspath(sys.argv[0])
        
        # Convert to .exe path if running from Python
        if app_path.endswith(".py"):
            # Use start_recorder.bat instead
            app_path = os.path.join(os.path.dirname(app_path), "start_recorder.bat")
        
        # Open registry key
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0,
            winreg.KEY_SET_VALUE | winreg.KEY_QUERY_VALUE
        )
        
        # Set or remove registry value
        if enable:
            winreg.SetValueEx(key, "ContinuousRecorder", 0, winreg.REG_SZ, f'"{app_path}"')
            logger.info(f"Added to startup: {app_path}")
        else:
            try:
                winreg.DeleteValue(key, "ContinuousRecorder")
                logger.info("Removed from startup")
            except FileNotFoundError:
                # Key doesn't exist, nothing to do
                pass
        
        winreg.CloseKey(key)
        return True
    except Exception as e:
        logger.error(f"Error configuring autostart: {e}")
        return False 
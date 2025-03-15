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
    # Create directory structure based on year/month/day
    year_str = block_start_time.strftime("%Y")
    month_str = block_start_time.strftime("%m")
    day_str = block_start_time.strftime("%d")
    
    # Create directory path
    dir_path = os.path.join(base_dir, year_str, month_str, day_str)
    os.makedirs(dir_path, exist_ok=True)
    
    # Determine the actual start time for the recording
    start_time = actual_start_time if actual_start_time else block_start_time
    
    # Calculate the end of the 3-hour block
    # First, determine which 3-hour block this belongs to
    hour = start_time.hour
    block_number = hour // 3
    block_end_hour = (block_number + 1) * 3
    
    # Create end time
    if block_end_hour >= 24:
        # If the block ends at or after midnight, we need to move to the next day
        next_day = start_time + datetime.timedelta(days=1)
        end_time = next_day.replace(hour=0, minute=0, second=0)
    else:
        # Same day, at the end of the 3-hour block
        end_time = start_time.replace(hour=block_end_hour, minute=0, second=0)
    
    # Format start and end times for filename
    start_str = start_time.strftime("%Y-%m-%d_%H-%M-%S")
    end_str = end_time.strftime("%Y-%m-%d_%H-%M-%S")
    
    # Create file path with start and end times in the name
    file_name = f"{start_str}_to_{end_str}.wav"
    file_path = os.path.join(dir_path, file_name)
    
    return file_path

def cleanup_old_recordings(base_dir, retention_days):
    """Delete recordings older than retention_days."""
    if not os.path.exists(base_dir):
        return
    
    # Calculate cutoff date
    cutoff_date = datetime.datetime.now() - datetime.timedelta(days=retention_days)
    cutoff_str = cutoff_date.strftime("%Y-%m-%d")
    
    # Process new format (year/month/day)
    try:
        year_dirs = [d for d in os.listdir(base_dir) if os.path.isdir(os.path.join(base_dir, d)) and d.isdigit()]
        
        # Process each year directory
        for year_dir in year_dirs:
            year_path = os.path.join(base_dir, year_dir)
            
            # Get list of month directories
            try:
                month_dirs = [d for d in os.listdir(year_path) if os.path.isdir(os.path.join(year_path, d)) and d.isdigit()]
            except Exception as e:
                logger.error(f"Error listing month directories in {year_dir}: {e}")
                continue
            
            # Process each month directory
            for month_dir in month_dirs:
                month_path = os.path.join(year_path, month_dir)
                
                # Get list of day directories
                try:
                    day_dirs = [d for d in os.listdir(month_path) if os.path.isdir(os.path.join(month_path, d)) and d.isdigit()]
                except Exception as e:
                    logger.error(f"Error listing day directories in {year_dir}/{month_dir}: {e}")
                    continue
                
                # Process each day directory
                for day_dir in day_dirs:
                    try:
                        # Create date from year/month/day
                        dir_date = datetime.datetime(int(year_dir), int(month_dir), int(day_dir))
                        
                        # Check if directory is older than cutoff date
                        if dir_date < cutoff_date:
                            day_path = os.path.join(month_path, day_dir)
                            logger.info(f"Deleting old recordings from {year_dir}/{month_dir}/{day_dir}")
                            
                            # Delete directory and contents
                            delete_directory(day_path)
                    except Exception as e:
                        logger.error(f"Error cleaning up directory {year_dir}/{month_dir}/{day_dir}: {e}")
                
                # Remove month directory if empty
                try:
                    if os.path.exists(month_path) and not os.listdir(month_path):
                        os.rmdir(month_path)
                except Exception as e:
                    logger.error(f"Error removing empty month directory {year_dir}/{month_dir}: {e}")
            
            # Remove year directory if empty
            try:
                if os.path.exists(year_path) and not os.listdir(year_path):
                    os.rmdir(year_path)
            except Exception as e:
                logger.error(f"Error removing empty year directory {year_dir}: {e}")
    except Exception as e:
        logger.error(f"Error processing new format directories: {e}")
    
    # Process old format (YYYY-MM-DD)
    try:
        date_dirs = [d for d in os.listdir(base_dir) if os.path.isdir(os.path.join(base_dir, d)) 
                    and len(d) == 10 and d[4] == '-' and d[7] == '-']
        
        # Sort directories by date
        date_dirs.sort()
        
        # Delete directories older than cutoff date
        for date_dir in date_dirs:
            try:
                # Check if directory is older than cutoff date
                if date_dir < cutoff_str:
                    dir_path = os.path.join(base_dir, date_dir)
                    logger.info(f"Deleting old recordings from {date_dir} (old format)")
                    
                    # Delete directory and contents
                    delete_directory(dir_path)
            except Exception as e:
                logger.error(f"Error cleaning up directory {date_dir}: {e}")
    except Exception as e:
        logger.error(f"Error processing old format directories: {e}")

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
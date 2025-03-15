"""
System utility functions for the Continuous Audio Recorder.
"""

import os
import sys
import signal
import atexit
import platform
import logging
import time

logger = logging.getLogger("ContinuousRecorder")

def setup_autostart(enable, app_path=None):
    """
    Configure the application to run on system startup.
    
    Args:
        enable: Boolean to enable/disable autostart
        app_path: Path to the application executable
        
    Returns:
        Boolean indicating success
    """
    if app_path is None:
        app_path = os.path.abspath(sys.argv[0])
    
    system = platform.system()
    
    try:
        if system == "Windows":
            import winreg
            startup_key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Run",
                0, winreg.KEY_SET_VALUE | winreg.KEY_QUERY_VALUE
            )
            
            app_name = "ContinuousRecorder"
            
            if enable:
                winreg.SetValueEx(startup_key, app_name, 0, winreg.REG_SZ, f'"{app_path}"')
                logger.info(f"Added {app_name} to startup registry")
            else:
                try:
                    winreg.DeleteValue(startup_key, app_name)
                    logger.info(f"Removed {app_name} from startup registry")
                except FileNotFoundError:
                    pass
            
            winreg.CloseKey(startup_key)
            return True
            
        elif system == "Linux":
            autostart_dir = os.path.expanduser("~/.config/autostart")
            desktop_file = os.path.join(autostart_dir, "continuous-recorder.desktop")
            
            if enable:
                os.makedirs(autostart_dir, exist_ok=True)
                with open(desktop_file, "w") as f:
                    f.write(f"""[Desktop Entry]
Type=Application
Name=Continuous Audio Recorder
Exec={app_path}
Terminal=false
Hidden=false
""")
                logger.info(f"Created autostart desktop file at {desktop_file}")
            else:
                if os.path.exists(desktop_file):
                    os.remove(desktop_file)
                    logger.info(f"Removed autostart desktop file at {desktop_file}")
            
            return True
            
        elif system == "Darwin":  # macOS
            launch_agents_dir = os.path.expanduser("~/Library/LaunchAgents")
            plist_file = os.path.join(launch_agents_dir, "com.user.continuousrecorder.plist")
            
            if enable:
                os.makedirs(launch_agents_dir, exist_ok=True)
                with open(plist_file, "w") as f:
                    f.write(f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.user.continuousrecorder</string>
    <key>ProgramArguments</key>
    <array>
        <string>{app_path}</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
</dict>
</plist>
""")
                logger.info(f"Created LaunchAgent plist at {plist_file}")
            else:
                if os.path.exists(plist_file):
                    os.remove(plist_file)
                    logger.info(f"Removed LaunchAgent plist at {plist_file}")
            
            return True
        
        else:
            logger.error(f"Autostart not supported on {system}")
            return False
            
    except Exception as e:
        logger.error(f"Error setting up autostart: {e}")
        return False

def register_signal_handlers(handler_func):
    """
    Register signal handlers for graceful shutdown.
    
    Args:
        handler_func: Function to call when signals are received
    """
    signal.signal(signal.SIGINT, handler_func)
    signal.signal(signal.SIGTERM, handler_func)

def register_exit_handler(cleanup_func):
    """
    Register a function to be called at program exit.
    
    Args:
        cleanup_func: Function to call at exit
    """
    atexit.register(cleanup_func)

def get_free_disk_space(path):
    """Get free disk space for the given path.
    
    Args:
        path (str): Path to check
        
    Returns:
        int: Free space in bytes
    """
    if not os.path.exists(path):
        # If path doesn't exist, use parent directory
        path = os.path.dirname(path)
        if not os.path.exists(path):
            # If parent doesn't exist, use current directory
            path = os.getcwd()
    
    try:
        if platform.system() == "Windows":
            import ctypes
            free_bytes = ctypes.c_ulonglong(0)
            ctypes.windll.kernel32.GetDiskFreeSpaceExW(
                ctypes.c_wchar_p(path), None, None, ctypes.pointer(free_bytes)
            )
            return free_bytes.value
        else:
            # Unix-based systems
            st = os.statvfs(path)
            return st.f_bavail * st.f_frsize
    except Exception as e:
        logger.error(f"Error getting free disk space: {e}")
        return 0

def measure_execution_time(func):
    """Decorator to measure execution time of a function.
    
    Args:
        func: Function to measure
        
    Returns:
        wrapper: Wrapped function
    """
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        logger.debug(f"{func.__name__} executed in {end_time - start_time:.4f} seconds")
        return result
    return wrapper 
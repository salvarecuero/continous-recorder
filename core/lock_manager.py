"""
Process locking module for the Continuous Audio Recorder.
"""

import os
import logging
import psutil

# Get logger
logger = logging.getLogger("ContinuousRecorder")

class LockManager:
    """Manages process locking for the Continuous Audio Recorder."""
    
    def __init__(self, config_path):
        """Initialize the lock manager.
        
        Args:
            config_path (str): Path to the configuration file
        """
        self.config_path = config_path
        self.pid = os.getpid()
    
    def check_lock(self):
        """Check if another instance is already recording.
        
        Returns:
            bool: True if another instance is recording, False otherwise
        """
        # Get lock file path
        lock_file = os.path.join(os.path.dirname(os.path.abspath(self.config_path)), ".recorder.lock")
        
        # Check if lock file exists
        if os.path.exists(lock_file):
            try:
                # Read PID from lock file
                with open(lock_file, "r") as f:
                    pid = int(f.read().strip())
                
                # Check if process is running
                if psutil.pid_exists(pid):
                    # Process is running, check if it's a recorder
                    try:
                        process = psutil.Process(pid)
                        if "python" in process.name().lower():
                            # It's a Python process, likely a recorder
                            return True
                    except:
                        # Process exists but we can't access it
                        return True
                
                # Process is not running, remove stale lock file
                os.remove(lock_file)
                return False
            except:
                # Error reading lock file, assume it's stale
                try:
                    os.remove(lock_file)
                except:
                    pass
                return False
        
        return False
    
    def create_lock(self):
        """Create a lock file to prevent multiple instances.
        
        Returns:
            bool: True if successful, False otherwise
        """
        # Get lock file path
        lock_file = os.path.join(os.path.dirname(os.path.abspath(self.config_path)), ".recorder.lock")
        
        # Create lock file
        try:
            with open(lock_file, "w") as f:
                f.write(str(self.pid))
            return True
        except:
            return False
    
    def cleanup_lock(self):
        """Remove the lock file.
        
        Returns:
            bool: True if successful, False otherwise
        """
        # Get lock file path
        lock_file = os.path.join(os.path.dirname(os.path.abspath(self.config_path)), ".recorder.lock")
        
        # Check if lock file exists
        if os.path.exists(lock_file):
            try:
                # Read PID from lock file
                with open(lock_file, "r") as f:
                    pid = int(f.read().strip())
                
                # Only remove if it's our lock
                if pid == self.pid:
                    os.remove(lock_file)
                    return True
            except:
                # Error reading lock file, don't remove it
                pass
        
        return False
    
    def send_command(self, command):
        """Send a command to another instance.
        
        Args:
            command (str): Command to send
            
        Returns:
            bool: True if successful, False otherwise
        """
        # Get command file path
        cmd_file = os.path.join(os.path.dirname(os.path.abspath(self.config_path)), ".recorder.cmd")
        
        # Create command file
        try:
            with open(cmd_file, "w") as f:
                f.write(command)
            return True
        except:
            return False
    
    def check_command(self):
        """Check for commands from other instances.
        
        Returns:
            str or None: Command if found, None otherwise
        """
        # Get command file path
        cmd_file = os.path.join(os.path.dirname(os.path.abspath(self.config_path)), ".recorder.cmd")
        
        # Check if command file exists
        if os.path.exists(cmd_file):
            try:
                # Read command from file
                with open(cmd_file, "r") as f:
                    command = f.read().strip()
                
                # Remove command file
                os.remove(cmd_file)
                
                # Return command
                return command
            except:
                # Error reading command file
                try:
                    os.remove(cmd_file)
                except:
                    pass
        
        return None 
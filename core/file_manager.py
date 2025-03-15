"""
File management module for the Continuous Audio Recorder.
"""

import os
import logging
import threading
import time
import sys

from utils.file_utils import cleanup_old_recordings, format_file_size

# Get logger
logger = logging.getLogger("ContinuousRecorder")

class FileManager:
    """Manages files for the Continuous Audio Recorder."""
    
    def __init__(self, config):
        """Initialize the file manager.
        
        Args:
            config (dict): Configuration dictionary
        """
        self.config = config
        self.cleanup_thread = None
        self.recording = False
        
        # Create base recordings directory
        logger.debug(f"Creating recordings directory: {self.config['paths']['recordings_dir']}")
        os.makedirs(self.config["paths"]["recordings_dir"], exist_ok=True)
    
    def start_cleanup_thread(self):
        """Start the cleanup thread.
        
        Returns:
            bool: True if successful, False otherwise
        """
        if self.cleanup_thread is not None:
            return False
        
        self.recording = True
        self.cleanup_thread = threading.Thread(target=self._run_cleanup_thread)
        self.cleanup_thread.daemon = True
        self.cleanup_thread.start()
        
        return True
    
    def stop_cleanup_thread(self):
        """Stop the cleanup thread.
        
        Returns:
            bool: True if successful, False otherwise
        """
        if self.cleanup_thread is None:
            return False
        
        self.recording = False
        
        if self.cleanup_thread is not None:
            self.cleanup_thread.join(timeout=2.0)
            self.cleanup_thread = None
        
        return True
    
    def _run_cleanup_thread(self):
        """Run the cleanup thread."""
        while self.recording:
            try:
                # Run cleanup
                self._cleanup_old_recordings()
                
                # Sleep for a day
                for _ in range(24 * 60 * 60 // 10):
                    if not self.recording:
                        break
                    time.sleep(10)
            except Exception as e:
                logger.error(f"Error in cleanup thread: {e}")
                time.sleep(60)
    
    def _cleanup_old_recordings(self):
        """Delete recordings older than retention_days."""
        cleanup_old_recordings(
            self.config["paths"]["recordings_dir"],
            self.config["general"]["retention_days"]
        )
    
    def get_recordings_folder_size(self):
        """Calculate the total size of the recordings folder.
        
        Returns:
            int: Size in bytes
        """
        total_size = 0
        recordings_dir = self.config["paths"]["recordings_dir"]
        
        if not os.path.exists(recordings_dir):
            return 0
            
        for dirpath, dirnames, filenames in os.walk(recordings_dir):
            for filename in filenames:
                file_path = os.path.join(dirpath, filename)
                if os.path.isfile(file_path):
                    total_size += os.path.getsize(file_path)
                    
        return total_size
    
    def get_free_disk_space(self):
        """Get free disk space where recordings are stored.
        
        Returns:
            int: Free space in bytes
        """
        recordings_dir = self.config["paths"]["recordings_dir"]
        
        if not os.path.exists(recordings_dir):
            # If directory doesn't exist, check the parent directory
            recordings_dir = os.path.dirname(os.path.abspath(recordings_dir))
            if not os.path.exists(recordings_dir):
                # If parent doesn't exist either, use current directory
                recordings_dir = os.getcwd()
        
        try:
            if sys.platform == "win32":
                import ctypes
                free_bytes = ctypes.c_ulonglong(0)
                ctypes.windll.kernel32.GetDiskFreeSpaceExW(
                    ctypes.c_wchar_p(recordings_dir), None, None, ctypes.pointer(free_bytes))
                return free_bytes.value
            else:
                # For Unix-based systems
                st = os.statvfs(recordings_dir)
                return st.f_bavail * st.f_frsize
        except Exception as e:
            logger.error(f"Error getting free disk space: {e}")
            return 0
    
    def calculate_day_size(self):
        """Calculate estimated file size for 1 day of continuous recording.
        
        Returns:
            int: Size in bytes
        """
        # Calculate bytes per second
        bytes_per_sample = 2  # 16-bit = 2 bytes
        channels = 1 if self.config["audio"]["mono"] else self.config["audio"]["channels"]
        bytes_per_second = self.config["audio"]["sample_rate"] * bytes_per_sample * channels
        
        # Calculate total seconds in 1 day
        seconds_in_day = 24 * 60 * 60
        
        # Calculate raw size
        raw_size = bytes_per_second * seconds_in_day
        
        # Apply compression factor if using MP3
        if self.config["audio"]["format"] == "mp3":
            # Compression factors based on quality
            compression_factors = {
                "high": 0.1,    # ~10:1 compression
                "medium": 0.075, # ~13:1 compression
                "low": 0.05     # ~20:1 compression
            }
            compression_factor = compression_factors.get(self.config["audio"]["quality"], 0.1)
            return raw_size * compression_factor
        
        return raw_size
    
    def calculate_block_size(self):
        """Calculate estimated file size for a recording block.
        
        Returns:
            int: Size in bytes
        """
        # Calculate bytes per second
        bytes_per_sample = 2  # 16-bit = 2 bytes
        channels = 1 if self.config["audio"]["mono"] else self.config["audio"]["channels"]
        bytes_per_second = self.config["audio"]["sample_rate"] * bytes_per_sample * channels
        
        # Calculate total seconds in the recording block
        hours = self.config["general"]["recording_hours"]
        seconds_in_block = hours * 60 * 60
        
        # Calculate raw size
        raw_size = bytes_per_second * seconds_in_block
        
        # Apply compression factor if using MP3
        if self.config["audio"]["format"] == "mp3":
            # Compression factors based on quality
            compression_factors = {
                "high": 0.1,    # ~10:1 compression
                "medium": 0.075, # ~13:1 compression
                "low": 0.05     # ~20:1 compression
            }
            compression_factor = compression_factors.get(self.config["audio"]["quality"], 0.1)
            return raw_size * compression_factor
        
        return raw_size
    
    def calculate_90day_size(self):
        """Calculate estimated file size for 90 days of continuous recording.
        
        Returns:
            int: Size in bytes
        """
        # Calculate bytes per second
        bytes_per_sample = 2  # 16-bit = 2 bytes
        channels = 1 if self.config["audio"]["mono"] else self.config["audio"]["channels"]
        bytes_per_second = self.config["audio"]["sample_rate"] * bytes_per_sample * channels
        
        # Calculate total seconds in 90 days
        seconds_in_90days = 90 * 24 * 60 * 60
        
        # Calculate raw size
        raw_size = bytes_per_second * seconds_in_90days
        
        # Apply compression factor if using MP3
        if self.config["audio"]["format"] == "mp3":
            # Compression factors based on quality
            compression_factors = {
                "high": 0.1,    # ~10:1 compression
                "medium": 0.075, # ~13:1 compression
                "low": 0.05     # ~20:1 compression
            }
            compression_factor = compression_factors.get(self.config["audio"]["quality"], 0.1)
            return raw_size * compression_factor
        
        return raw_size
    
    def would_retention_fit(self):
        """Check if the current retention period would fit in the available disk space.
        
        Returns:
            dict: Dictionary with fit information
        """
        # Get free disk space
        free_space = self.get_free_disk_space()
        
        # Calculate size needed for retention period
        day_size = self.calculate_day_size()
        retention_days = self.config["general"]["retention_days"]
        needed_space = day_size * retention_days
        
        # Return result and percentage
        fits = free_space > needed_space
        percentage = (needed_space / free_space * 100) if free_space > 0 else 100
        
        return {
            "fits": fits,
            "free_space": free_space,
            "needed_space": needed_space,
            "percentage": min(percentage, 100)  # Cap at 100%
        }
    
    def display_configuration(self):
        """Display the current recording configuration."""
        logger.info("Current Recording Configuration:")
        logger.info(f"  Sample Rate: {self.config['audio']['sample_rate']} Hz")
        logger.info(f"  Bit Depth: 16-bit")
        logger.info(f"  Channels: {1 if self.config['audio']['mono'] else self.config['audio']['channels']}")
        logger.info(f"  Format: {self.config['audio']['format'].upper()}")
        logger.info(f"  Quality: {self.config['audio']['quality']}")
        logger.info(f"  Recording Block Hours: {self.config['general']['recording_hours']}")
        logger.info(f"  Retention Period: {self.config['general']['retention_days']} days")
        
        # Calculate and display estimated file sizes
        block_size = self.calculate_block_size()
        day_size = self.calculate_day_size()
        estimated_size = self.calculate_90day_size()
        logger.info(f"  Estimated Block Size ({self.config['general']['recording_hours']} hours): {format_file_size(block_size)}")
        logger.info(f"  Estimated Daily Storage Requirement: {format_file_size(day_size)}")
        logger.info(f"  Estimated 90-Day Storage Requirement: {format_file_size(estimated_size)}")
        
        # Display current recordings folder size
        folder_size = self.get_recordings_folder_size()
        logger.info(f"  Current Recordings Folder Size: {format_file_size(folder_size)}")
        
        # Display free disk space
        free_space = self.get_free_disk_space()
        logger.info(f"  Free Disk Space: {format_file_size(free_space)}")
        
        # Check if retention would fit
        retention_fit = self.would_retention_fit()
        if retention_fit["fits"]:
            logger.info(f"  Retention Period Would Fit in Available Space (Using {retention_fit['percentage']:.1f}% of free space)")
        else:
            logger.warning(f"  WARNING: Retention Period Would NOT Fit in Available Space (Needs {format_file_size(retention_fit['needed_space'])})") 
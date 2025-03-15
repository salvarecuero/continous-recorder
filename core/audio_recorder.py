"""
Core audio recorder module for the Continuous Audio Recorder.
"""

import os
import sys
import time
import signal
import atexit
import logging
import datetime

from config.settings import load_config, save_config
from core.device_manager import DeviceManager
from core.audio_processor import AudioProcessor
from core.monitor import AudioMonitor
from core.file_manager import FileManager
from core.lock_manager import LockManager
from utils.file_utils import setup_autostart

# Check if WASAPI is available
try:
    import pyaudiowpatch as pyaudio
    HAS_WASAPI = True
except ImportError:
    import pyaudio
    HAS_WASAPI = False

# Get logger
logger = logging.getLogger("ContinuousRecorder")

class AudioRecorder:
    """Main class for handling continuous audio recording from system output."""
    
    def __init__(self, config_path="config.ini"):
        """Initialize the recorder with configuration."""
        logger.info("Initializing AudioRecorder")
        try:
            logger.debug(f"Loading configuration from {config_path}")
            self.config = load_config(config_path)
            self.config_path = config_path
            
            # Initialize components
            self.device_manager = DeviceManager(self.config)
            self.audio_processor = AudioProcessor(self.config, self.device_manager)
            self.monitor = AudioMonitor(self.config)
            self.file_manager = FileManager(self.config)
            self.lock_manager = LockManager(self.config_path)
            
            # Register signal handlers for graceful shutdown
            logger.debug("Registering signal handlers")
            signal.signal(signal.SIGINT, self._signal_handler)
            signal.signal(signal.SIGTERM, self._signal_handler)
            
            # Register cleanup function
            logger.debug("Registering cleanup function")
            atexit.register(self._cleanup)
            
            # Display current configuration
            logger.debug("Displaying configuration")
            self.file_manager.display_configuration()
            
            # Initialize device error
            self.device_error = None  # Initialize device error message
            
            logger.info("AudioRecorder initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing AudioRecorder: {e}")
            raise
    
    def _save_config(self):
        """Save configuration to file."""
        result = save_config(self.config, self.config_path)
        if result:
            # Display updated configuration
            self.file_manager.display_configuration()
        return result
    
    def list_devices(self):
        """List available audio devices and return them."""
        return self.device_manager.list_devices()
    
    def set_audio_quality(self, quality):
        """Set audio quality for MP3 conversion."""
        if self.audio_processor.set_audio_quality(quality):
            self._save_config()
            return True
        return False
    
    def set_mono(self, mono):
        """Set mono/stereo recording mode."""
        if self.audio_processor.set_mono(mono):
            self._save_config()
            return True
        return False
    
    def set_monitor_level(self, level):
        """Set audio monitoring level."""
        if self.monitor.set_monitor_level(level):
            self._save_config()
            return True
        return False
    
    def start_recording(self):
        """Start the recording process."""
        logger.info("Starting main recording process...")
        
        try:
            # Check if already recording
            if self.recording:
                logger.warning("Recording is already in progress")
                return True
            
            # Check if another instance is already recording
            logger.debug("Checking for other recording instances...")
            if self.lock_manager.check_lock():
                logger.error("Another instance is already recording")
                return False
            
            # Create lock file
            logger.debug("Creating lock file...")
            if not self.lock_manager.create_lock():
                logger.error("Failed to create lock file")
                return False
            
            # Start audio processor
            logger.debug("Starting audio processor...")
            if not self.audio_processor.start_recording():
                logger.error("Failed to start audio processor")
                self.lock_manager.cleanup_lock()
                return False
            
            # Start monitor
            logger.debug("Starting audio monitor...")
            self.monitor.start_monitor(self.audio, self.audio_queue)
            
            # Start cleanup thread
            logger.debug("Starting cleanup thread...")
            self.file_manager.start_cleanup_thread()
            
            logger.info("Main recording process started successfully")
            return True
        except Exception as e:
            logger.error(f"Error starting recording: {e}")
            # Attempt to clean up
            try:
                self.stop_recording()
            except Exception as cleanup_error:
                logger.error(f"Error during cleanup after failed start: {cleanup_error}")
            return False
    
    def stop_recording(self):
        """Stop the recording process."""
        logger.info("Stopping main recording process...")
        
        try:
            # Check if not recording
            if not self.recording:
                logger.debug("Not currently recording, nothing to stop")
                return True
            
            # Stop audio processor
            logger.debug("Stopping audio processor...")
            self.audio_processor.stop_recording()
            
            # Stop monitor
            logger.debug("Stopping audio monitor...")
            self.monitor.stop_monitor()
            
            # Stop cleanup thread
            logger.debug("Stopping cleanup thread...")
            self.file_manager.stop_cleanup_thread()
            
            # Remove lock file
            logger.debug("Removing lock file...")
            self.lock_manager.cleanup_lock()
            
            logger.info("Main recording process stopped successfully")
            return True
        except Exception as e:
            logger.error(f"Error stopping recording: {e}")
            # Try to clean up lock file anyway
            try:
                self.lock_manager.cleanup_lock()
            except Exception as cleanup_error:
                logger.error(f"Error cleaning up lock file: {cleanup_error}")
            return False
    
    def pause_recording(self):
        """Pause the recording process."""
        return self.audio_processor.pause_recording()
    
    def resume_recording(self):
        """Resume the recording process."""
        return self.audio_processor.resume_recording()
    
    def get_status(self):
        """Get the current status of the recorder."""
        # Get recording state once to avoid multiple property accesses
        is_recording = self.recording
        is_paused = self.paused
        
        # Determine status text
        if not is_recording:
            status_text = "Stopped"
        elif is_paused:
            status_text = "Paused"
        else:
            status_text = "Recording"
        
        # Calculate recording time
        recording_time = 0
        if is_recording and hasattr(self.audio_processor, 'recording_start_time') and self.audio_processor.recording_start_time:
            recording_time = time.time() - self.audio_processor.recording_start_time
        
        # Get device info once
        device_name = None
        device_index = self.device_manager.device_index
        if device_index is not None:
            device_info = self.device_manager.get_device_info()
            if device_info:
                device_name = device_info["name"]
            else:
                device_name = f"Device {device_index}"
        
        # Get file sizes and disk space
        try:
            current_block_size = self.get_current_block_size()
            recordings_folder_size = self.get_recordings_folder_size()
            free_disk_space = self.get_free_disk_space()
            day_size = self.calculate_day_size()
            retention_size = self.calculate_90day_size()
            would_fit = self.would_retention_fit()
        except Exception as e:
            logger.error(f"Error getting file sizes: {e}")
            current_block_size = 0
            recordings_folder_size = 0
            free_disk_space = 0
            day_size = 0
            retention_size = 0
            would_fit = False
        
        # Build status dictionary
        status = {
            "status": status_text,
            "recording": is_recording,
            "paused": is_paused,
            "device_index": device_index,
            "device": device_name,
            "sample_rate": self.config["audio"]["sample_rate"],
            "channels": self.config["audio"]["channels"],
            "format": self.config["audio"]["format"],
            "quality": self.config["audio"]["quality"],
            "mono": self.config["audio"]["mono"],
            "monitor_level": self.config["audio"]["monitor_level"],
            "current_file": self.current_file,
            "recordings_dir": self.config["paths"]["recordings_dir"],
            "retention_days": self.config["general"]["retention_days"],
            "recording_hours": self.config["general"]["recording_hours"],
            "recording_time": recording_time,
            "next_block_time": self.get_time_until_next_block() if is_recording else 0,
            "current_block_size": current_block_size,
            "recordings_folder_size": recordings_folder_size,
            "free_disk_space": free_disk_space,
            "day_size": day_size,
            "retention_size": retention_size,
            "would_retention_fit": would_fit,
            "device_error": self.has_device_error()
        }
        
        return status
    
    def set_device(self, device_index):
        """Set the recording device."""
        if self.device_manager.set_device(device_index):
            self._save_config()
            return True
        return False
    
    def setup_autostart(self, enable):
        """Configure application to run on system startup."""
        return setup_autostart(enable)
    
    def _signal_handler(self, sig, frame):
        """Handle signals for graceful shutdown."""
        logger.info(f"Signal {sig} received, stopping recording")
        try:
            self.stop_recording()
        except Exception as e:
            logger.error(f"Error stopping recording during signal handling: {e}")
        finally:
            sys.exit(0)
    
    def _cleanup(self):
        """Clean up resources on exit."""
        logger.debug("Cleaning up resources")
        try:
            # Only stop recording if it's actually in progress
            if self.recording:
                logger.debug("Recording in progress, stopping before exit")
                self.stop_recording()
            else:
                logger.debug("No recording in progress, nothing to stop")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
        
        try:
            self.lock_manager.cleanup_lock()
        except Exception as e:
            logger.error(f"Error cleaning up lock file: {e}")
    
    def get_audio_level(self):
        """Get the current audio level for visualization."""
        return self.audio_processor.get_audio_level()
    
    def get_device_level(self):
        """Get the current audio level from the device."""
        try:
            return self.device_manager.get_device_level()
        except Exception as e:
            if "timeout" in str(e).lower():
                self._handle_timeout("get_device_level")
            return 0
    
    def is_device_valid(self):
        """Check if the device is valid and available."""
        try:
            return self.device_manager.is_device_valid()
        except Exception as e:
            if "timeout" in str(e).lower():
                self._handle_timeout("is_device_valid")
            return False
    
    def find_working_device(self):
        """Find a working audio device and switch to it."""
        if self.device_manager.find_working_device():
            self._save_config()
            return True
        return False
    
    @property
    def device_index(self):
        """Get the current device index."""
        return self.device_manager.device_index
    
    @property
    def recording(self):
        """Check if recording is in progress."""
        return self.audio_processor.recording if hasattr(self.audio_processor, 'recording') else False
    
    @property
    def paused(self):
        """Check if recording is paused."""
        return self.audio_processor.paused if hasattr(self.audio_processor, 'paused') else False
    
    def calculate_block_size(self):
        """Calculate the size of one recording block.
        
        Returns:
            int: Size in bytes
        """
        return self.file_manager.calculate_block_size()
    
    @property
    def audio(self):
        """Get the PyAudio instance."""
        return self.audio_processor.audio if hasattr(self.audio_processor, 'audio') else None
    
    @property
    def audio_queue(self):
        """Get the audio queue."""
        return self.audio_processor.audio_queue if hasattr(self.audio_processor, 'audio_queue') else None
    
    @property
    def current_file(self):
        """Get the current recording file."""
        if hasattr(self.audio_processor, 'get_current_file'):
            return self.audio_processor.get_current_file()
        return None
    
    def format_file_size(self, size_bytes):
        """Format file size in human-readable format.
        
        Args:
            size_bytes (int): Size in bytes
            
        Returns:
            str: Formatted size string
        """
        from utils.file_utils import format_file_size
        return format_file_size(size_bytes)
        
    def get_recordings_folder_size(self):
        """Get the size of the recordings folder.
        
        Returns:
            int: Size in bytes
        """
        return self.file_manager.get_recordings_folder_size()
        
    def get_free_disk_space(self):
        """Get the free disk space.
        
        Returns:
            int: Size in bytes
        """
        return self.file_manager.get_free_disk_space()
        
    def calculate_day_size(self):
        """Calculate the size of one day of recordings.
        
        Returns:
            int: Size in bytes
        """
        return self.file_manager.calculate_day_size()
        
    def calculate_90day_size(self):
        """Calculate the size of 90 days of recordings.
        
        Returns:
            int: Size in bytes
        """
        return self.file_manager.calculate_90day_size()
        
    def would_retention_fit(self):
        """Check if the current retention period would fit in the available disk space.
        
        Returns:
            bool: True if it would fit, False otherwise
        """
        return self.file_manager.would_retention_fit()
        
    def get_current_block_size(self):
        """Get the current block file size in bytes.
        
        Returns:
            int: Size in bytes
        """
        return self.audio_processor.get_current_block_size()
    
    def get_time_until_next_block(self):
        """Calculate the time remaining until the next recording block starts.
        
        Returns:
            float: Time in seconds until the next block
        """
        return self.audio_processor.get_time_until_next_block()
    
    def _handle_timeout(self, operation):
        """Handle a timeout error.
        
        Args:
            operation (str): The operation that timed out
        """
        logger.warning(f"Timeout detected during {operation}, switching to a working device")
        
        # Try to find a working device immediately
        if self.find_working_device():
            logger.info("Successfully switched to a working device")
            self.device_error = "Device timeout detected. Switched to a working device."
        else:
            logger.error("Failed to find a working device")
            self.device_error = "Device timeout detected. Failed to find a working device."
    
    def has_device_error(self):
        """Check if there's a device error.
        
        Returns:
            str or None: Error message if there's an error, None otherwise
        """
        if hasattr(self, 'device_error') and self.device_error:
            error = self.device_error
            self.device_error = None  # Clear the error after it's been read
            return error
        return None 
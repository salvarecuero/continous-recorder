"""
Audio processing module for the Continuous Audio Recorder.
"""

import logging
import queue
import time
import datetime

from core.audio_stream_manager import AudioStreamManager
from core.audio_file_handler import AudioFileHandler
from core.audio_level_analyzer import AudioLevelAnalyzer

# Get logger
logger = logging.getLogger("ContinuousRecorder")

class AudioProcessor:
    """Coordinates audio recording, processing, and file management for the Continuous Audio Recorder."""
    
    def __init__(self, config, device_manager):
        """Initialize the audio processor.
        
        Args:
            config (dict): Configuration dictionary
            device_manager (DeviceManager): Device manager instance
        """
        self.config = config
        self.device_manager = device_manager
        self.recording = False
        self.paused = False
        self.recording_start_time = None
        
        # Create audio queue for communication between components
        self.audio_queue = queue.Queue()
        
        # Initialize components
        self.stream_manager = AudioStreamManager(config, device_manager, self.audio_queue)
        self.file_handler = AudioFileHandler(config, self.audio_queue)
        self.level_analyzer = AudioLevelAnalyzer()
    
    def start_recording(self):
        """Start the recording process.
        
        Returns:
            bool: True if successful, False otherwise
        """
        logger.debug("Initializing audio processor components...")
        if self.recording:
            logger.warning("Audio processor is already recording")
            return False
        
        # Start stream manager
        if not self.stream_manager.start_recording():
            logger.error("Failed to start audio stream")
            return False
        
        # Start file handler
        if not self.file_handler.start_processing():
            logger.error("Failed to start audio processing")
            self.stream_manager.stop_recording()
            return False
        
        # Set recording flags
        self.recording = True
        self.paused = False
        
        # Update recording start time
        self.recording_start_time = time.time()
        
        logger.info("Audio processor initialized successfully")
        return True
    
    def stop_recording(self):
        """Stop the recording process.
        
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.recording:
            logger.warning("Audio processor is not recording")
            return False
        
        # Stop recording
        self.recording = False
        
        # Stop stream manager
        self.stream_manager.stop_recording()
        
        # Stop file handler
        self.file_handler.stop_processing()
        
        # Update recording start time
        self.recording_start_time = None
        
        logger.info("Audio processor shutdown complete")
        return True
    
    def pause_recording(self):
        """Pause the recording process.
        
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.recording:
            logger.warning("Audio processor is not recording")
            return False
        
        self.paused = True
        self.stream_manager.pause_recording()
        
        logger.info("Audio processor paused")
        return True
    
    def resume_recording(self):
        """Resume the recording process.
        
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.recording:
            logger.warning("Audio processor is not recording")
            return False
        
        self.paused = False
        self.stream_manager.resume_recording()
        
        logger.info("Audio processor resumed")
        return True
    
    def get_time_until_next_block(self):
        """Calculate the time remaining until the next recording block starts.
        
        Returns:
            float: Time in seconds until the next block
        """
        return self.file_handler.get_time_until_next_block()
    
    def get_current_block_size(self):
        """Get the current block file size in bytes.
        
        Returns:
            int: Size in bytes
        """
        return self.file_handler.get_current_block_size()
    
    def get_audio_level(self):
        """Get the current audio level for visualization.
        
        Returns:
            tuple: (rms, db, level) where:
                rms is the root mean square of the audio samples
                db is the decibel level (-60 to 0)
                level is the normalized level (0 to 1)
        """
        viz_buffer = self.stream_manager.get_visualization_buffer()
        return self.level_analyzer.get_audio_level(viz_buffer, self.recording)
    
    def set_audio_quality(self, quality):
        """Set audio quality for MP3 conversion.
        
        Args:
            quality (str): Quality setting ('high', 'medium', 'low')
            
        Returns:
            bool: True if successful, False otherwise
        """
        if quality not in ["high", "medium", "low"]:
            logger.error(f"Invalid quality setting: {quality}")
            return False
        
        self.config["audio"]["quality"] = quality
        return True
    
    def set_mono(self, mono):
        """Set mono/stereo recording mode.
        
        Args:
            mono (bool): True for mono, False for stereo
            
        Returns:
            bool: True if successful, False otherwise
        """
        self.config["audio"]["mono"] = bool(mono)
        return True
        
    def get_current_file(self):
        """Get the current recording file path.
        
        Returns:
            str: Current file path or None if not recording
        """
        if hasattr(self.file_handler, 'current_file'):
            return self.file_handler.current_file
        return None
        
    @property
    def audio(self):
        """Get the PyAudio instance.
        
        Returns:
            PyAudio: PyAudio instance or None if not initialized
        """
        if hasattr(self.stream_manager, 'audio'):
            return self.stream_manager.audio
        return None 
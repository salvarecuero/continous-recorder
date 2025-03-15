"""
Audio file handler for the Continuous Audio Recorder.
Manages file creation, writing, and conversion.
"""

import os
import time
import datetime
import logging
import threading
import queue

from utils.file_utils import create_file_path, calculate_block_times, create_wave_file
from utils.audio_utils import convert_to_mp3

# Get logger
logger = logging.getLogger("ContinuousRecorder")

class AudioFileHandler:
    """Manages audio file creation, writing, and conversion."""
    
    def __init__(self, config, audio_queue):
        """Initialize the audio file handler.
        
        Args:
            config (dict): Configuration dictionary
            audio_queue (queue.Queue): Queue for audio data
        """
        self.config = config
        self.audio_queue = audio_queue
        self.recording = False
        self.process_thread = None
        self.current_file = None
        self.current_wave = None
        self.current_block_size = 0
        self.recording_start_time = None  # Track the actual recording start time
    
    def start_processing(self):
        """Start processing audio data from the queue.
        
        Returns:
            bool: True if successful, False otherwise
        """
        if self.recording:
            logger.warning("File processing is already active")
            return False
        
        # Start recording
        self.recording = True
        
        # Set recording start time
        self.recording_start_time = datetime.datetime.now()
        
        # Start process thread
        logger.debug("Starting process thread...")
        self.process_thread = threading.Thread(target=self._process_audio)
        self.process_thread.daemon = True
        self.process_thread.start()
        
        logger.info("File processing started successfully")
        return True
    
    def stop_processing(self):
        """Stop processing audio data.
        
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.recording:
            logger.warning("File processing is not active")
            return False
        
        # Stop recording
        self.recording = False
        
        # Wait for thread to finish
        if self.process_thread is not None:
            self.process_thread.join(timeout=2.0)
            self.process_thread = None
        
        # Close current file
        current_file_path = None
        if self.current_wave is not None:
            try:
                current_file_path = self.current_file
                self.current_wave.close()
                self.current_wave = None
                self.current_file = None
                
                # Convert to MP3 if needed
                if current_file_path and self.config["audio"]["format"] == "mp3":
                    mp3_file = convert_to_mp3(
                        current_file_path,
                        self.config["paths"]["ffmpeg_path"],
                        self.config["audio"]["quality"]
                    )
                    if mp3_file:
                        logger.info(f"Converted to {mp3_file}")
                
            except Exception as e:
                logger.error(f"Error closing wave file: {e}")
        
        logger.info("File processing stopped successfully")
        return True
    
    def get_current_block_size(self):
        """Get the current block file size in bytes.
        
        Returns:
            int: Size in bytes
        """
        import os
        if self.current_file and os.path.exists(self.current_file):
            return os.path.getsize(self.current_file)
        return 0
    
    def get_time_until_next_block(self):
        """Calculate the time remaining until the next recording block starts.
        
        Returns:
            float: Time in seconds until the next block
        """
        if not self.recording:
            return 0
            
        now = datetime.datetime.now()
        recording_hours = self.config["general"]["recording_hours"]
        
        from utils.file_utils import get_time_until_next_block
        return get_time_until_next_block(now, recording_hours)
    
    def _create_new_wave_file(self, block_start_time):
        """Create a new WAV file for the current block.
        
        Args:
            block_start_time (datetime): Start time of the current block
            
        Returns:
            tuple: (file_path, wave_file)
        """
        # Create file path with the actual recording start time
        file_path = create_file_path(
            self.config["paths"]["recordings_dir"],
            block_start_time,
            self.recording_start_time,
            self.config["general"]["recording_hours"]
        )
        
        # Determine channels (mono or original)
        channels = 1 if self.config["audio"]["mono"] else self.config["audio"]["channels"]
        
        # Create wave file
        wave_file = create_wave_file(file_path, channels, self.config["audio"]["sample_rate"])
        
        logger.info(f"Creating new recording file: {file_path}")
        
        return file_path, wave_file
    
    def _process_audio(self):
        """Process audio data from the queue."""
        # Initialize variables
        block_start_time = datetime.datetime.now()
        self.current_block_size = 0
        
        # Calculate block times
        block_start_time, block_end_time = calculate_block_times(
            block_start_time, 
            self.config["general"]["recording_hours"]
        )
        
        # Create wave file
        self.current_file, self.current_wave = self._create_new_wave_file(block_start_time)
        
        # Process audio
        while self.recording:
            try:
                # Check if block time has elapsed
                now = datetime.datetime.now()
                if now >= block_end_time:
                    # Close current file
                    self.current_wave.close()
                    
                    # Convert to MP3 if needed
                    if self.config["audio"]["format"] == "mp3":
                        mp3_file = convert_to_mp3(
                            self.current_file,
                            self.config["paths"]["ffmpeg_path"],
                            self.config["audio"]["quality"]
                        )
                        if mp3_file:
                            logger.info(f"Converted to {mp3_file}")
                    
                    # Start new block
                    block_start_time = now
                    
                    # Calculate new block times
                    block_start_time, block_end_time = calculate_block_times(
                        block_start_time, 
                        self.config["general"]["recording_hours"]
                    )
                    
                    # Create new wave file - use the same recording_start_time for consistent naming
                    self.current_file, self.current_wave = self._create_new_wave_file(block_start_time)
                    
                    # Reset block size
                    self.current_block_size = 0
                
                # Get data from queue
                try:
                    data = self.audio_queue.get(block=True, timeout=0.1)
                    
                    # Write to file
                    self.current_wave.writeframes(data)
                    
                    # Update current block size
                    self.current_block_size += len(data)
                    
                    # Log current block size every 5 minutes (300 seconds)
                    current_time = int(time.time())
                    if current_time % 300 == 0:
                        from utils.file_utils import format_file_size
                        logger.info(f"Current block size: {format_file_size(self.get_current_block_size())}")
                    
                except queue.Empty:
                    pass
            except Exception as e:
                logger.error(f"Error in process thread: {e}")
                time.sleep(0.1) 
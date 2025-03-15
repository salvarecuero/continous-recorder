"""
Audio stream manager for the Continuous Audio Recorder.
Handles PyAudio stream initialization, recording, and cleanup.
"""

import logging
import threading
import time
import queue

import numpy as np

from utils.audio_utils import get_pyaudio_instance, setup_audio_stream, convert_to_mono

# Get logger
logger = logging.getLogger("ContinuousRecorder")

# Check if WASAPI is available
try:
    import pyaudiowpatch as pyaudio
    HAS_WASAPI = True
except ImportError:
    import pyaudio
    HAS_WASAPI = False

class AudioStreamManager:
    """Manages audio stream initialization, recording, and cleanup."""
    
    def __init__(self, config, device_manager, audio_queue):
        """Initialize the audio stream manager.
        
        Args:
            config (dict): Configuration dictionary
            device_manager (DeviceManager): Device manager instance
            audio_queue (queue.Queue): Queue for audio data
        """
        self.config = config
        self.device_manager = device_manager
        self.audio_queue = audio_queue
        self.audio = None
        self.stream = None
        self.recording = False
        self.paused = False
        self.record_thread = None
        
        # Visualization buffer
        self._viz_buffer = bytearray()
        self._viz_buffer_size = 0
    
    def initialize_audio(self):
        """Initialize PyAudio instance.
        
        Returns:
            bool: True if successful, False otherwise
        """
        logger.debug("Initializing PyAudio...")
        if self.audio is None:
            self.audio, _ = get_pyaudio_instance()
            if self.audio is None:
                logger.error("Failed to initialize PyAudio")
                return False
        return True
    
    def start_recording(self):
        """Start the recording process.
        
        Returns:
            bool: True if successful, False otherwise
        """
        logger.debug("Initializing audio stream...")
        if self.recording:
            logger.warning("Audio stream is already active")
            return False
        
        # Initialize PyAudio
        if not self.initialize_audio():
            return False
        
        # Ensure we have a valid device
        logger.debug("Checking device index...")
        if self.device_manager.device_index is None:
            logger.debug("No device index set, attempting to find one...")
            self.device_manager.device_index = self.device_manager._get_device_index(force_refresh=True)
            if self.device_manager.device_index is None:
                logger.error("No valid recording device found. Cannot start recording.")
                return False
        
        # Validate device exists
        logger.debug(f"Validating device index {self.device_manager.device_index}...")
        try:
            device_info = self.audio.get_device_info_by_index(self.device_manager.device_index)
            logger.info(f"Using device: {device_info['name']}")
        except Exception as e:
            logger.error(f"Invalid device index {self.device_manager.device_index}: {e}")
            # Try to get a valid device
            logger.debug("Attempting to find a new valid device...")
            self.device_manager.device_index = self.device_manager._get_device_index(force_refresh=True)
            if self.device_manager.device_index is None:
                logger.error("Could not find a valid recording device. Cannot start recording.")
                return False
        
        # Start recording
        logger.debug("Setting recording flags...")
        self.recording = True
        self.paused = False
        
        # Initialize visualization buffer
        logger.debug("Initializing visualization buffer")
        self._viz_buffer = bytearray()
        self._viz_buffer_size = self.config["audio"]["sample_rate"] * 2 * 0.1  # 100ms of audio
        
        # Start record thread
        logger.debug("Starting record thread...")
        self.record_thread = threading.Thread(target=self._record_audio)
        self.record_thread.daemon = True
        self.record_thread.start()
        
        logger.info("Audio stream started successfully")
        return True
    
    def stop_recording(self):
        """Stop the recording process.
        
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.recording:
            logger.warning("Audio stream is not active")
            return False
        
        # Stop recording
        self.recording = False
        
        # Wait for thread to finish
        if self.record_thread is not None:
            self.record_thread.join(timeout=2.0)
            self.record_thread = None
        
        # Close stream
        if self.stream is not None:
            try:
                logger.debug("Stopping stream")
                self.stream.stop_stream()
                logger.debug("Closing stream")
                self.stream.close()
                logger.debug("Closed audio stream")
            except Exception as e:
                logger.error(f"Error closing audio stream: {e}")
            finally:
                self.stream = None
        
        # Clean up PyAudio
        if self.audio is not None:
            try:
                self.audio.terminate()
                self.audio = None
            except Exception as e:
                logger.error(f"Error terminating PyAudio: {e}")
        
        logger.info("Audio stream stopped successfully")
        return True
    
    def pause_recording(self):
        """Pause the recording process.
        
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.recording:
            logger.warning("Audio stream is not active")
            return False
        
        self.paused = True
        logger.info("Audio stream paused")
        return True
    
    def resume_recording(self):
        """Resume the recording process.
        
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.recording:
            logger.warning("Audio stream is not active")
            return False
        
        self.paused = False
        logger.info("Audio stream resumed")
        return True
    
    def get_visualization_buffer(self):
        """Get the current visualization buffer.
        
        Returns:
            bytearray: Audio data for visualization
        """
        # Return a copy to prevent external modification
        if self._viz_buffer:
            return bytes(self._viz_buffer)
        return bytearray()
    
    def _record_audio(self):
        """Record audio from the selected device."""
        logger.info("Record thread started")
        try:
            # Validate device index
            logger.debug(f"Validating device index: {self.device_manager.device_index}")
            if self.device_manager.device_index is None:
                logger.error("No valid recording device selected")
                self.recording = False
                return
                
            # Verify device exists
            logger.debug(f"Verifying device {self.device_manager.device_index} exists")
            try:
                device_info = self.audio.get_device_info_by_index(self.device_manager.device_index)
                logger.debug(f"Using device: {device_info['name']}")
            except Exception as e:
                logger.error(f"Invalid device index {self.device_manager.device_index}: {e}")
                # Try to get a valid device
                logger.debug("Attempting to find a valid device")
                self.device_manager.device_index = self.device_manager._get_device_index(force_refresh=True)
                if self.device_manager.device_index is None:
                    logger.error("Could not find a valid recording device")
                    self.recording = False
                    return
            
            # Check if device is a loopback device
            is_loopback = False
            if HAS_WASAPI and hasattr(self.audio, "is_loopback"):
                is_loopback = self.audio.is_loopback(self.device_manager.device_index)
            
            # Open stream
            logger.debug(f"Opening audio stream with device {self.device_manager.device_index}")
            self.stream = setup_audio_stream(
                self.audio, 
                self.device_manager.device_index, 
                self.config, 
                is_loopback
            )
            
            if self.stream is None:
                logger.error("Failed to open audio stream")
                self.recording = False
                return
            
            logger.info(f"Audio stream opened with device {self.device_manager.device_index}")
            
            # Record audio
            logger.debug("Starting audio recording loop")
            while self.recording:
                # Skip if paused
                if self.paused:
                    time.sleep(0.1)
                    continue
                
                # Read audio data
                try:
                    logger.debug("Reading audio chunk")
                    # Use a try-except block with a timeout to avoid hanging
                    try:
                        raw_data = self.stream.read(self.config["audio"]["chunk_size"])
                        logger.debug(f"Read {len(raw_data)} bytes of audio data")
                    except Exception as read_error:
                        logger.error(f"Error reading from stream: {read_error}")
                        time.sleep(0.1)
                        continue
                    
                    # Make a copy of the data immediately to avoid modifying the original
                    data = bytes(raw_data)
                    
                    # Convert to mono if needed
                    if self.config["audio"]["mono"] and self.config["audio"]["channels"] > 1:
                        mono_data = convert_to_mono(data, self.config["audio"]["channels"])
                        # Create a new bytes object to ensure it's completely separate
                        data = bytes(mono_data)
                    
                    # Create a completely new copy for visualization
                    viz_data = bytes(data)
                    
                    # Update visualization buffer with a new bytearray
                    new_viz_buffer = bytearray(self._viz_buffer)
                    new_viz_buffer.extend(viz_data)
                    if len(new_viz_buffer) > self._viz_buffer_size:
                        new_viz_buffer = new_viz_buffer[-int(self._viz_buffer_size):]
                    self._viz_buffer = new_viz_buffer
                    
                    # Add to queue (already a copy)
                    self.audio_queue.put(data)
                except Exception as e:
                    logger.error(f"Error reading audio data: {e}")
                    import traceback
                    logger.debug(f"Traceback: {traceback.format_exc()}")
                    time.sleep(0.1)
            
        except Exception as e:
            logger.error(f"Error in record thread: {e}")
            self.recording = False
        
        logger.info("Record thread finished") 
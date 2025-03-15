"""
Audio monitoring module for the Continuous Audio Recorder.
"""

import logging
import threading
import queue
import time
import numpy as np

# Get logger
logger = logging.getLogger("ContinuousRecorder")

class AudioMonitor:
    """Handles audio monitoring for the Continuous Audio Recorder."""
    
    def __init__(self, config):
        """Initialize the audio monitor.
        
        Args:
            config (dict): Configuration dictionary
        """
        self.config = config
        self.monitor_stream = None
        self.monitor_thread = None
        self.audio_queue = None
        self.audio = None
        self.recording = False
    
    def start_monitor(self, audio, audio_queue):
        """Start audio monitoring.
        
        Args:
            audio: PyAudio instance
            audio_queue: Queue for audio data
            
        Returns:
            bool: True if successful, False otherwise
        """
        if self.config["audio"]["monitor_level"] <= 0.0:
            return False
        
        self.audio = audio
        self.audio_queue = audio_queue
        self.recording = True
        
        try:
            # Open output stream
            self.monitor_stream = self.audio.open(
                format=self.audio.get_format_from_width(2),  # 16-bit
                channels=self.config["audio"]["channels"],
                rate=self.config["audio"]["sample_rate"],
                output=True,
                frames_per_buffer=self.config["audio"]["chunk_size"]
            )
            
            # Start monitor thread
            self.monitor_thread = threading.Thread(target=self._monitor_audio)
            self.monitor_thread.daemon = True
            self.monitor_thread.start()
            
            logger.debug("Audio monitoring started")
            return True
        except Exception as e:
            logger.error(f"Error starting audio monitor: {e}")
            return False
    
    def stop_monitor(self):
        """Stop audio monitoring.
        
        Returns:
            bool: True if successful, False otherwise
        """
        self.recording = False
        
        if self.monitor_stream is not None:
            try:
                self.monitor_stream.stop_stream()
                self.monitor_stream.close()
                self.monitor_stream = None
                logger.debug("Audio monitoring stopped")
                return True
            except Exception as e:
                logger.error(f"Error stopping audio monitor: {e}")
                return False
        return True
    
    def set_monitor_level(self, level):
        """Set audio monitoring level.
        
        Args:
            level (float): Level between 0.0 and 1.0
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            level = float(level)
            if level < 0.0 or level > 1.0:
                raise ValueError("Level must be between 0.0 and 1.0")
            
            self.config["audio"]["monitor_level"] = level
            
            # Update monitor if active
            if self.monitor_stream is not None:
                self.stop_monitor()
                if level > 0.0 and self.audio is not None and self.audio_queue is not None:
                    self.start_monitor(self.audio, self.audio_queue)
            
            return True
        except Exception as e:
            logger.error(f"Error setting monitor level: {e}")
            return False
    
    def _monitor_audio(self):
        """Monitor audio data for playback."""
        while self.monitor_stream is not None and self.recording:
            try:
                # Get data from queue
                if not self.audio_queue.empty():
                    data = self.audio_queue.get(block=False)
                    
                    # Apply volume
                    if self.config["audio"]["monitor_level"] > 0.0:
                        # Convert to numpy array
                        audio_data = np.frombuffer(data, dtype=np.int16)
                        
                        # Apply volume
                        audio_data = audio_data * self.config["audio"]["monitor_level"]
                        
                        # Convert back to bytes
                        data = audio_data.astype(np.int16).tobytes()
                        
                        # Play audio
                        self.monitor_stream.write(data)
            except queue.Empty:
                time.sleep(0.01)
            except Exception as e:
                logger.error(f"Error in audio monitor: {e}")
                time.sleep(0.1) 
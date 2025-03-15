"""
Audio level analyzer for the Continuous Audio Recorder.
Handles audio level calculation and visualization buffering.
"""

import time
import logging

from utils.audio_utils import calculate_audio_level

# Get logger
logger = logging.getLogger("ContinuousRecorder")

class AudioLevelAnalyzer:
    """Handles audio level calculation and visualization buffering."""
    
    def __init__(self):
        """Initialize the audio level analyzer."""
        # Level calculation cache
        self._last_level_calc = 0
        self._last_level_log = 0
        self._cached_level = (0, -60, 0)
    
    def get_audio_level(self, viz_buffer, recording=True):
        """Get the current audio level for visualization.
        
        Args:
            viz_buffer (bytearray or bytes): Audio data buffer for visualization
            recording (bool): Whether recording is in progress
            
        Returns:
            tuple: (rms, db, level) where:
                rms is the root mean square of the audio samples
                db is the decibel level (-60 to 0)
                level is the normalized level (0 to 1)
        """
        # Check if we're recording and have data
        if not recording or not viz_buffer or len(viz_buffer) == 0:
            logger.debug("Not recording or no visualization buffer available")
            return (0, -60, 0)
        
        # Check if we need to recalculate (cache results to avoid recalculating too often)
        current_time = time.time()
        if current_time - self._last_level_calc < 0.1:
            # Return cached value if it's recent enough
            return self._cached_level
        
        try:
            # Make a copy of the buffer to ensure we don't modify it
            buffer_copy = bytes(viz_buffer)
            
            # Calculate audio level
            logger.debug(f"Processing visualization buffer of size {len(buffer_copy)}")
            rms, db, level = calculate_audio_level(buffer_copy)
            
            # Debug log (only log occasionally to reduce spam)
            if current_time - self._last_level_log > 1.0:
                self._last_level_log = current_time
                if rms > 0:
                    logger.debug(f"Audio level: RMS={rms:.2f}, dB={db:.2f}, level={level:.2f}")
                else:
                    logger.debug("Audio level: silent (RMS=0)")
            
            # Cache the result
            self._last_level_calc = current_time
            self._cached_level = (rms, db, level)
            
            return (rms, db, level)
            
        except Exception as e:
            logger.error(f"Error getting audio level: {e}")
            import traceback
            logger.debug(f"Traceback: {traceback.format_exc()}")
            # Return safe default values
            return (0, -60, 0) 
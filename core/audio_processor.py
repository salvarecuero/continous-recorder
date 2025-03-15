"""
Audio processing for the Continuous Audio Recorder.
"""

import wave
import numpy as np
import logging

logger = logging.getLogger("ContinuousRecorder")

class AudioProcessor:
    """Processes audio data for recording and monitoring."""
    
    def __init__(self, config):
        """
        Initialize the audio processor.
        
        Args:
            config: Configuration manager instance
        """
        self.config = config
        self.sample_rate = self.config.get("audio", "sample_rate")
        self.channels = self.config.get("audio", "channels")
        self.mono = self.config.get("audio", "mono")
        self.monitor_level = self.config.get("audio", "monitor_level")
    
    def prepare_audio_data(self, audio_data):
        """
        Prepare audio data for recording.
        
        Args:
            audio_data: Raw audio data
            
        Returns:
            Processed audio data
        """
        # Convert to numpy array
        data = np.frombuffer(audio_data, dtype=np.int16)
        
        # Apply mono conversion if enabled
        if self.mono and self.channels > 1:
            # Reshape data to have channels as the second dimension
            data = data.reshape(-1, self.channels)
            
            # Average across channels
            data = np.mean(data, axis=1, dtype=np.int16)
            
            # Duplicate the mono channel to match the expected format
            data = np.repeat(data, self.channels)
        
        return data.tobytes()
    
    def mix_monitor_audio(self, audio_data):
        """
        Mix audio data for monitoring.
        
        Args:
            audio_data: Raw audio data
            
        Returns:
            Mixed audio data for monitoring
        """
        if self.monitor_level <= 0:
            return b''
        
        # Convert to numpy array
        data = np.frombuffer(audio_data, dtype=np.int16)
        
        # Apply volume scaling
        data = (data * self.monitor_level).astype(np.int16)
        
        return data.tobytes()
    
    def get_wave_params(self):
        """
        Get wave parameters for recording.
        
        Returns:
            Dictionary of wave parameters
        """
        return {
            'nchannels': 1 if self.mono else self.channels,
            'sampwidth': 2,  # 16-bit
            'framerate': self.sample_rate,
            'comptype': 'NONE',
            'compname': 'not compressed'
        }
    
    def create_wave_file(self, file_path):
        """
        Create a new wave file.
        
        Args:
            file_path: Path to the wave file
            
        Returns:
            Wave file object
        """
        wave_file = wave.open(file_path, 'wb')
        params = self.get_wave_params()
        wave_file.setparams((
            params['nchannels'],
            params['sampwidth'],
            params['framerate'],
            0,  # nframes (will be set as data is written)
            params['comptype'],
            params['compname']
        ))
        return wave_file
    
    def set_mono(self, mono):
        """
        Set mono mode.
        
        Args:
            mono: Boolean to enable/disable mono mode
        """
        self.mono = mono
        self.config.set("audio", "mono", mono)
    
    def set_monitor_level(self, level):
        """
        Set monitor level.
        
        Args:
            level: Float between 0.0 and 1.0
        """
        self.monitor_level = max(0.0, min(1.0, level))
        self.config.set("audio", "monitor_level", self.monitor_level) 
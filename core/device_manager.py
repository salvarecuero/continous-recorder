"""
Audio device management for the Continuous Audio Recorder.
"""

import logging
try:
    import pyaudiowpatch as pyaudio
    HAS_WASAPI = True
except ImportError:
    import pyaudio
    HAS_WASAPI = False

logger = logging.getLogger("ContinuousRecorder")

class DeviceManager:
    """Manages audio devices and provides device selection functionality."""
    
    def __init__(self):
        """Initialize the device manager."""
        self.audio = self._get_pyaudio_instance()
        self.devices = self.get_devices()
    
    def _get_pyaudio_instance(self):
        """Get a PyAudio instance."""
        return pyaudio.PyAudio()
    
    def get_devices(self):
        """
        Get a list of available audio devices.
        
        Returns:
            List of device dictionaries with name, index, and other properties
        """
        devices = []
        
        # Get device count
        device_count = self.audio.get_device_count()
        
        # Get default output device
        default_output = self.audio.get_default_output_device_info() if HAS_WASAPI else None
        default_output_index = default_output['index'] if default_output else -1
        
        # Iterate through devices
        for i in range(device_count):
            try:
                device_info = self.audio.get_device_info_by_index(i)
                
                # Skip input-only devices
                if device_info['maxOutputChannels'] == 0:
                    continue
                
                # Create device entry
                device = {
                    'index': device_info['index'],
                    'name': device_info['name'],
                    'channels': device_info['maxOutputChannels'],
                    'sample_rate': int(device_info['defaultSampleRate']),
                    'is_default': (device_info['index'] == default_output_index),
                    'is_loopback': False
                }
                
                # Add to devices list
                devices.append(device)
                
                # If WASAPI is available, add loopback device
                if HAS_WASAPI:
                    loopback_device = device.copy()
                    loopback_device['name'] = f"{device_info['name']} (Loopback)"
                    loopback_device['is_loopback'] = True
                    devices.append(loopback_device)
                
            except Exception as e:
                logger.warning(f"Error getting device info for index {i}: {e}")
        
        return devices
    
    def get_default_device(self):
        """
        Get the default output device.
        
        Returns:
            Device dictionary or None if no default device found
        """
        for device in self.devices:
            if device['is_default']:
                return device
        
        # If no default device found, return first device or None
        return self.devices[0] if self.devices else None
    
    def get_device_by_index(self, index):
        """
        Get a device by its index.
        
        Args:
            index: Device index
            
        Returns:
            Device dictionary or None if not found
        """
        for device in self.devices:
            if device['index'] == index:
                return device
        return None
    
    def refresh_devices(self):
        """Refresh the list of available devices."""
        self.devices = self.get_devices()
        return self.devices
    
    def close(self):
        """Close the PyAudio instance."""
        if self.audio:
            self.audio.terminate()
            self.audio = None 
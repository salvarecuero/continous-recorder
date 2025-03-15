"""
Device management module for the Continuous Audio Recorder.
"""

import logging
import queue
import threading
import time
import numpy as np

from utils.audio_utils import get_pyaudio_instance, list_audio_devices

# Check if WASAPI is available
try:
    import pyaudiowpatch as pyaudio
    HAS_WASAPI = True
except ImportError:
    import pyaudio
    HAS_WASAPI = False

# Get logger
logger = logging.getLogger("ContinuousRecorder")

class DeviceManager:
    """Manages audio devices for the Continuous Audio Recorder."""
    
    def __init__(self, config):
        """Initialize the device manager.
        
        Args:
            config (dict): Configuration dictionary
        """
        self.config = config
        self.device_index = self._get_device_index()
        logger.debug(f"Device index set to: {self.device_index}")
        
        # Cache for device validity and info
        self._device_valid_cache = {}
        self._device_info_cache = {}
        self._device_level_cache = {}
    
    def _get_device_index(self, force_refresh=False):
        """Get the index of the recording device."""
        logger.info(f"Getting device index (force_refresh={force_refresh})")
        
        # Use configured device if available
        if self.config["audio"]["device_index"] is not None and not force_refresh:
            logger.debug(f"Using configured device index: {self.config['audio']['device_index']}")
            # Validate the configured device
            try:
                logger.debug("Validating configured device")
                audio = self._get_pyaudio_instance()
                device_info = audio.get_device_info_by_index(self.config["audio"]["device_index"])
                logger.debug(f"Validated device: {device_info['name']}")
                audio.terminate()
                return self.config["audio"]["device_index"]
            except Exception as e:
                logger.warning(f"Configured device index {self.config['audio']['device_index']} is invalid: {e}")
                # Continue to find a new device
        
        # Get PyAudio instance
        logger.debug("Getting PyAudio instance")
        audio, has_wasapi = get_pyaudio_instance()
        logger.debug(f"Got PyAudio instance, WASAPI available: {has_wasapi}")
        
        # Find loopback device if WASAPI is available
        if has_wasapi:
            logger.debug("Searching for WASAPI loopback devices")
            try:
                # Get device count
                device_count = audio.get_device_count()
                logger.debug(f"Found {device_count} audio devices")
                
                # Find loopback device
                for i in range(device_count):
                    try:
                        logger.debug(f"Checking device {i}")
                        device_info = audio.get_device_info_by_index(i)
                        
                        # Check if device is a loopback device
                        logger.debug(f"Checking if device {i} is a loopback device")
                        if audio.is_loopback(i):
                            logger.debug(f"Device {i} is a loopback device: {device_info['name']}")
                            # Check if device is the default output device
                            try:
                                logger.debug("Checking if device is the default output device")
                                default_output = audio.get_default_output_device_info()
                                if device_info["name"] == default_output["name"]:
                                    logger.info(f"Using default output loopback device: {device_info['name']}")
                                    self.config["audio"]["device_index"] = i
                                    return i
                            except Exception as e:
                                logger.debug(f"Error checking default output: {e}")
                            
                            # Use first loopback device
                            logger.info(f"Using loopback device: {device_info['name']}")
                            self.config["audio"]["device_index"] = i
                            audio.terminate()
                            return i
                    except Exception as e:
                        logger.debug(f"Error checking device {i}: {e}")
                
                logger.debug("No suitable loopback devices found")
            except Exception as e:
                logger.error(f"Error finding loopback device: {e}")
        
        # Use default input device
        logger.debug("Trying to use default input device")
        try:
            device_info = audio.get_default_input_device_info()
            logger.info(f"Using default input device: {device_info['name']}")
            self.config["audio"]["device_index"] = device_info["index"]
            audio.terminate()
            return device_info["index"]
        except Exception as e:
            logger.error(f"Error getting default input device: {e}")
        
        # Try to find any available input device
        logger.debug("Searching for any available input device")
        try:
            device_count = audio.get_device_count()
            logger.debug(f"Found {device_count} audio devices")
            for i in range(device_count):
                try:
                    logger.debug(f"Checking input device {i}")
                    device_info = audio.get_device_info_by_index(i)
                    if device_info["maxInputChannels"] > 0:
                        logger.info(f"Using input device: {device_info['name']}")
                        self.config["audio"]["device_index"] = i
                        audio.terminate()
                        return i
                except Exception as e:
                    logger.debug(f"Error checking input device {i}: {e}")
            
            logger.debug("No suitable input devices found")
        except Exception as e:
            logger.error(f"Error finding any input device: {e}")
        
        # Clean up
        logger.debug("Terminating PyAudio instance")
        audio.terminate()
        
        logger.warning("No suitable recording device found")
        return None
    
    def set_device(self, device_index):
        """Set the recording device.
        
        Args:
            device_index (int): Index of the device to use
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Get PyAudio instance
            audio = self._get_pyaudio_instance()
            
            # Check if device exists
            device_info = audio.get_device_info_by_index(device_index)
            
            # Set device
            self.device_index = device_index
            self.config["audio"]["device_index"] = device_index
            
            # Clean up
            audio.terminate()
            
            logger.info(f"Recording device set to {device_info['name']}")
            return True
        except Exception as e:
            logger.error(f"Error setting device: {e}")
            return False
    
    def list_devices(self):
        """List available audio devices and return them.
        
        Returns:
            list: List of available audio devices
        """
        # Get PyAudio instance
        audio, has_wasapi = get_pyaudio_instance()
        
        # Get devices
        devices = list_audio_devices(audio)
        
        # Print devices
        print("\nAvailable Audio Devices:")
        print("------------------------")
        for device in devices:
            default = " (Default)" if device.get("is_default", False) else ""
            loopback = " (Loopback)" if device.get("is_loopback", False) else ""
            print(f"Index: {device['index']}, Name: {device['name']}{default}{loopback}")
        print()
        
        # Clean up
        audio.terminate()
        
        return devices
    
    def is_device_valid(self, device_index=None):
        """Check if the device is valid and available.
        
        This method will check if the device is valid by:
        1. Checking if the device index is valid
        2. Checking if the device info can be retrieved
        3. Checking if a stream can be opened
        4. Checking if data can be read from the stream
        
        Args:
            device_index (int, optional): Device index to check. Defaults to None (current device).
            
        Returns:
            bool: True if the device is valid, False otherwise
        """
        # Use current device if not specified
        if device_index is None:
            device_index = self.device_index
        
        # Check if device index is valid
        if device_index is None:
            logger.debug("No device selected")
            return False
            
        # Cache device validity results to avoid frequent checks
        cache_key = f"device_valid_{device_index}"
        current_time = time.time()
        
        # If we have a cached result that's less than 5 seconds old, use it
        if cache_key in self._device_valid_cache and current_time - self._device_valid_cache[f"{cache_key}_time"] < 5.0:
            return self._device_valid_cache[cache_key]
        
        # Use a queue to get the result from the thread
        result_queue = queue.Queue()
        
        # Define the thread function
        def _check_device_thread():
            try:
                # Get PyAudio instance
                audio, has_wasapi = get_pyaudio_instance()
                
                # Try to get device info
                try:
                    device_info = audio.get_device_info_by_index(device_index)
                except Exception as e:
                    logger.error(f"Error getting device info: {e}")
                    result_queue.put(False)
                    audio.terminate()
                    return
                
                # Try to open a stream
                stream = None
                try:
                    stream = audio.open(
                        format=pyaudio.paInt16,
                        channels=int(device_info["maxInputChannels"]),
                        rate=int(device_info["defaultSampleRate"]),
                        input=True,
                        frames_per_buffer=1024,
                        input_device_index=device_index
                    )
                except Exception as e:
                    logger.error(f"Error opening stream: {e}")
                    result_queue.put(False)
                    audio.terminate()
                    return
                
                # Try to read data
                try:
                    data = stream.read(1024, exception_on_overflow=False)
                except Exception as e:
                    logger.error(f"Error reading data: {e}")
                    try:
                        stream.close()
                    except:
                        pass
                    audio.terminate()
                    result_queue.put(False)
                    return
                
                # Close stream
                try:
                    stream.close()
                except Exception as e:
                    logger.error(f"Error closing stream: {e}")
                
                # Terminate PyAudio
                try:
                    audio.terminate()
                except Exception as e:
                    logger.error(f"Error terminating PyAudio: {e}")
                
                # Device is valid
                result_queue.put(True)
            except Exception as e:
                logger.error(f"Unexpected error in _check_device_thread: {e}")
                # Make sure we always put something in the queue
                result_queue.put(False)
        
        # Start the thread
        thread = threading.Thread(target=_check_device_thread)
        thread.daemon = True
        thread.start()
        
        try:
            # Wait for the result with a timeout
            result = result_queue.get(timeout=2)
            
            # Cache the result
            self._device_valid_cache[cache_key] = result
            self._device_valid_cache[f"{cache_key}_time"] = current_time
            
            return result
        except queue.Empty:
            logger.warning("Timeout checking device validity")
            
            # Cache the result
            self._device_valid_cache[cache_key] = False
            self._device_valid_cache[f"{cache_key}_time"] = current_time
            
            return False
        except Exception as e:
            logger.error(f"Error getting result from queue: {e}")
            
            # Cache the result
            self._device_valid_cache[cache_key] = False
            self._device_valid_cache[f"{cache_key}_time"] = current_time
            
            return False
    
    def find_working_device(self):
        """Find a working audio device and switch to it.
        
        This method will try all available devices until it finds one that works.
        
        Returns:
            bool: True if a working device was found and set, False otherwise
        """
        logger.info("Searching for a working audio device")
        
        # Get PyAudio instance
        try:
            audio, has_wasapi = get_pyaudio_instance()
        except Exception as e:
            logger.error(f"Error getting PyAudio instance: {e}")
            return False
        
        # Get device count
        try:
            device_count = audio.get_device_count()
            logger.info(f"Found {device_count} audio devices")
        except Exception as e:
            logger.error(f"Error getting device count: {e}")
            audio.terminate()
            return False
        
        # Try each device
        current_device = self.device_index
        for i in range(device_count):
            # Skip current device if it's the one that failed
            if i == current_device:
                continue
            
            # Check if device is valid
            if self.is_device_valid(i):
                try:
                    # Get device info
                    device_info = audio.get_device_info_by_index(i)
                    logger.info(f"Found working device: {device_info['name']} (index {i})")
                    
                    # Set device
                    self.device_index = i
                    self.config["audio"]["device_index"] = i
                    
                    # Clean up
                    audio.terminate()
                    
                    return True
                except Exception as e:
                    logger.error(f"Error setting device {i}: {e}")
        
        # Clean up
        audio.terminate()
        
        logger.warning("No working audio devices found")
        return False
    
    def get_device_info(self):
        """Get information about the current device.
        
        Returns:
            dict: Device information or None if the device is invalid
        """
        # Cache device info results to avoid frequent checks
        cache_key = f"device_info_{self.device_index}"
        current_time = time.time()
        
        # If we have a cached result that's less than 5 seconds old, use it
        if cache_key in self._device_info_cache and current_time - self._device_info_cache[f"{cache_key}_time"] < 5.0:
            return self._device_info_cache[cache_key]
            
        try:
            # Get PyAudio instance
            audio, has_wasapi = get_pyaudio_instance()
            
            # Get device info
            device_info = audio.get_device_info_by_index(self.device_index)
            
            # Clean up
            audio.terminate()
            
            # Cache the result
            self._device_info_cache[cache_key] = device_info
            self._device_info_cache[f"{cache_key}_time"] = current_time
            
            return device_info
        except Exception as e:
            logger.error(f"Error getting device info: {e}")
            
            # Cache the result
            self._device_info_cache[cache_key] = None
            self._device_info_cache[f"{cache_key}_time"] = current_time
            
            return None
    
    def get_device_level(self):
        """Get the current audio level from the device.
        
        This method will attempt to get the audio level from the device.
        If the device is not available or there is an error, it will return 0.
        
        Returns:
            float: Audio level from 0 to 1
        """
        # Cache device level results to avoid frequent checks
        cache_key = "device_level"
        current_time = time.time()
        
        # If we have a cached result that's less than 0.1 seconds old, use it
        if cache_key in self._device_level_cache and current_time - self._device_level_cache[f"{cache_key}_time"] < 0.1:
            return self._device_level_cache[cache_key]
            
        # Use a queue to get the result from the thread
        result_queue = queue.Queue()
        
        # Define the thread function
        def _get_level_thread():
            try:
                # Get PyAudio instance
                audio, has_wasapi = get_pyaudio_instance()
                
                # Get device info
                try:
                    device_info = audio.get_device_info_by_index(self.device_index)
                except Exception as e:
                    logger.error(f"Error getting device info: {e}")
                    result_queue.put(0)
                    audio.terminate()
                    return
                
                # Open stream
                try:
                    stream = audio.open(
                        format=pyaudio.paInt16,
                        channels=int(device_info["maxInputChannels"]),
                        rate=int(device_info["defaultSampleRate"]),
                        input=True,
                        frames_per_buffer=1024,
                        input_device_index=self.device_index
                    )
                except Exception as e:
                    logger.error(f"Error opening stream: {e}")
                    result_queue.put(0)
                    audio.terminate()
                    return
                
                # Read data
                try:
                    data = stream.read(1024, exception_on_overflow=False)
                except Exception as e:
                    logger.error(f"Error reading data: {e}")
                    try:
                        stream.close()
                    except:
                        pass
                    audio.terminate()
                    result_queue.put(0)
                    return
                
                # Close stream
                try:
                    stream.close()
                except Exception as e:
                    logger.error(f"Error closing stream: {e}")
                
                # Terminate PyAudio
                try:
                    audio.terminate()
                except Exception as e:
                    logger.error(f"Error terminating PyAudio: {e}")
                
                # Convert to numpy array
                try:
                    audio_data = np.frombuffer(data, dtype=np.int16)
                except Exception as e:
                    logger.error(f"Error converting to numpy array: {e}")
                    result_queue.put(0)
                    return
                
                # Convert to mono if needed
                try:
                    if len(audio_data) == 0:
                        logger.warning("Empty audio data")
                        result_queue.put(0)
                        return
                    
                    channels = int(device_info["maxInputChannels"])
                    if channels > 1:
                        # Reshape and average across channels
                        audio_data = audio_data.reshape(-1, channels)
                        audio_data = np.mean(audio_data, axis=1)
                except Exception as e:
                    logger.error(f"Error converting to mono: {e}")
                    result_queue.put(0)
                    return
                
                # Calculate RMS
                try:
                    rms = np.sqrt(np.mean(np.square(audio_data)))
                except Exception as e:
                    logger.error(f"Error calculating RMS: {e}")
                    result_queue.put(0)
                    return
                
                # Convert to dB and normalize to 0-1 range
                try:
                    if rms > 0:
                        db = 20 * np.log10(rms / 32767)
                        # Normalize to 0-1 range (assuming -60dB to 0dB range)
                        level = (db + 60) / 60
                        level = max(0, min(1, level))
                    else:
                        level = 0
                except Exception as e:
                    logger.error(f"Error converting to dB: {e}")
                    result_queue.put(0)
                    return
                
                # Put the result in the queue
                result_queue.put(level)
            except Exception as e:
                logger.error(f"Unexpected error in _get_level_thread: {e}")
                # Make sure we always put something in the queue
                result_queue.put(0)
        
        # Start the thread
        thread = threading.Thread(target=_get_level_thread)
        thread.daemon = True
        thread.start()
        
        try:
            # Wait for the result with a timeout
            level = result_queue.get(timeout=2)
            
            # Cache the result
            self._device_level_cache[cache_key] = level
            self._device_level_cache[f"{cache_key}_time"] = current_time
            
            return level
        except queue.Empty:
            logger.warning("Timeout getting device level")
            
            # Cache the result
            self._device_level_cache[cache_key] = 0
            self._device_level_cache[f"{cache_key}_time"] = current_time
            
            return 0
        except Exception as e:
            logger.error(f"Error getting result from queue: {e}")
            
            # Cache the result
            self._device_level_cache[cache_key] = 0
            self._device_level_cache[f"{cache_key}_time"] = current_time
            
            return 0
    
    def _get_pyaudio_instance(self):
        """Get a PyAudio instance."""
        logger.debug("Getting PyAudio instance")
        try:
            audio, _ = get_pyaudio_instance()
            logger.debug("PyAudio instance created successfully")
            return audio
        except Exception as e:
            logger.error(f"Error creating PyAudio instance: {e}")
            raise 
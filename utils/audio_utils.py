"""
Audio utility functions for the Continuous Audio Recorder.
"""

import os
import subprocess
import logging

logger = logging.getLogger("ContinuousRecorder")

def get_pyaudio_instance():
    """Get a PyAudio instance with WASAPI support if available."""
    logger.debug("Attempting to get PyAudio instance")
    try:
        logger.debug("Trying to import pyaudiowpatch")
        try:
            import pyaudiowpatch as pyaudio
            logger.debug("Successfully imported pyaudiowpatch")
            try:
                logger.debug("Creating PyAudio instance with WASAPI support - STEP 1")
                logger.debug("Calling pyaudio.PyAudio() constructor")
                
                # Use a timeout mechanism to prevent hanging
                import threading
                import queue
                
                def create_pyaudio():
                    try:
                        result_queue.put((pyaudio.PyAudio(), None))
                    except Exception as e:
                        result_queue.put((None, e))
                
                result_queue = queue.Queue()
                thread = threading.Thread(target=create_pyaudio)
                thread.daemon = True
                thread.start()
                
                # Wait for result with timeout
                try:
                    result, error = result_queue.get(timeout=5.0)  # 5 second timeout
                    if error:
                        raise error
                    if result is None:
                        raise Exception("Failed to create PyAudio instance (unknown error)")
                    
                    logger.debug("Successfully created PyAudio instance with WASAPI support")
                    return result, True
                except queue.Empty:
                    logger.error("Timeout while creating PyAudio instance with WASAPI")
                    raise Exception("Timeout while creating PyAudio instance")
                
            except Exception as e:
                logger.error(f"Error creating PyAudio instance with WASAPI: {e}")
                import traceback
                logger.error(f"Traceback: {traceback.format_exc()}")
                raise
        except ImportError as e:
            logger.debug(f"pyaudiowpatch not available: {e}, falling back to standard pyaudio")
            try:
                logger.debug("Importing standard pyaudio")
                import pyaudio
                logger.debug("Successfully imported standard pyaudio")
                try:
                    logger.debug("Creating standard PyAudio instance - STEP 1")
                    logger.debug("Calling pyaudio.PyAudio() constructor")
                    
                    # Use a timeout mechanism to prevent hanging
                    import threading
                    import queue
                    
                    def create_pyaudio():
                        try:
                            result_queue.put((pyaudio.PyAudio(), None))
                        except Exception as e:
                            result_queue.put((None, e))
                    
                    result_queue = queue.Queue()
                    thread = threading.Thread(target=create_pyaudio)
                    thread.daemon = True
                    thread.start()
                    
                    # Wait for result with timeout
                    try:
                        result, error = result_queue.get(timeout=5.0)  # 5 second timeout
                        if error:
                            raise error
                        if result is None:
                            raise Exception("Failed to create PyAudio instance (unknown error)")
                        
                        logger.debug("Successfully created standard PyAudio instance")
                        return result, False
                    except queue.Empty:
                        logger.error("Timeout while creating standard PyAudio instance")
                        raise Exception("Timeout while creating PyAudio instance")
                    
                except Exception as e:
                    logger.error(f"Error creating standard PyAudio instance: {e}")
                    import traceback
                    logger.error(f"Traceback: {traceback.format_exc()}")
                    raise
            except ImportError as e:
                logger.error(f"Failed to import pyaudio: {e}")
                import traceback
                logger.error(f"Traceback: {traceback.format_exc()}")
                raise
    except Exception as e:
        logger.error(f"Unexpected error in get_pyaudio_instance: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise

def list_audio_devices(audio_instance):
    """List all available audio devices."""
    devices = []
    
    # Get device count
    device_count = audio_instance.get_device_count()
    
    # Get default device
    try:
        default_device = audio_instance.get_default_input_device_info()
        default_index = default_device["index"]
    except:
        default_index = -1
    
    # Iterate through devices
    for i in range(device_count):
        try:
            device_info = audio_instance.get_device_info_by_index(i)
            
            # Check if device is an input device
            if device_info["maxInputChannels"] > 0:
                # Check if device is a loopback device
                is_loopback = False
                if hasattr(audio_instance, "is_loopback"):
                    is_loopback = audio_instance.is_loopback(i)
                
                # Add device to list
                devices.append({
                    "index": i,
                    "name": device_info["name"],
                    "channels": device_info["maxInputChannels"],
                    "sample_rate": int(device_info["defaultSampleRate"]),
                    "is_default": i == default_index,
                    "is_loopback": is_loopback
                })
        except:
            pass
    
    return devices

def convert_to_mp3(wav_file, ffmpeg_path="ffmpeg", quality="high"):
    """Convert WAV file to MP3 format."""
    # Determine quality settings
    quality_settings = {
        "high": "-b:a 320k",
        "medium": "-b:a 192k",
        "low": "-b:a 128k"
    }
    
    quality_param = quality_settings.get(quality, quality_settings["high"])
    
    # Create output file path
    mp3_file = os.path.splitext(wav_file)[0] + ".mp3"
    
    # Build command
    cmd = f'"{ffmpeg_path}" -y -i "{wav_file}" {quality_param} "{mp3_file}"'
    
    try:
        # Run command
        subprocess.run(cmd, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        # Delete WAV file if conversion successful
        if os.path.exists(mp3_file):
            os.remove(wav_file)
            return mp3_file
    except subprocess.CalledProcessError as e:
        logger.error(f"Error converting to MP3: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error during conversion: {e}")
        return None

def convert_to_mono(audio_data, channels):
    """Convert multi-channel audio data to mono.
    
    Args:
        audio_data (bytes): Raw audio data
        channels (int): Number of channels in the audio data
        
    Returns:
        bytes: Mono audio data
    """
    if channels <= 1:
        return bytes(audio_data)
        
    import numpy as np
    
    # Make a copy to ensure we don't modify the original data
    data_copy = bytes(audio_data)
    
    # Convert to numpy array
    samples = np.frombuffer(data_copy, dtype=np.int16).copy()
    
    # Reshape to channels
    samples = samples.reshape(-1, channels)
    
    # Average channels
    mono_samples = np.mean(samples, axis=1, dtype=np.int16)
    
    # Convert back to bytes
    return mono_samples.tobytes()

def calculate_audio_level(audio_data):
    """Calculate audio level metrics from raw audio data.
    
    Args:
        audio_data (bytes): Raw audio data (16-bit PCM)
        
    Returns:
        tuple: (rms, db, level) where:
            rms is the root mean square of the audio samples
            db is the decibel level (-60 to 0)
            level is the normalized level (0 to 1)
    """
    import numpy as np
    
    # Make a copy to ensure we don't modify the original data
    data_copy = bytes(audio_data)
    
    # Convert to numpy array
    samples = np.frombuffer(data_copy, dtype=np.int16).copy()
    
    if len(samples) == 0:
        return (0, -60, 0)
    
    # Calculate RMS value
    rms = np.sqrt(np.mean(samples.astype(np.float32)**2))
    
    # Convert to dB (relative to full scale)
    if rms > 0:
        db = 20 * np.log10(rms / 32768)
        db = max(-60, min(0, db))  # Clamp between -60 and 0 dB
        
        # Convert to 0-1 range for meter
        level = (db + 60) / 60
        
        return (rms, db, level)
    
    # Silent case
    return (0, -60, 0)

def setup_audio_stream(audio, device_index, config, is_loopback=False):
    """Set up an audio input stream with the given configuration.
    
    Args:
        audio: PyAudio instance
        device_index (int): Device index to use
        config (dict): Configuration dictionary with audio settings
        is_loopback (bool): Whether to use WASAPI loopback mode
        
    Returns:
        stream: PyAudio stream object or None if failed
    """
    import logging
    logger = logging.getLogger("ContinuousRecorder")
    
    # Check if WASAPI is available
    has_wasapi = False
    try:
        import pyaudiowpatch
        has_wasapi = True
        pyaudio = pyaudiowpatch
    except ImportError:
        import pyaudio as pyaudio_std
        has_wasapi = False
        pyaudio = pyaudio_std
    
    try:
        if has_wasapi and is_loopback:
            # Open loopback stream
            logger.debug("Opening WASAPI loopback stream")
            stream = audio.open(
                format=pyaudio.paInt16,
                channels=config["audio"]["channels"],
                rate=config["audio"]["sample_rate"],
                frames_per_buffer=config["audio"]["chunk_size"],
                input=True,
                input_device_index=device_index,
                as_loopback=True
            )
            logger.debug("WASAPI loopback stream opened successfully")
        else:
            # Open regular stream
            logger.debug("Opening regular input stream")
            stream = audio.open(
                format=pyaudio.paInt16,
                channels=config["audio"]["channels"],
                rate=config["audio"]["sample_rate"],
                frames_per_buffer=config["audio"]["chunk_size"],
                input=True,
                input_device_index=device_index
            )
            logger.debug("Regular input stream opened successfully")
        
        return stream
    except Exception as e:
        logger.error(f"Failed to open audio stream: {e}")
        return None 
"""
Audio utility functions for the Continuous Audio Recorder.
"""

import os
import subprocess
import logging

logger = logging.getLogger("ContinuousRecorder")

def get_pyaudio_instance():
    """Get a PyAudio instance with WASAPI support if available."""
    try:
        import pyaudiowpatch as pyaudio
        return pyaudio.PyAudio(), True
    except ImportError:
        import pyaudio
        return pyaudio.PyAudio(), False

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
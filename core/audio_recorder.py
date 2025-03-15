"""
Core audio recorder module for the Continuous Audio Recorder.
"""

import os
import sys
import time
import queue
import signal
import atexit
import logging
import threading
import datetime
import numpy as np
import wave

from config.settings import load_config, save_config
from utils.audio_utils import get_pyaudio_instance, list_audio_devices, convert_to_mp3
from utils.file_utils import create_file_path, cleanup_old_recordings, setup_autostart

# Get logger
logger = logging.getLogger("ContinuousRecorder")

# Check if WASAPI is available
try:
    import pyaudiowpatch as pyaudio
    HAS_WASAPI = True
except ImportError:
    import pyaudio
    HAS_WASAPI = False

class AudioRecorder:
    """Main class for handling continuous audio recording from system output."""
    
    def __init__(self, config_path="config.ini"):
        """Initialize the recorder with configuration."""
        self.config = load_config(config_path)
        self.config_path = config_path
        self.recording = False
        self.paused = False
        self.audio = None
        self.stream = None
        self.current_file = None
        self.current_wave = None
        self.audio_queue = queue.Queue()
        self.record_thread = None
        self.process_thread = None
        self.cleanup_thread = None
        self.device_index = self._get_device_index()
        self.pid = os.getpid()
        self.monitor_stream = None
        self.monitor_thread = None
        self.current_block_size = 0  # Track current block size
        
        # Create base recordings directory
        os.makedirs(self.config["paths"]["recordings_dir"], exist_ok=True)
        
        # Register signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        # Register cleanup function
        atexit.register(self._cleanup_lock)
        
        # Display current configuration
        self.display_configuration()
    
    def _save_config(self):
        """Save configuration to file."""
        result = save_config(self.config, self.config_path)
        if result:
            # Display updated configuration
            self.display_configuration()
        return result
    
    def list_devices(self):
        """List available audio devices and return them."""
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
    
    def set_audio_quality(self, quality):
        """Set audio quality for MP3 conversion."""
        if quality not in ["high", "medium", "low"]:
            logger.error(f"Invalid quality setting: {quality}")
            return False
        
        self.config["audio"]["quality"] = quality
        self._save_config()
        return True
    
    def set_mono(self, mono):
        """Set mono/stereo recording mode."""
        self.config["audio"]["mono"] = bool(mono)
        self._save_config()
        return True
    
    def set_monitor_level(self, level):
        """Set audio monitoring level."""
        try:
            level = float(level)
            if level < 0.0 or level > 1.0:
                raise ValueError("Level must be between 0.0 and 1.0")
            
            self.config["audio"]["monitor_level"] = level
            self._save_config()
            
            # Update monitor if active
            if self.monitor_stream is not None:
                self._stop_monitor()
                self._start_monitor()
            
            return True
        except Exception as e:
            logger.error(f"Error setting monitor level: {e}")
            return False
    
    def _start_monitor(self):
        """Start audio monitoring."""
        if self.config["audio"]["monitor_level"] <= 0.0:
            return
        
        try:
            # Get PyAudio instance
            if self.audio is None:
                self.audio = self._get_pyaudio_instance()
            
            # Open output stream
            self.monitor_stream = self.audio.open(
                format=pyaudio.paInt16,
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
        except Exception as e:
            logger.error(f"Error starting audio monitor: {e}")
    
    def _stop_monitor(self):
        """Stop audio monitoring."""
        if self.monitor_stream is not None:
            try:
                self.monitor_stream.stop_stream()
                self.monitor_stream.close()
                self.monitor_stream = None
                logger.debug("Audio monitoring stopped")
            except Exception as e:
                logger.error(f"Error stopping audio monitor: {e}")
    
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
    
    def start_recording(self):
        """Start the recording process."""
        if self.recording:
            logger.warning("Recording is already in progress")
            return False
        
        # Check if another instance is already recording
        if self._check_lock():
            logger.error("Another instance is already recording")
            return False
        
        # Create lock file
        self._create_lock()
        
        # Initialize PyAudio
        if self.audio is None:
            self.audio = self._get_pyaudio_instance()
        
        # Display current configuration
        self.display_configuration()
        
        # Start recording
        self.recording = True
        self.paused = False
        
        # Start record thread
        self.record_thread = threading.Thread(target=self._record_audio)
        self.record_thread.daemon = True
        self.record_thread.start()
        
        # Start process thread
        self.process_thread = threading.Thread(target=self._process_audio)
        self.process_thread.daemon = True
        self.process_thread.start()
        
        # Start cleanup thread
        self.cleanup_thread = threading.Thread(target=self._run_cleanup_thread)
        self.cleanup_thread.daemon = True
        self.cleanup_thread.start()
        
        # Start monitor
        self._start_monitor()
        
        logger.info("Recording started")
        return True
    
    def stop_recording(self):
        """Stop the recording process."""
        if not self.recording:
            logger.warning("Recording is not in progress")
            return False
        
        # Stop recording
        self.recording = False
        
        # Stop monitor
        self._stop_monitor()
        
        # Wait for threads to finish
        if self.record_thread is not None:
            self.record_thread.join(timeout=2.0)
            self.record_thread = None
        
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
        
        # Clean up PyAudio
        if self.audio is not None:
            try:
                self.audio.terminate()
                self.audio = None
            except Exception as e:
                logger.error(f"Error terminating PyAudio: {e}")
        
        # Remove lock file
        self._cleanup_lock()
        
        logger.info("Recording stopped")
        return True
    
    def pause_recording(self):
        """Pause the recording process."""
        if not self.recording:
            logger.warning("Recording is not in progress")
            return False
        
        self.paused = True
        logger.info("Recording paused")
        return True
    
    def resume_recording(self):
        """Resume the recording process."""
        if not self.recording:
            logger.warning("Recording is not in progress")
            return False
        
        self.paused = False
        logger.info("Recording resumed")
        return True
    
    def get_status(self):
        """Get the current status of the recorder."""
        status = {
            "recording": self.recording,
            "paused": self.paused,
            "device_index": self.device_index,
            "device_name": "Unknown",
            "sample_rate": self.config["audio"]["sample_rate"],
            "channels": self.config["audio"]["channels"],
            "format": self.config["audio"]["format"],
            "quality": self.config["audio"]["quality"],
            "mono": self.config["audio"]["mono"],
            "monitor_level": self.config["audio"]["monitor_level"],
            "current_file": self.current_file,
            "recordings_dir": self.config["paths"]["recordings_dir"],
            "retention_days": self.config["general"]["retention_days"],
            "recording_hours": self.config["general"]["recording_hours"],
            "current_block_size": self.get_current_block_size(),
            "estimated_90day_size": self.calculate_90day_size(),
            "estimated_day_size": self.calculate_day_size(),
            "estimated_block_size": self.calculate_block_size(),
            "recordings_folder_size": self.get_recordings_folder_size(),
            "free_disk_space": self.get_free_disk_space(),
            "retention_fit": self.would_retention_fit()  # Always include retention fit info
        }
        
        # Get device name
        if self.device_index is not None:
            try:
                audio = self._get_pyaudio_instance()
                device_info = audio.get_device_info_by_index(self.device_index)
                status["device_name"] = device_info["name"]
                audio.terminate()
            except:
                pass
        
        return status
    
    def _get_device_index(self):
        """Get the index of the recording device."""
        # Use configured device if available
        if self.config["audio"]["device_index"] is not None:
            return self.config["audio"]["device_index"]
        
        # Get PyAudio instance
        audio, has_wasapi = get_pyaudio_instance()
        
        # Find loopback device if WASAPI is available
        if has_wasapi:
            try:
                # Get device count
                device_count = audio.get_device_count()
                
                # Find loopback device
                for i in range(device_count):
                    try:
                        device_info = audio.get_device_info_by_index(i)
                        
                        # Check if device is a loopback device
                        if audio.is_loopback(i):
                            # Check if device is the default output device
                            try:
                                default_output = audio.get_default_output_device_info()
                                if device_info["name"] == default_output["name"]:
                                    logger.info(f"Using default output loopback device: {device_info['name']}")
                                    self.config["audio"]["device_index"] = i
                                    self._save_config()
                                    audio.terminate()
                                    return i
                            except:
                                pass
                            
                            # Use first loopback device
                            logger.info(f"Using loopback device: {device_info['name']}")
                            self.config["audio"]["device_index"] = i
                            self._save_config()
                            audio.terminate()
                            return i
                    except:
                        pass
            except Exception as e:
                logger.error(f"Error finding loopback device: {e}")
        
        # Use default input device
        try:
            device_info = audio.get_default_input_device_info()
            logger.info(f"Using default input device: {device_info['name']}")
            self.config["audio"]["device_index"] = device_info["index"]
            self._save_config()
            audio.terminate()
            return device_info["index"]
        except:
            pass
        
        # Clean up
        audio.terminate()
        
        logger.warning("No suitable recording device found")
        return None
    
    def set_device(self, device_index):
        """Set the recording device."""
        try:
            # Get PyAudio instance
            audio = self._get_pyaudio_instance()
            
            # Check if device exists
            device_info = audio.get_device_info_by_index(device_index)
            
            # Set device
            self.device_index = device_index
            self.config["audio"]["device_index"] = device_index
            self._save_config()
            
            # Clean up
            audio.terminate()
            
            logger.info(f"Recording device set to {device_info['name']}")
            return True
        except Exception as e:
            logger.error(f"Error setting device: {e}")
            return False
    
    def _get_pyaudio_instance(self):
        """Get a PyAudio instance."""
        audio, _ = get_pyaudio_instance()
        return audio
    
    def _signal_handler(self, sig, frame):
        """Handle signals for graceful shutdown."""
        logger.info(f"Signal {sig} received, stopping recording")
        self.stop_recording()
        sys.exit(0)
    
    def _check_lock(self):
        """Check if another instance is already recording."""
        # Get lock file path
        lock_file = os.path.join(os.path.dirname(os.path.abspath(self.config_path)), ".recorder.lock")
        
        # Check if lock file exists
        if os.path.exists(lock_file):
            try:
                # Read lock file
                with open(lock_file, "r") as f:
                    pid = int(f.read().strip())
                
                # Check if process is running
                if pid == self.pid:
                    # This is our lock file
                    return False
                
                # Check if process exists
                try:
                    os.kill(pid, 0)
                    # Process exists
                    return True
                except OSError:
                    # Process doesn't exist
                    logger.warning(f"Removing stale lock file for PID {pid}")
                    os.remove(lock_file)
                    return False
            except Exception as e:
                logger.error(f"Error checking lock file: {e}")
                # Remove lock file
                try:
                    os.remove(lock_file)
                except:
                    pass
                return False
        
        return False
    
    def _create_lock(self):
        """Create a lock file to prevent multiple instances."""
        # Get lock file path
        lock_file = os.path.join(os.path.dirname(os.path.abspath(self.config_path)), ".recorder.lock")
        
        # Create lock file
        try:
            with open(lock_file, "w") as f:
                f.write(str(self.pid))
            logger.debug(f"Created lock file with PID {self.pid}")
        except Exception as e:
            logger.error(f"Error creating lock file: {e}")
    
    def _cleanup_lock(self):
        """Remove the lock file."""
        # Get lock file path
        lock_file = os.path.join(os.path.dirname(os.path.abspath(self.config_path)), ".recorder.lock")
        
        # Check if lock file exists
        if os.path.exists(lock_file):
            try:
                # Read lock file
                with open(lock_file, "r") as f:
                    pid = int(f.read().strip())
                
                # Check if this is our lock file
                if pid == self.pid:
                    # Remove lock file
                    os.remove(lock_file)
                    logger.debug(f"Removed lock file for PID {self.pid}")
            except Exception as e:
                logger.error(f"Error removing lock file: {e}")
    
    def _send_command(self, command):
        """Send a command to another instance."""
        # Get command file path
        cmd_file = os.path.join(os.path.dirname(os.path.abspath(self.config_path)), ".recorder.cmd")
        
        # Create command file
        try:
            with open(cmd_file, "w") as f:
                f.write(command)
            logger.debug(f"Sent command: {command}")
            return True
        except Exception as e:
            logger.error(f"Error sending command: {e}")
            return False
    
    def _check_command(self):
        """Check for commands from other instances."""
        # Get command file path
        cmd_file = os.path.join(os.path.dirname(os.path.abspath(self.config_path)), ".recorder.cmd")
        
        # Check if command file exists
        if os.path.exists(cmd_file):
            try:
                # Read command file
                with open(cmd_file, "r") as f:
                    command = f.read().strip()
                
                # Remove command file
                os.remove(cmd_file)
                
                # Process command
                if command == "stop":
                    logger.info("Received stop command")
                    self.stop_recording()
                elif command == "pause":
                    logger.info("Received pause command")
                    self.paused = True
                elif command == "resume":
                    logger.info("Received resume command")
                    self.paused = False
                
                return command
            except Exception as e:
                logger.error(f"Error checking command: {e}")
        
        return None
    
    def _record_audio(self):
        """Record audio from the selected device."""
        try:
            # Open stream
            if HAS_WASAPI and hasattr(self.audio, "is_loopback") and self.audio.is_loopback(self.device_index):
                # Open loopback stream
                self.stream = self.audio.open(
                    format=pyaudio.paInt16,
                    channels=self.config["audio"]["channels"],
                    rate=self.config["audio"]["sample_rate"],
                    frames_per_buffer=self.config["audio"]["chunk_size"],
                    input=True,
                    input_device_index=self.device_index,
                    as_loopback=True
                )
            else:
                # Open regular stream
                self.stream = self.audio.open(
                    format=pyaudio.paInt16,
                    channels=self.config["audio"]["channels"],
                    rate=self.config["audio"]["sample_rate"],
                    frames_per_buffer=self.config["audio"]["chunk_size"],
                    input=True,
                    input_device_index=self.device_index
                )
            
            logger.debug(f"Opened audio stream with device {self.device_index}")
            
            # Record audio
            while self.recording:
                # Check for commands
                self._check_command()
                
                # Skip if paused
                if self.paused:
                    time.sleep(0.1)
                    continue
                
                # Read audio data
                try:
                    data = self.stream.read(self.config["audio"]["chunk_size"])
                    
                    # Convert to mono if needed
                    if self.config["audio"]["mono"] and self.config["audio"]["channels"] > 1:
                        # Convert to numpy array
                        audio_data = np.frombuffer(data, dtype=np.int16)
                        
                        # Reshape to channels
                        audio_data = audio_data.reshape(-1, self.config["audio"]["channels"])
                        
                        # Average channels
                        audio_data = np.mean(audio_data, axis=1, dtype=np.int16)
                        
                        # Convert back to bytes
                        data = audio_data.tobytes()
                    
                    # Add to queue
                    self.audio_queue.put(data)
                except Exception as e:
                    logger.error(f"Error reading audio data: {e}")
                    time.sleep(0.1)
            
            # Close stream
            self.stream.stop_stream()
            self.stream.close()
            self.stream = None
            
            logger.debug("Closed audio stream")
        except Exception as e:
            logger.error(f"Error in record thread: {e}")
            self.recording = False
    
    def _process_audio(self):
        """Process audio data from the queue."""
        # Initialize variables
        block_start_time = datetime.datetime.now()
        self.current_block_size = 0
        last_disk_check_time = 0
        
        # Calculate the end of the current 3-hour block
        hour = block_start_time.hour
        block_number = hour // 3
        block_end_hour = (block_number + 1) * 3
        
        # Create end time
        if block_end_hour >= 24:
            # If the block ends at or after midnight, we need to move to the next day
            next_day = block_start_time + datetime.timedelta(days=1)
            block_end_time = next_day.replace(hour=0, minute=0, second=0)
        else:
            # Same day, at the end of the 3-hour block
            block_end_time = block_start_time.replace(hour=block_end_hour, minute=0, second=0)
        
        # Create file path
        file_path = create_file_path(
            self.config["paths"]["recordings_dir"],
            block_start_time
        )
        
        # Create wave file
        self.current_file = file_path
        self.current_wave = wave.open(file_path, "wb")
        self.current_wave.setnchannels(1 if self.config["audio"]["mono"] else self.config["audio"]["channels"])
        self.current_wave.setsampwidth(2)  # 16-bit
        self.current_wave.setframerate(self.config["audio"]["sample_rate"])
        
        logger.info(f"Recording to {file_path}")
        
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
                            file_path,
                            self.config["paths"]["ffmpeg_path"],
                            self.config["audio"]["quality"]
                        )
                        if mp3_file:
                            logger.info(f"Converted to {mp3_file}")
                    
                    # Start new block
                    block_start_time = now
                    
                    # Calculate the end of the new 3-hour block
                    hour = block_start_time.hour
                    block_number = hour // 3
                    block_end_hour = (block_number + 1) * 3
                    
                    # Create end time
                    if block_end_hour >= 24:
                        # If the block ends at or after midnight, we need to move to the next day
                        next_day = block_start_time + datetime.timedelta(days=1)
                        block_end_time = next_day.replace(hour=0, minute=0, second=0)
                    else:
                        # Same day, at the end of the 3-hour block
                        block_end_time = block_start_time.replace(hour=block_end_hour, minute=0, second=0)
                    
                    # Create file path
                    file_path = create_file_path(
                        self.config["paths"]["recordings_dir"],
                        block_start_time
                    )
                    
                    # Create wave file
                    self.current_file = file_path
                    self.current_wave = wave.open(file_path, "wb")
                    self.current_wave.setnchannels(1 if self.config["audio"]["mono"] else self.config["audio"]["channels"])
                    self.current_wave.setsampwidth(2)  # 16-bit
                    self.current_wave.setframerate(self.config["audio"]["sample_rate"])
                    
                    logger.info(f"Recording to {file_path}")
                
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
                        logger.info(f"Current block size: {self.format_file_size(self.get_current_block_size())}")
                    
                    # Check disk space every minute
                    if current_time - last_disk_check_time >= 60:
                        last_disk_check_time = current_time
                        
                        # Check free disk space
                        free_space = self.get_free_disk_space()
                        folder_size = self.get_recordings_folder_size()
                        
                        # Log disk space info
                        logger.debug(f"Free disk space: {self.format_file_size(free_space)}")
                        logger.debug(f"Recordings folder size: {self.format_file_size(folder_size)}")
                        
                        # Check if retention would fit
                        retention_fit = self.would_retention_fit()
                        if not retention_fit["fits"]:
                            logger.warning(f"WARNING: Retention period would not fit in available disk space. "
                                          f"Need {self.format_file_size(retention_fit['needed_space'])}, "
                                          f"have {self.format_file_size(free_space)}")
                        
                        # Check if disk space is critically low (less than 5GB or 5% of needed space)
                        critical_space = min(5 * 1024 * 1024 * 1024, retention_fit["needed_space"] * 0.05)
                        if free_space < critical_space:
                            logger.error(f"CRITICAL: Disk space is critically low! "
                                        f"Only {self.format_file_size(free_space)} remaining.")
                        
                except queue.Empty:
                    pass
            except Exception as e:
                logger.error(f"Error in process thread: {e}")
                time.sleep(0.1)
    
    def _convert_to_mp3(self, wav_file):
        """Convert WAV file to MP3 format."""
        return convert_to_mp3(
            wav_file,
            self.config["paths"]["ffmpeg_path"],
            self.config["audio"]["quality"]
        )
    
    def _run_cleanup_thread(self):
        """Run the cleanup thread."""
        while self.recording:
            try:
                # Run cleanup
                self._cleanup_old_recordings()
                
                # Sleep for a day
                for _ in range(24 * 60 * 60 // 10):
                    if not self.recording:
                        break
                    time.sleep(10)
            except Exception as e:
                logger.error(f"Error in cleanup thread: {e}")
                time.sleep(60)
    
    def _cleanup_old_recordings(self):
        """Delete recordings older than retention_days."""
        cleanup_old_recordings(
            self.config["paths"]["recordings_dir"],
            self.config["general"]["retention_days"]
        )
    
    def setup_autostart(self, enable):
        """Configure application to run on system startup."""
        return setup_autostart(enable)
    
    def display_configuration(self):
        """Display the current recording configuration."""
        logger.info("Current Recording Configuration:")
        logger.info(f"  Sample Rate: {self.config['audio']['sample_rate']} Hz")
        logger.info(f"  Bit Depth: 16-bit")
        logger.info(f"  Channels: {1 if self.config['audio']['mono'] else self.config['audio']['channels']}")
        logger.info(f"  Format: {self.config['audio']['format'].upper()}")
        logger.info(f"  Quality: {self.config['audio']['quality']}")
        logger.info(f"  Recording Block Hours: {self.config['general']['recording_hours']}")
        logger.info(f"  Retention Period: {self.config['general']['retention_days']} days")
        
        # Calculate and display estimated file sizes
        block_size = self.calculate_block_size()
        day_size = self.calculate_day_size()
        estimated_size = self.calculate_90day_size()
        logger.info(f"  Estimated Block Size ({self.config['general']['recording_hours']} hours): {self.format_file_size(block_size)}")
        logger.info(f"  Estimated Daily Storage Requirement: {self.format_file_size(day_size)}")
        logger.info(f"  Estimated 90-Day Storage Requirement: {self.format_file_size(estimated_size)}")
        
        # Display current recordings folder size
        folder_size = self.get_recordings_folder_size()
        logger.info(f"  Current Recordings Folder Size: {self.format_file_size(folder_size)}")
        
        # Display free disk space
        free_space = self.get_free_disk_space()
        logger.info(f"  Free Disk Space: {self.format_file_size(free_space)}")
        
        # Check if retention would fit
        retention_fit = self.would_retention_fit()
        if retention_fit["fits"]:
            logger.info(f"  Retention Period Would Fit in Available Space (Using {retention_fit['percentage']:.1f}% of free space)")
        else:
            logger.warning(f"  WARNING: Retention Period Would NOT Fit in Available Space (Needs {self.format_file_size(retention_fit['needed_space'])})")
    
    def get_current_block_size(self):
        """Get the current block file size in bytes."""
        if self.current_file and os.path.exists(self.current_file):
            return os.path.getsize(self.current_file)
        return 0
    
    def calculate_90day_size(self):
        """Calculate estimated file size for 90 days of continuous recording."""
        # Calculate bytes per second
        bytes_per_sample = 2  # 16-bit = 2 bytes
        channels = 1 if self.config["audio"]["mono"] else self.config["audio"]["channels"]
        bytes_per_second = self.config["audio"]["sample_rate"] * bytes_per_sample * channels
        
        # Calculate total seconds in 90 days
        seconds_in_90days = 90 * 24 * 60 * 60
        
        # Calculate raw size
        raw_size = bytes_per_second * seconds_in_90days
        
        # Apply compression factor if using MP3
        if self.config["audio"]["format"] == "mp3":
            # Compression factors based on quality
            compression_factors = {
                "high": 0.1,    # ~10:1 compression
                "medium": 0.075, # ~13:1 compression
                "low": 0.05     # ~20:1 compression
            }
            compression_factor = compression_factors.get(self.config["audio"]["quality"], 0.1)
            return raw_size * compression_factor
        
        return raw_size
    
    def format_file_size(self, size_bytes):
        """Format file size in human-readable format."""
        if size_bytes < 1024:
            return f"{size_bytes} bytes"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.2f} KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.2f} MB"
        else:
            return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"
    
    def get_recordings_folder_size(self):
        """Calculate the total size of the recordings folder."""
        total_size = 0
        recordings_dir = self.config["paths"]["recordings_dir"]
        
        if not os.path.exists(recordings_dir):
            return 0
            
        for dirpath, dirnames, filenames in os.walk(recordings_dir):
            for filename in filenames:
                file_path = os.path.join(dirpath, filename)
                if os.path.isfile(file_path):
                    total_size += os.path.getsize(file_path)
                    
        return total_size
    
    def get_free_disk_space(self):
        """Get free disk space where recordings are stored."""
        recordings_dir = self.config["paths"]["recordings_dir"]
        
        if not os.path.exists(recordings_dir):
            # If directory doesn't exist, check the parent directory
            recordings_dir = os.path.dirname(os.path.abspath(recordings_dir))
            if not os.path.exists(recordings_dir):
                # If parent doesn't exist either, use current directory
                recordings_dir = os.getcwd()
        
        try:
            if sys.platform == "win32":
                import ctypes
                free_bytes = ctypes.c_ulonglong(0)
                ctypes.windll.kernel32.GetDiskFreeSpaceExW(
                    ctypes.c_wchar_p(recordings_dir), None, None, ctypes.pointer(free_bytes))
                return free_bytes.value
            else:
                # For Unix-based systems
                st = os.statvfs(recordings_dir)
                return st.f_bavail * st.f_frsize
        except Exception as e:
            logger.error(f"Error getting free disk space: {e}")
            return 0
    
    def calculate_day_size(self):
        """Calculate estimated file size for 1 day of continuous recording."""
        # Calculate bytes per second
        bytes_per_sample = 2  # 16-bit = 2 bytes
        channels = 1 if self.config["audio"]["mono"] else self.config["audio"]["channels"]
        bytes_per_second = self.config["audio"]["sample_rate"] * bytes_per_sample * channels
        
        # Calculate total seconds in 1 day
        seconds_in_day = 24 * 60 * 60
        
        # Calculate raw size
        raw_size = bytes_per_second * seconds_in_day
        
        # Apply compression factor if using MP3
        if self.config["audio"]["format"] == "mp3":
            # Compression factors based on quality
            compression_factors = {
                "high": 0.1,    # ~10:1 compression
                "medium": 0.075, # ~13:1 compression
                "low": 0.05     # ~20:1 compression
            }
            compression_factor = compression_factors.get(self.config["audio"]["quality"], 0.1)
            return raw_size * compression_factor
        
        return raw_size
    
    def calculate_block_size(self):
        """Calculate estimated file size for a recording block."""
        # Calculate bytes per second
        bytes_per_sample = 2  # 16-bit = 2 bytes
        channels = 1 if self.config["audio"]["mono"] else self.config["audio"]["channels"]
        bytes_per_second = self.config["audio"]["sample_rate"] * bytes_per_sample * channels
        
        # Calculate total seconds in the recording block
        hours = self.config["general"]["recording_hours"]
        seconds_in_block = hours * 60 * 60
        
        # Calculate raw size
        raw_size = bytes_per_second * seconds_in_block
        
        # Apply compression factor if using MP3
        if self.config["audio"]["format"] == "mp3":
            # Compression factors based on quality
            compression_factors = {
                "high": 0.1,    # ~10:1 compression
                "medium": 0.075, # ~13:1 compression
                "low": 0.05     # ~20:1 compression
            }
            compression_factor = compression_factors.get(self.config["audio"]["quality"], 0.1)
            return raw_size * compression_factor
        
        return raw_size
    
    def would_retention_fit(self):
        """Check if the current retention period would fit in the available disk space."""
        # Get free disk space
        free_space = self.get_free_disk_space()
        
        # Calculate size needed for retention period
        day_size = self.calculate_day_size()
        retention_days = self.config["general"]["retention_days"]
        needed_space = day_size * retention_days
        
        # Return result and percentage
        fits = free_space > needed_space
        percentage = (needed_space / free_space * 100) if free_space > 0 else 100
        
        return {
            "fits": fits,
            "free_space": free_space,
            "needed_space": needed_space,
            "percentage": min(percentage, 100)  # Cap at 100%
        } 
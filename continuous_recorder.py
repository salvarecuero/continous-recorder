# Import necessary modules
import os
import sys
import time
import queue
import signal
import atexit
import logging
import argparse
import threading
import datetime
import configparser
import numpy as np
try:
    import pyaudiowpatch as pyaudio
    HAS_WASAPI = True
except ImportError:
    import pyaudio
    HAS_WASAPI = False
import wave

# Configure logging
logger = logging.getLogger("ContinuousRecorder")
logger.setLevel(logging.DEBUG)

# Create console handler
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console_handler.setFormatter(console_formatter)
logger.addHandler(console_handler)

# Create file handler
os.makedirs("logs", exist_ok=True)
log_file = os.path.join("logs", f"recorder_{datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.log")
file_handler = logging.FileHandler(log_file)
file_handler.setLevel(logging.DEBUG)
file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(file_formatter)
logger.addHandler(file_handler)

# Default configuration
DEFAULT_CONFIG = {
    "general": {
        "retention_days": 90,
        "recording_hours": 3,
        "run_on_startup": True,
        "minimize_to_tray": True
    },
    "audio": {
        "format": "mp3",
        "sample_rate": 44100,
        "channels": 2,
        "chunk_size": 1024,
        "device_index": None,
        "quality": "high",  # high, medium, low
        "mono": False,  # True for mono, False for stereo
        "monitor_level": 0.0  # 0.0 to 1.0
    },
    "paths": {
        "recordings_dir": "Recordings",
        "ffmpeg_path": "ffmpeg"
    }
}

class AudioRecorder:
    """Main class for handling continuous audio recording from system output."""
    
    def __init__(self, config_path="config.ini"):
        """Initialize the recorder with configuration."""
        self.config = self._load_config(config_path)
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
        
        # Create base recordings directory
        os.makedirs(self.config["paths"]["recordings_dir"], exist_ok=True)
        
        # Register signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        # Register cleanup function
        atexit.register(self._cleanup_lock)

    def _load_config(self, config_path):
        """Load configuration from file or use defaults."""
        config = DEFAULT_CONFIG.copy()
        
        if os.path.exists(config_path):
            try:
                import configparser
                parser = configparser.ConfigParser()
                parser.read(config_path)
                
                # Load general settings
                if "general" in parser:
                    for key in ["retention_days", "recording_hours", "run_on_startup", "minimize_to_tray"]:
                        if key in parser["general"]:
                            config["general"][key] = parser["general"].getboolean(key)
                
                # Load audio settings
                if "audio" in parser:
                    for key in ["format", "sample_rate", "channels", "chunk_size", "device_index", "quality", "mono", "monitor_level"]:
                        if key in parser["audio"]:
                            if key in ["sample_rate", "channels", "chunk_size", "device_index"]:
                                config["audio"][key] = parser["audio"].getint(key)
                            elif key in ["mono"]:
                                config["audio"][key] = parser["audio"].getboolean(key)
                            elif key in ["monitor_level"]:
                                config["audio"][key] = parser["audio"].getfloat(key)
                            else:
                                config["audio"][key] = parser["audio"][key]
                
                # Load paths
                if "paths" in parser:
                    for key in ["recordings_dir", "ffmpeg_path"]:
                        if key in parser["paths"]:
                            config["paths"][key] = parser["paths"][key]
                
                logger.info(f"Configuration loaded from {config_path}")
            except Exception as e:
                logger.error(f"Error loading config file: {e}")
                logger.info("Using default configuration")
        
        return config

    def _save_config(self):
        """Save current configuration to file."""
        try:
            import configparser
            parser = configparser.ConfigParser()
            
            # Save general settings
            parser["general"] = {
                "retention_days": str(self.config["general"]["retention_days"]),
                "recording_hours": str(self.config["general"]["recording_hours"]),
                "run_on_startup": str(self.config["general"]["run_on_startup"]),
                "minimize_to_tray": str(self.config["general"]["minimize_to_tray"])
            }
            
            # Save audio settings
            parser["audio"] = {
                "format": self.config["audio"]["format"],
                "sample_rate": str(self.config["audio"]["sample_rate"]),
                "channels": str(self.config["audio"]["channels"]),
                "chunk_size": str(self.config["audio"]["chunk_size"]),
                "device_index": str(self.config["audio"]["device_index"]),
                "quality": self.config["audio"]["quality"],
                "mono": str(self.config["audio"]["mono"]),
                "monitor_level": str(self.config["audio"]["monitor_level"])
            }
            
            # Save paths
            parser["paths"] = {
                "recordings_dir": self.config["paths"]["recordings_dir"],
                "ffmpeg_path": self.config["paths"]["ffmpeg_path"]
            }
            
            with open("config.ini", "w") as f:
                parser.write(f)
            
            logger.info("Configuration saved")
        except Exception as e:
            logger.error(f"Error saving config file: {e}")

    def list_devices(self):
        """List all available audio devices."""
        p = pyaudio.PyAudio()
        
        print("\nAvailable Audio Devices:")
        print("-" * 50)
        
        # Get default WASAPI device if available
        default_wasapi = None
        if HAS_WASAPI:
            try:
                default_wasapi = p.get_default_wasapi_device()
                print(f"Default WASAPI device: {default_wasapi['name']} (index {default_wasapi['index']})")
            except Exception as e:
                print(f"Error getting default WASAPI device: {e}")
        
        # Get loopback devices
        loopback_devices = []
        if HAS_WASAPI:
            try:
                for device in p.get_loopback_device_info_generator():
                    loopback_devices.append(device['index'])
                    print(f"Loopback Device {device['index']}: {device['name']}")
                    print(f"  Input Channels: {device['maxInputChannels']}")
                    print(f"  Sample Rate: {device['defaultSampleRate']}")
                    print("-" * 50)
            except Exception as e:
                print(f"Error getting loopback devices: {e}")
        
        # List all devices
        recommended_devices = []
        try:
            for device in p.get_device_info_generator():
                host_api = p.get_host_api_info_by_index(device.get('hostApi', 0))
                host_api_name = host_api.get('name', 'Unknown')
                
                is_loopback = device.get('isLoopbackDevice', False) or device['index'] in loopback_devices
                is_wasapi = device.get('hostApi', 0) == p.get_host_api_info_by_type(pyaudio.paWASAPI)['index']
                has_input = device.get('maxInputChannels', 0) > 0
                
                # Only show output devices
                if device.get('maxOutputChannels', 0) > 0:
                    # Build status indicators
                    status = []
                    if is_loopback:
                        status.append("LOOPBACK")
                    if is_wasapi:
                        status.append("WASAPI")
                    if has_input:
                        status.append("INPUT")
                    
                    status_str = f" [{', '.join(status)}]" if status else ""
                    
                    # Determine if this is a recommended device for recording
                    is_recommended = is_loopback and has_input
                    if is_recommended:
                        recommended_devices.append(device['index'])
                    
                    # Add a star to recommended devices
                    rec_str = " ⭐" if is_recommended else ""
                    
                    print(f"Device {device['index']}: {device['name']}{status_str}{rec_str}")
                    print(f"  Host API: {host_api_name}")
                    print(f"  Input Channels: {device['maxInputChannels']}")
                    print(f"  Output Channels: {device['maxOutputChannels']}")
                    print(f"  Default Sample Rate: {device['defaultSampleRate']}")
                    print("-" * 50)
        except Exception as e:
            print(f"Error listing devices: {e}")
        
        # Print recommendations
        if recommended_devices:
            print("\nRecommended devices for recording system audio:")
            for idx in recommended_devices:
                device = p.get_device_info_by_index(idx)
                print(f"  Device {idx}: {device['name']}")
            print("\nUse --set-device INDEX to select a device.")
        else:
            print("\nNo recommended devices found. Try selecting a WASAPI device manually.")
        
        p.terminate()

    def set_audio_quality(self, quality):
        """Set the audio quality level."""
        if quality not in ["high", "medium", "low"]:
            logger.error(f"Invalid quality level: {quality}")
            return False
            
        self.config["audio"]["quality"] = quality
        
        # Update audio parameters based on quality
        if quality == "high":
            self.config["audio"]["sample_rate"] = 48000
            self.config["audio"]["chunk_size"] = 2048
        elif quality == "medium":
            self.config["audio"]["sample_rate"] = 44100
            self.config["audio"]["chunk_size"] = 1024
        else:  # low
            self.config["audio"]["sample_rate"] = 22050
            self.config["audio"]["chunk_size"] = 512
            
        self._save_config()
        logger.info(f"Audio quality set to {quality}")
        return True

    def set_mono(self, mono):
        """Set mono/stereo recording mode."""
        self.config["audio"]["mono"] = mono
        self._save_config()
        logger.info(f"Recording mode set to {'mono' if mono else 'stereo'}")
        return True

    def set_monitor_level(self, level):
        """Set the monitor level (0.0 to 1.0)."""
        if not 0.0 <= level <= 1.0:
            logger.error(f"Invalid monitor level: {level}")
            return False
            
        self.config["audio"]["monitor_level"] = level
        self._save_config()
        logger.info(f"Monitor level set to {level}")
        return True

    def _start_monitor(self):
        """Start monitoring the selected device."""
        if self.monitor_stream is not None:
            return
            
        try:
            self.audio = pyaudio.PyAudio()
            self.monitor_stream = self.audio.open(
                format=pyaudio.paFloat32,
                channels=1,
                rate=44100,
                input=True,
                input_device_index=self.device_index,
                frames_per_buffer=1024
            )
            
            self.monitor_thread = threading.Thread(target=self._monitor_audio)
            self.monitor_thread.daemon = True
            self.monitor_thread.start()
            logger.info("Started audio monitoring")
        except Exception as e:
            logger.error(f"Error starting audio monitor: {e}")
            self._stop_monitor()

    def _stop_monitor(self):
        """Stop monitoring the selected device."""
        if self.monitor_stream:
            try:
                self.monitor_stream.stop_stream()
                self.monitor_stream.close()
            except Exception as e:
                logger.error(f"Error closing monitor stream: {e}")
            finally:
                self.monitor_stream = None
                self.monitor_thread = None
                logger.info("Stopped audio monitoring")

    def _monitor_audio(self):
        """Monitor audio levels from the selected device."""
        while self.monitor_stream:
            try:
                data = self.monitor_stream.read(1024, exception_on_overflow=False)
                # Convert to numpy array for level calculation
                audio_data = np.frombuffer(data, dtype=np.float32)
                level = np.abs(audio_data).mean()
                
                # Log level if it's significant
                if level > 0.01:  # Threshold to avoid noise
                    logger.debug(f"Audio level: {level:.3f}")
                    
            except Exception as e:
                logger.error(f"Error monitoring audio: {e}")
                time.sleep(0.1)

    def start_recording(self):
        """Start the recording process."""
        # Check if another instance is running
        if self._check_lock():
            logger.warning("Another instance of the recorder is already running")
            return False
            
        if self.recording:
            logger.warning("Recording is already in progress")
            return False
        
        if self.device_index is None:
            logger.error("No recording device selected")
            return False
        
        # Create lock file
        if not self._create_lock():
            logger.error("Failed to create lock file")
            return False
        
        self.recording = True
        self.paused = False
        
        # Start monitoring
        self._start_monitor()
        
        # Start the recording thread
        self.record_thread = threading.Thread(target=self._record_audio)
        self.record_thread.daemon = True
        self.record_thread.start()
        
        # Start the processing thread
        self.process_thread = threading.Thread(target=self._process_audio)
        self.process_thread.daemon = True
        self.process_thread.start()
        
        # Start the cleanup thread
        self.cleanup_thread = threading.Thread(target=self._run_cleanup_thread)
        self.cleanup_thread.daemon = True
        self.cleanup_thread.start()
        
        # Start the status update thread
        self.status_thread = threading.Thread(target=self._run_status_thread)
        self.status_thread.daemon = True
        self.status_thread.start()
        
        logger.info("Recording started")
        return True

    def stop_recording(self):
        """Stop the recording process."""
        # Check if another instance is running
        pid = self._check_lock()
        if pid and pid != self.pid:
            logger.info(f"Sending stop command to process {pid}")
            return self._send_command("stop")
            
        if not self.recording:
            logger.warning("Recording is not in progress")
            return False
        
        self.recording = False
        
        # Stop monitoring
        self._stop_monitor()
        
        # Wait for threads to finish
        if self.record_thread:
            self.record_thread.join(timeout=2)
        if self.process_thread:
            self.process_thread.join(timeout=5)
        if self.cleanup_thread:
            self.cleanup_thread.join(timeout=2)
        if hasattr(self, 'status_thread') and self.status_thread:
            self.status_thread.join(timeout=2)
        
        # Clean up lock file
        self._cleanup_lock()
        
        logger.info("Recording stopped")
        return True
        
    def pause_recording(self):
        """Pause the recording."""
        if not self.recording:
            logger.warning("Recording is not in progress")
            return False
            
        self.paused = True
        logger.info("Recording paused")
        return True
        
    def resume_recording(self):
        """Resume the recording."""
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
            "current_file": self.current_file,
            "next_file_time": None,
            "queue_size": self.audio_queue.qsize() if self.audio_queue else 0
        }
        
        # Calculate next file time
        if self.recording and self.current_file:
            try:
                # Extract current file start time
                filename = os.path.basename(self.current_file)
                start_time_str = filename.split("_")[0] + "_" + filename.split("_")[1]
                start_time = datetime.datetime.strptime(start_time_str, "%Y-%m-%d_%H-%M")
                
                # Add recording hours to get next file time
                next_file_time = start_time + datetime.timedelta(hours=self.config["general"]["recording_hours"])
                status["next_file_time"] = next_file_time.strftime("%Y-%m-%d %H:%M")
            except Exception as e:
                logger.error(f"Error calculating next file time: {e}")
        
        return status
        
    def _get_device_index(self):
        """Get the device index from config or auto-detect."""
        if self.config["audio"]["device_index"] is not None:
            return self.config["audio"]["device_index"]
            
        # Auto-detect a suitable device
        try:
            p = pyaudio.PyAudio()
            
            # Try to get default WASAPI device first
            if HAS_WASAPI:
                try:
                    default_wasapi = p.get_default_wasapi_device()
                    if default_wasapi and default_wasapi.get('maxInputChannels', 0) > 0:
                        p.terminate()
                        logger.info(f"Auto-detected default WASAPI device: {default_wasapi['name']}")
                        return default_wasapi['index']
                except Exception as e:
                    logger.error(f"Error getting default WASAPI device: {e}")
            
            # Try to get default WASAPI loopback
            if HAS_WASAPI:
                try:
                    default_loopback = p.get_default_wasapi_loopback()
                    if default_loopback and default_loopback.get('maxInputChannels', 0) > 0:
                        p.terminate()
                        logger.info(f"Auto-detected default WASAPI loopback: {default_loopback['name']}")
                        return default_loopback['index']
                except Exception as e:
                    logger.error(f"Error getting default WASAPI loopback: {e}")
            
            # Try to find a suitable loopback device
            try:
                for device in p.get_loopback_device_info_generator():
                    if device.get('maxInputChannels', 0) > 0:
                        p.terminate()
                        logger.info(f"Auto-detected loopback device: {device['name']}")
                        return device['index']
            except Exception as e:
                logger.error(f"Error getting loopback devices: {e}")
            
            # Try to find any suitable WASAPI device
            if HAS_WASAPI:
                try:
                    wasapi_api_index = p.get_host_api_info_by_type(pyaudio.paWASAPI)['index']
                    for device in p.get_device_info_generator_by_host_api(wasapi_api_index):
                        if device.get('maxInputChannels', 0) > 0:
                            p.terminate()
                            logger.info(f"Auto-detected WASAPI device: {device['name']}")
                            return device['index']
                except Exception as e:
                    logger.error(f"Error getting WASAPI devices: {e}")
            
            p.terminate()
            logger.warning("No suitable device found for auto-detection")
            return None
        except Exception as e:
            logger.error(f"Error auto-detecting device: {e}")
            return None
            
    def set_device(self, device_index):
        """Set the recording device by index."""
        try:
            p = pyaudio.PyAudio()
            device_info = p.get_device_info_by_index(device_index)
            p.terminate()
            
            self.device_index = device_index
            self.config["audio"]["device_index"] = device_index
            self._save_config()
            
            logger.info(f"Recording device set to {device_index}: {device_info['name']}")
            return True
        except Exception as e:
            logger.error(f"Error setting device {device_index}: {e}")
            return False
            
    def _get_pyaudio_instance(self):
        """Get a PyAudio instance."""
        try:
            return pyaudio.PyAudio()
        except Exception as e:
            logger.error(f"Error creating PyAudio instance: {e}")
            return None
            
    def _signal_handler(self, sig, frame):
        """Handle signals for graceful shutdown."""
        logger.info(f"Received signal {sig}, shutting down...")
        self.stop_recording()
        sys.exit(0)
        
    def _check_lock(self):
        """Check if another instance is running."""
        global os
        lock_file = "recorder.lock"
        if os.path.exists(lock_file):
            try:
                with open(lock_file, "r") as f:
                    pid = int(f.read().strip())
                
                # Check if process is still running
                if sys.platform == "win32":
                    import ctypes
                    kernel32 = ctypes.windll.kernel32
                    handle = kernel32.OpenProcess(1, False, pid)
                    if handle:
                        kernel32.CloseHandle(handle)
                        return pid
                else:
                    import os
                    try:
                        os.kill(pid, 0)
                        return pid
                    except OSError:
                        pass
            except Exception as e:
                logger.error(f"Error checking lock file: {e}")
            
            # Lock file exists but process is not running
            try:
                os.remove(lock_file)
            except:
                pass
        
        return False
        
    def _create_lock(self):
        """Create a lock file."""
        lock_file = "recorder.lock"
        try:
            with open(lock_file, "w") as f:
                f.write(str(self.pid))
            return True
        except Exception as e:
            logger.error(f"Error creating lock file: {e}")
            return False
            
    def _cleanup_lock(self):
        """Clean up the lock file."""
        lock_file = "recorder.lock"
        if os.path.exists(lock_file):
            try:
                with open(lock_file, "r") as f:
                    pid = int(f.read().strip())
                
                if pid == self.pid:
                    os.remove(lock_file)
                    logger.info("Lock file removed")
            except Exception as e:
                logger.error(f"Error cleaning up lock file: {e}")
                
    def _send_command(self, command):
        """Send a command to another instance."""
        command_file = "recorder_command.txt"
        try:
            with open(command_file, "w") as f:
                f.write(command)
            logger.info(f"Command '{command}' sent")
            return True
        except Exception as e:
            logger.error(f"Error sending command: {e}")
            return False
            
    def _check_command(self):
        """Check for commands from other instances."""
        command_file = "recorder_command.txt"
        if os.path.exists(command_file):
            try:
                with open(command_file, "r") as f:
                    command = f.read().strip()
                
                os.remove(command_file)
                
                if command == "stop":
                    logger.info("Received stop command")
                    self.stop_recording()
                elif command == "pause":
                    logger.info("Received pause command")
                    self.pause_recording()
                elif command == "resume":
                    logger.info("Received resume command")
                    self.resume_recording()
                
                return command
            except Exception as e:
                logger.error(f"Error checking command: {e}")
        
        return None
        
    def _record_audio(self):
        """Record audio from the selected device."""
        try:
            # Initialize PyAudio
            self.audio = pyaudio.PyAudio()
            
            # Get device info
            device_info = self.audio.get_device_info_by_index(self.device_index)
            logger.info(f"Recording from device: {device_info['name']} (index {self.device_index})")
            
            # Determine channels
            channels = 1 if self.config["audio"]["mono"] else min(2, device_info.get('maxInputChannels', 2))
            logger.info(f"Using {channels} channel(s)")
            
            # Open stream
            self.stream = self.audio.open(
                format=pyaudio.paInt16,
                channels=channels,
                rate=self.config["audio"]["sample_rate"],
                input=True,
                input_device_index=self.device_index,
                frames_per_buffer=self.config["audio"]["chunk_size"]
            )
            
            logger.info(f"Stream opened with sample rate {self.config['audio']['sample_rate']} Hz")
            
            # Record until stopped
            while self.recording:
                if not self.paused:
                    try:
                        data = self.stream.read(self.config["audio"]["chunk_size"], exception_on_overflow=False)
                        self.audio_queue.put(data)
                    except Exception as e:
                        logger.error(f"Error reading audio data: {e}")
                        time.sleep(0.1)
                else:
                    time.sleep(0.1)
                
                # Check for commands
                self._check_command()
            
            # Clean up
            self.stream.stop_stream()
            self.stream.close()
            self.audio.terminate()
            self.stream = None
            self.audio = None
            
            logger.info("Recording thread stopped")
        except Exception as e:
            logger.error(f"Error in recording thread: {e}")
            self.recording = False
            
    def _process_audio(self):
        """Process audio data from the queue."""
        try:
            # Initialize variables
            current_file = None
            current_wave = None
            last_file_time = None
            
            while self.recording or not self.audio_queue.empty():
                # Check if we need to create a new file
                now = datetime.datetime.now()
                file_time = now.replace(minute=now.minute - (now.minute % 60), second=0, microsecond=0)
                
                if last_file_time is None or file_time != last_file_time:
                    # Close previous file if open
                    if current_wave:
                        current_wave.close()
                    
                    # Create new file
                    file_path = self._create_file_path(file_time)
                    
                    try:
                        # Create directory if it doesn't exist
                        os.makedirs(os.path.dirname(file_path), exist_ok=True)
                        
                        # Create wave file
                        current_wave = wave.open(file_path, 'wb')
                        current_wave.setnchannels(1 if self.config["audio"]["mono"] else 2)
                        current_wave.setsampwidth(2)  # 16-bit
                        current_wave.setframerate(self.config["audio"]["sample_rate"])
                        
                        current_file = file_path
                        self.current_file = file_path
                        last_file_time = file_time
                        
                        logger.info(f"Created new recording file: {file_path}")
                    except Exception as e:
                        logger.error(f"Error creating file {file_path}: {e}")
                        time.sleep(1)
                        continue
                
                # Process data from queue
                try:
                    # Use a timeout to avoid blocking forever
                    data = self.audio_queue.get(timeout=0.5)
                    
                    # Write data to file
                    if current_wave:
                        current_wave.writeframes(data)
                    
                    # Log queue size occasionally
                    queue_size = self.audio_queue.qsize()
                    if queue_size > 100 or queue_size == 0:
                        logger.debug(f"Queue size: {queue_size} chunks")
                except queue.Empty:
                    # No data available, just continue
                    continue
                except Exception as e:
                    logger.error(f"Error processing audio data: {e}")
                    time.sleep(0.1)
            
            # Close the final file
            if current_wave:
                current_wave.close()
                logger.info(f"Closed final recording file: {current_file}")
                
                # Convert to MP3 if needed
                if self.config["audio"]["format"] == "mp3":
                    self._convert_to_mp3(current_file)
            
            logger.info("Processing thread stopped")
        except Exception as e:
            logger.error(f"Error in processing thread: {e}")
            
    def _create_file_path(self, file_time):
        """Create a file path for the recording."""
        # Calculate end time (start time + recording hours)
        end_time = file_time + datetime.timedelta(hours=self.config["general"]["recording_hours"])
        
        # Format times
        start_str = file_time.strftime("%Y-%m-%d_%H-%M")
        end_str = end_time.strftime("%Y-%m-%d_%H-%M")
        
        # Create directory structure
        year_dir = os.path.join(self.config["paths"]["recordings_dir"], file_time.strftime("%Y"))
        month_dir = os.path.join(year_dir, file_time.strftime("%m"))
        day_dir = os.path.join(month_dir, file_time.strftime("%d"))
        
        # Create file name
        file_name = f"{start_str}_to_{end_str}.wav"
        
        return os.path.join(day_dir, file_name)
        
    def _convert_to_mp3(self, wav_file):
        """Convert WAV file to MP3."""
        if not os.path.exists(wav_file):
            logger.error(f"WAV file not found: {wav_file}")
            return False
            
        mp3_file = wav_file.replace(".wav", ".mp3")
        ffmpeg_path = self.config["paths"]["ffmpeg_path"]
        
        try:
            import subprocess
            cmd = [ffmpeg_path, "-i", wav_file, "-codec:a", "libmp3lame", "-qscale:a", "2", mp3_file]
            
            # Run FFmpeg
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            stdout, stderr = process.communicate()
            
            if process.returncode == 0:
                logger.info(f"Converted {wav_file} to MP3")
                
                # Remove WAV file if conversion successful
                os.remove(wav_file)
                logger.info(f"Removed original WAV file: {wav_file}")
                
                return True
            else:
                logger.error(f"FFmpeg error: {stderr.decode()}")
                return False
        except Exception as e:
            logger.error(f"Error converting to MP3: {e}")
            return False
            
    def _run_cleanup_thread(self):
        """Run the cleanup process in a separate thread."""
        while self.recording:
            try:
                self._cleanup_old_recordings()
            except Exception as e:
                logger.error(f"Error in cleanup thread: {e}")
            
            # Sleep for an hour before next cleanup
            for _ in range(60):  # Check every minute if we should stop
                if not self.recording:
                    break
                time.sleep(60)
                
    def _cleanup_old_recordings(self):
        """Clean up old recordings based on retention days."""
        retention_days = self.config["general"]["retention_days"]
        if retention_days <= 0:
            logger.info("Retention disabled, skipping cleanup")
            return
            
        # Calculate cutoff date
        cutoff_date = datetime.datetime.now() - datetime.timedelta(days=retention_days)
        logger.info(f"Cleaning up recordings older than {cutoff_date.strftime('%Y-%m-%d')}")
        
        # Walk through recordings directory
        recordings_dir = self.config["paths"]["recordings_dir"]
        if not os.path.exists(recordings_dir):
            logger.warning(f"Recordings directory not found: {recordings_dir}")
            return
            
        try:
            for root, dirs, files in os.walk(recordings_dir):
                for file in files:
                    if file.endswith(".wav") or file.endswith(".mp3"):
                        file_path = os.path.join(root, file)
                        
                        # Extract date from file name
                        try:
                            date_str = file.split("_")[0]
                            file_date = datetime.datetime.strptime(date_str, "%Y-%m-%d")
                            
                            if file_date < cutoff_date:
                                os.remove(file_path)
                                logger.info(f"Removed old recording: {file_path}")
                        except Exception as e:
                            logger.error(f"Error parsing date from file {file}: {e}")
        except Exception as e:
            logger.error(f"Error cleaning up old recordings: {e}")
            
    def _run_status_thread(self):
        """Run the status update thread."""
        status_file = "recorder_status.json"
        
        while self.recording:
            try:
                # Get current status
                status = self.get_status()
                
                # Write to status file
                import json
                with open(status_file, "w") as f:
                    json.dump(status, f)
            except Exception as e:
                logger.error(f"Error updating status file: {e}")
            
            # Update every second
            time.sleep(1)
            
        # Clean up status file
        if os.path.exists(status_file):
            try:
                os.remove(status_file)
            except:
                pass
                
    def setup_autostart(self, enable):
        """Configure autostart with Windows."""
        if sys.platform != "win32":
            logger.warning("Autostart is only supported on Windows")
            return False
            
        try:
            import winreg
            
            # Get path to current script
            script_path = os.path.abspath(sys.argv[0])
            
            # Use pythonw for background execution
            if script_path.endswith(".py"):
                cmd = f'pythonw "{script_path}" --start'
            else:
                cmd = f'"{script_path}" --start'
            
            # Open registry key
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Run",
                0,
                winreg.KEY_SET_VALUE | winreg.KEY_QUERY_VALUE
            )
            
            if enable:
                # Add to startup
                winreg.SetValueEx(key, "ContinuousRecorder", 0, winreg.REG_SZ, cmd)
                logger.info("Added to Windows startup")
            else:
                # Remove from startup
                try:
                    winreg.DeleteValue(key, "ContinuousRecorder")
                    logger.info("Removed from Windows startup")
                except:
                    pass
            
            winreg.CloseKey(key)
            
            # Update config
            self.config["general"]["run_on_startup"] = enable
            self._save_config()
            
            return True
        except Exception as e:
            logger.error(f"Error configuring autostart: {e}")
            return False

def main():
    """Main entry point for the application."""
    parser = argparse.ArgumentParser(description="Continuous Audio Recorder")
    
    # Command-line arguments
    parser.add_argument("--start", action="store_true", help="Start recording immediately")
    parser.add_argument("--stop", action="store_true", help="Stop recording")
    parser.add_argument("--pause", action="store_true", help="Pause recording")
    parser.add_argument("--resume", action="store_true", help="Resume recording")
    parser.add_argument("--status", action="store_true", help="Show current status")
    parser.add_argument("--list-devices", action="store_true", help="List available audio devices")
    parser.add_argument("--set-device", type=int, help="Set recording device by index")
    parser.add_argument("--set-quality", choices=["high", "medium", "low"], help="Set audio quality")
    parser.add_argument("--set-mono", type=bool, help="Set mono/stereo mode")
    parser.add_argument("--set-monitor", type=float, help="Set monitor level (0.0 to 1.0)")
    parser.add_argument("--autostart", type=bool, help="Configure autostart with Windows")
    parser.add_argument("--config", type=str, default="config.ini", help="Path to configuration file")
    
    args = parser.parse_args()
    
    # Create recorder instance
    recorder = AudioRecorder(config_path=args.config)
    
    # Process commands
    if args.list_devices:
        recorder.list_devices()
    elif args.set_device is not None:
        if recorder.set_device(args.set_device):
            print(f"Recording device set to index {args.set_device}")
        else:
            print(f"Failed to set recording device to index {args.set_device}")
    elif args.set_quality is not None:
        if recorder.set_audio_quality(args.set_quality):
            print(f"Audio quality set to {args.set_quality}")
        else:
            print(f"Failed to set audio quality to {args.set_quality}")
    elif args.set_mono is not None:
        if recorder.set_mono(args.set_mono):
            print(f"Recording mode set to {'mono' if args.set_mono else 'stereo'}")
        else:
            print(f"Failed to set recording mode")
    elif args.set_monitor is not None:
        if recorder.set_monitor_level(args.set_monitor):
            print(f"Monitor level set to {args.set_monitor}")
        else:
            print(f"Failed to set monitor level")
    elif args.autostart is not None:
        if recorder.setup_autostart(args.autostart):
            print(f"Autostart {'enabled' if args.autostart else 'disabled'}")
        else:
            print("Failed to configure autostart")

    # Process command-line arguments
    if args.start:
        recorder.start_recording()
    elif args.stop:
        recorder.stop_recording()
    elif args.pause:
        recorder.paused = True
        logger.info("Recording paused")
    elif args.resume:
        recorder.paused = False
        logger.info("Recording resumed")
    elif args.status:
        status = recorder.get_status()
        print(f"Recording status: {status}")

if __name__ == "__main__":
    main() 
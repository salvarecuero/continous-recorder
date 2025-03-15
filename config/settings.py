"""
Configuration settings module for the Continuous Audio Recorder.
"""

import os
import configparser

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

def load_config(config_path="config.ini"):
    """Load configuration from file or use defaults."""
    config = DEFAULT_CONFIG.copy()
    
    if os.path.exists(config_path):
        parser = configparser.ConfigParser()
        parser.read(config_path)
        
        # Update config with values from file
        if "general" in parser:
            config["general"]["retention_days"] = parser.getint("general", "retention_days", fallback=config["general"]["retention_days"])
            config["general"]["recording_hours"] = parser.getint("general", "recording_hours", fallback=config["general"]["recording_hours"])
            config["general"]["run_on_startup"] = parser.getboolean("general", "run_on_startup", fallback=config["general"]["run_on_startup"])
            config["general"]["minimize_to_tray"] = parser.getboolean("general", "minimize_to_tray", fallback=config["general"]["minimize_to_tray"])
        
        if "audio" in parser:
            config["audio"]["format"] = parser.get("audio", "format", fallback=config["audio"]["format"])
            config["audio"]["sample_rate"] = parser.getint("audio", "sample_rate", fallback=config["audio"]["sample_rate"])
            config["audio"]["channels"] = parser.getint("audio", "channels", fallback=config["audio"]["channels"])
            config["audio"]["chunk_size"] = parser.getint("audio", "chunk_size", fallback=config["audio"]["chunk_size"])
            
            device_index = parser.get("audio", "device_index", fallback=None)
            if device_index is not None and device_index.lower() != "none":
                try:
                    config["audio"]["device_index"] = int(device_index)
                except ValueError:
                    config["audio"]["device_index"] = None
            
            config["audio"]["quality"] = parser.get("audio", "quality", fallback=config["audio"]["quality"])
            config["audio"]["mono"] = parser.getboolean("audio", "mono", fallback=config["audio"]["mono"])
            config["audio"]["monitor_level"] = parser.getfloat("audio", "monitor_level", fallback=config["audio"]["monitor_level"])
        
        if "paths" in parser:
            config["paths"]["recordings_dir"] = parser.get("paths", "recordings_dir", fallback=config["paths"]["recordings_dir"])
            config["paths"]["ffmpeg_path"] = parser.get("paths", "ffmpeg_path", fallback=config["paths"]["ffmpeg_path"])
    
    return config

def save_config(config, config_path="config.ini"):
    """Save configuration to file."""
    parser = configparser.ConfigParser()
    
    # General section
    parser.add_section("general")
    parser.set("general", "retention_days", str(config["general"]["retention_days"]))
    parser.set("general", "recording_hours", str(config["general"]["recording_hours"]))
    parser.set("general", "run_on_startup", str(config["general"]["run_on_startup"]))
    parser.set("general", "minimize_to_tray", str(config["general"]["minimize_to_tray"]))
    
    # Audio section
    parser.add_section("audio")
    parser.set("audio", "format", config["audio"]["format"])
    parser.set("audio", "sample_rate", str(config["audio"]["sample_rate"]))
    parser.set("audio", "channels", str(config["audio"]["channels"]))
    parser.set("audio", "chunk_size", str(config["audio"]["chunk_size"]))
    
    if config["audio"]["device_index"] is not None:
        parser.set("audio", "device_index", str(config["audio"]["device_index"]))
    else:
        parser.set("audio", "device_index", "None")
    
    parser.set("audio", "quality", config["audio"]["quality"])
    parser.set("audio", "mono", str(config["audio"]["mono"]))
    parser.set("audio", "monitor_level", str(config["audio"]["monitor_level"]))
    
    # Paths section
    parser.add_section("paths")
    parser.set("paths", "recordings_dir", config["paths"]["recordings_dir"])
    parser.set("paths", "ffmpeg_path", config["paths"]["ffmpeg_path"])
    
    # Write to file
    with open(config_path, 'w') as f:
        parser.write(f)
    
    return True 
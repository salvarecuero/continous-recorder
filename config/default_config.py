"""
Default configuration settings for the Continuous Audio Recorder.
"""

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
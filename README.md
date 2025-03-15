# Continuous Audio Recorder

A Python application that continuously records audio from system output, saving recordings in configurable time blocks and managing storage.

## Features

- Record audio from any system output device
- WASAPI loopback support for Windows
- Configurable recording quality and format
- Automatic file management with retention policies
- GUI with system tray support
- Headless mode for background recording
- Monitor audio while recording

## Installation

### Requirements

- Python 3.7 or higher
- FFmpeg (for MP3 conversion)

### Setup

1. Clone the repository:

   ```
   git clone https://github.com/yourusername/continuous-recorder.git
   cd continuous-recorder
   ```

2. Install dependencies:

   ```
   pip install -r requirements.txt
   ```

3. Run the application:
   ```
   python main.py
   ```

### Windows Installation

On Windows, you can use the provided installation script:

```
install.bat
```

This will install all required dependencies and create shortcuts for starting the recorder.

## Usage

### GUI Mode

Run the application without any arguments to start in GUI mode:

```
python main.py
```

The GUI provides controls for:

- Starting, stopping, and pausing recording
- Selecting audio devices
- Configuring audio quality and format
- Setting storage options
- Viewing recording status

### Headless Mode

Run the application in headless mode for background recording:

```
python main.py --headless
```

### Command Line Options

```
python main.py --help
```

Available options:

- `--config PATH`: Path to configuration file (default: config.ini)
- `--headless`: Run in headless mode (no GUI)
- `--list-devices`: List available audio devices and exit
- `--device INDEX`: Device index to use for recording

## Configuration

The application uses a configuration file (config.ini) with the following sections:

### General Settings

```ini
[general]
retention_days = 90
recording_hours = 3
run_on_startup = True
minimize_to_tray = True
```

- `retention_days`: Number of days to keep recordings
- `recording_hours`: Duration of each recording block
- `run_on_startup`: Whether to run on system startup
- `minimize_to_tray`: Whether to minimize to system tray

### Audio Settings

```ini
[audio]
sample_rate = 44100
channels = 2
chunk_size = 1024
device_index = 0
quality = high
mono = False
monitor_level = 0.0
```

- `sample_rate`: Sample rate in Hz
- `channels`: Number of audio channels
- `chunk_size`: Audio buffer size
- `device_index`: Index of the recording device
- `quality`: MP3 quality (high, medium, low)
- `mono`: Whether to record in mono
- `monitor_level`: Level for audio monitoring (0.0-1.0)

### Path Settings

```ini
[paths]
recordings_dir = Recordings
ffmpeg_path = ffmpeg
```

- `recordings_dir`: Directory to store recordings
- `ffmpeg_path`: Path to FFmpeg executable

## Project Structure

The project has been refactored into a modular structure:

```
continuous-recorder/
├── config/
│   ├── __init__.py
│   ├── default_config.py
│   └── config_manager.py
├── core/
│   ├── __init__.py
│   ├── audio_recorder.py
│   ├── audio_processor.py
│   ├── device_manager.py
│   └── file_manager.py
├── utils/
│   ├── __init__.py
│   ├── logging_setup.py
│   └── system_utils.py
├── gui/
│   ├── __init__.py
│   ├── main_window.py
│   ├── status_panel.py
│   └── settings_panel.py
├── main.py
└── requirements.txt
```

## License

This project is licensed under the MIT License - see the LICENSE file for details.

# Continuous Audio Recorder

A Windows application that continuously records system audio output, splitting files by time periods and managing storage with automatic cleanup of old recordings.

## Features

- Records system audio output using WASAPI loopback devices
- Automatically splits recordings into time-based files
- Manages storage by cleaning up old recordings
- Supports WAV and MP3 formats (requires FFmpeg for MP3)
- GUI and command-line interfaces
- Minimizes to system tray
- Autostart with Windows

## Requirements

- Windows 10 or later
- Python 3.7 or later
- PyAudioWPatch library
- FFmpeg (optional, for MP3 conversion)

## Installation

1. Clone or download this repository
2. Install the required dependencies:

```
pip install pyaudiowpatch pillow pystray
```

3. (Optional) Download FFmpeg from [ffmpeg.org](https://ffmpeg.org/download.html) and place the executable in the same directory or add it to your PATH.

## Usage

### GUI Interface

Run the GUI application:

```
python recorder_gui.py
```

The GUI provides the following features:

- Select recording device
- Start, stop, and pause recording
- Configure settings (retention period, recording duration, format)
- View recording status and logs

### Command-line Interface

Run the command-line interface:

```
python continuous_recorder.py [options]
```

Available options:

- `--start`: Start recording immediately
- `--stop`: Stop recording
- `--pause`: Pause recording
- `--resume`: Resume recording
- `--status`: Show current status
- `--list-devices`: List available audio devices
- `--set-device INDEX`: Set recording device by index
- `--autostart BOOL`: Configure autostart with Windows
- `--config PATH`: Path to configuration file

### Interactive Mode

Run the application without arguments to enter interactive mode:

```
python continuous_recorder.py
```

Available commands:

- `start`: Start recording
- `stop`: Stop recording
- `pause`: Pause recording
- `resume`: Resume recording
- `status`: Show current status
- `devices`: List available audio devices
- `device INDEX`: Set recording device by index
- `autostart true/false`: Configure autostart
- `exit`: Exit the application

## Configuration

The application uses a configuration file (`config.ini`) with the following settings:

### General

- `retention_days`: Number of days to keep recordings (default: 90)
- `recording_hours`: Duration of each recording file in hours (default: 3)
- `run_on_startup`: Whether to run the application at Windows startup (default: true)
- `minimize_to_tray`: Whether to minimize to system tray (default: true)

### Audio

- `format`: Output format, either "wav" or "mp3" (default: "mp3")
- `sample_rate`: Sample rate in Hz (default: 44100)
- `channels`: Number of audio channels (default: 2)
- `chunk_size`: Audio buffer size (default: 1024)
- `device_index`: Index of the recording device (default: auto-detect)

### Paths

- `recordings_dir`: Directory to store recordings (default: "Recordings")
- `ffmpeg_path`: Path to FFmpeg executable (default: "ffmpeg")

## Troubleshooting

### No audio is being recorded

- Make sure you have selected a loopback device
- Check if the selected device is the one playing audio
- Try a different loopback device

### FFmpeg conversion fails

- Make sure FFmpeg is installed and accessible
- Check the logs for specific error messages

### Application crashes

- Check the logs in the `logs` directory for error details
- Make sure you have the latest version of PyAudioWPatch

## License

This project is licensed under the MIT License - see the LICENSE file for details.

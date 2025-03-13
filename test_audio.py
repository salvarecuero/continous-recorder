#!/usr/bin/env python3
"""
Test script for PyAudioWPatch to verify that it can record system audio.
"""

import os
import time
import wave
import pyaudiowpatch as pyaudio

def main():
    print("PyAudioWPatch Test Script")
    print("=" * 50)
    
    # Initialize PyAudio
    p = pyaudio.PyAudio()
    
    # List all available devices
    print("\nAvailable Audio Devices:")
    print("-" * 50)
    
    for i in range(p.get_device_count()):
        device_info = p.get_device_info_by_index(i)
        host_api = p.get_host_api_info_by_index(device_info.get('hostApi', 0))
        host_api_name = host_api.get('name', 'Unknown')
        
        print(f"Device {i}: {device_info['name']}")
        print(f"  Host API: {host_api_name}")
        print(f"  Input Channels: {device_info['maxInputChannels']}")
        print(f"  Output Channels: {device_info['maxOutputChannels']}")
        print(f"  Default Sample Rate: {device_info['defaultSampleRate']}")
        print("-" * 50)
    
    # Find loopback devices
    loopback_devices = []
    for i in range(p.get_device_count()):
        device_info = p.get_device_info_by_index(i)
        if "[Loopback]" in device_info['name']:
            loopback_devices.append((i, device_info))
    
    if not loopback_devices:
        print("No loopback devices found!")
        return
    
    # Select the first loopback device
    device_index = loopback_devices[0][0]
    device_info = loopback_devices[0][1]
    print(f"\nUsing loopback device: {device_info['name']} (index {device_index})")
    
    # Set up recording parameters
    sample_rate = int(device_info['defaultSampleRate'])
    channels = min(2, device_info['maxInputChannels'])
    chunk_size = 1024
    record_seconds = 5
    
    print(f"\nRecording parameters:")
    print(f"  Sample Rate: {sample_rate} Hz")
    print(f"  Channels: {channels}")
    print(f"  Duration: {record_seconds} seconds")
    
    # Start recording
    print("\nStarting recording for 5 seconds...")
    frames = []
    
    try:
        # Open the stream with basic parameters
        stream = p.open(
            format=pyaudio.paInt16,
            channels=channels,
            rate=sample_rate,
            input=True,
            frames_per_buffer=chunk_size,
            input_device_index=device_index
        )
        
        print("Recording...")
        for i in range(0, int(sample_rate / chunk_size * record_seconds)):
            data = stream.read(chunk_size)
            frames.append(data)
            if i % 10 == 0:
                print(".", end="", flush=True)
        print("\nFinished recording!")
        
        # Stop and close the stream
        stream.stop_stream()
        stream.close()
        
        # Save the recorded data as a WAV file
        output_file = "test_recording.wav"
        print(f"\nSaving to {output_file}...")
        
        wf = wave.open(output_file, 'wb')
        wf.setnchannels(channels)
        wf.setsampwidth(p.get_sample_size(pyaudio.paInt16))
        wf.setframerate(sample_rate)
        wf.writeframes(b''.join(frames))
        wf.close()
        
        file_size = os.path.getsize(output_file)
        print(f"File saved successfully! Size: {file_size} bytes")
    except Exception as e:
        print(f"Error: {e}")
    
    # Terminate PyAudio
    p.terminate()

if __name__ == "__main__":
    main() 
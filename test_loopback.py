#!/usr/bin/env python3
"""
Test script for PyAudioWPatch loopback recording based on the official example.
"""

import os
import time
import wave
import pyaudiowpatch as pyaudio

DURATION = 5.0
CHUNK_SIZE = 1024
filename = "loopback_record.wav"

def main():
    print("PyAudioWPatch Loopback Test")
    print("=" * 50)
    
    with pyaudio.PyAudio() as p:
        try:
            # Get default WASAPI info
            wasapi_info = p.get_host_api_info_by_type(pyaudio.paWASAPI)
            print(f"WASAPI info: {wasapi_info}")
        except OSError:
            print("Looks like WASAPI is not available on the system. Exiting...")
            exit()
        
        # Get default WASAPI speakers
        default_speakers = p.get_device_info_by_index(wasapi_info["defaultOutputDevice"])
        print(f"Default speakers: {default_speakers['name']} (index {default_speakers['index']})")
        
        if not default_speakers.get("isLoopbackDevice", False):
            print("Looking for loopback device...")
            loopback_found = False
            
            for loopback in p.get_loopback_device_info_generator():
                print(f"Found loopback device: {loopback['name']} (index {loopback['index']})")
                
                if default_speakers["name"] in loopback["name"]:
                    default_speakers = loopback
                    loopback_found = True
                    print(f"Selected loopback device: {default_speakers['name']} (index {default_speakers['index']})")
                    break
            
            if not loopback_found:
                print("Default loopback output device not found. Exiting...")
                exit()
        
        print(f"\nRecording from: ({default_speakers['index']}) {default_speakers['name']}")
        print(f"Channels: {default_speakers['maxInputChannels']}")
        print(f"Sample Rate: {int(default_speakers['defaultSampleRate'])}")
        
        wave_file = wave.open(filename, 'wb')
        wave_file.setnchannels(default_speakers["maxInputChannels"])
        wave_file.setsampwidth(pyaudio.get_sample_size(pyaudio.paInt16))
        wave_file.setframerate(int(default_speakers["defaultSampleRate"]))
        
        def callback(in_data, frame_count, time_info, status):
            """Write frames and return PA flag"""
            wave_file.writeframes(in_data)
            return (in_data, pyaudio.paContinue)
        
        print(f"\nOpening stream...")
        with p.open(format=pyaudio.paInt16,
                channels=default_speakers["maxInputChannels"],
                rate=int(default_speakers["defaultSampleRate"]),
                frames_per_buffer=CHUNK_SIZE,
                input=True,
                input_device_index=default_speakers["index"],
                stream_callback=callback
        ) as stream:
            print(f"The next {DURATION} seconds will be written to {filename}")
            print("Recording...")
            
            # Show progress
            for i in range(int(DURATION)):
                print(f"{i+1}...", end=" ", flush=True)
                time.sleep(1)
            
            print("\nFinished recording!")
        
        wave_file.close()
        
        # Check file size
        file_size = os.path.getsize(filename)
        print(f"\nFile saved: {filename}")
        print(f"File size: {file_size} bytes")
        
        if file_size > 1000:
            print("Recording successful!")
        else:
            print("Warning: File size is very small, recording may not have worked properly.")

if __name__ == "__main__":
    main() 
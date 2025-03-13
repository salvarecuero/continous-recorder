#!/usr/bin/env python3
"""
Test script for the continuous recorder.
This script will start a recording for a specified duration and then stop it.
"""

import os
import sys
import time
import argparse
import logging
import continuous_recorder as recorder

# Configure logging to see detailed output
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def main():
    """Main entry point for the test script."""
    parser = argparse.ArgumentParser(description="Test Continuous Audio Recorder")
    
    # Command-line arguments
    parser.add_argument("--duration", type=int, default=10, help="Recording duration in seconds")
    parser.add_argument("--device", type=int, help="Device index to use for recording")
    parser.add_argument("--quality", choices=["high", "medium", "low"], help="Audio quality level")
    parser.add_argument("--mono", type=bool, help="Use mono recording")
    parser.add_argument("--monitor", type=float, help="Monitor level (0.0 to 1.0)")
    parser.add_argument("--list-devices", action="store_true", help="List available audio devices")
    
    args = parser.parse_args()
    
    # Create recorder instance
    rec = recorder.AudioRecorder()
    
    if args.list_devices:
        rec.list_devices()
        return
    
    # Set device if specified
    if args.device is not None:
        if not rec.set_device(args.device):
            print(f"Failed to set device {args.device}")
            return
    
    # Set audio quality if specified
    if args.quality is not None:
        if not rec.set_audio_quality(args.quality):
            print(f"Failed to set audio quality to {args.quality}")
            return
    
    # Set mono/stereo mode if specified
    if args.mono is not None:
        if not rec.set_mono(args.mono):
            print(f"Failed to set mono mode to {args.mono}")
            return
    
    # Set monitor level if specified
    if args.monitor is not None:
        if not rec.set_monitor_level(args.monitor):
            print(f"Failed to set monitor level to {args.monitor}")
            return
    
    # Start recording
    print(f"Starting recording for {args.duration} seconds...")
    if not rec.start_recording():
        print("Failed to start recording")
        return
    
    # Wait for the specified duration
    for i in range(args.duration, 0, -1):
        print(f"Recording... {i} seconds remaining", end="\r")
        time.sleep(1)
    
    print("\nStopping recording...")
    rec.stop_recording()
    
    print("Recording completed.")
    
    # Show the status
    status = rec.get_status()
    print("\nFinal Status:")
    print("-" * 50)
    print(f"Recording: {'Yes' if status['recording'] else 'No'}")
    print(f"Device Index: {status['device_index']}")
    print(f"Last File: {status['current_file']}")
    print(f"Audio Quality: {rec.config['audio']['quality']}")
    print(f"Mono Mode: {'Yes' if rec.config['audio']['mono'] else 'No'}")
    print(f"Monitor Level: {rec.config['audio']['monitor_level']}")
    print("-" * 50)

if __name__ == "__main__":
    main() 
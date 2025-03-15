#!/usr/bin/env python3
"""
Continuous Audio Recorder - Main Entry Point

This application records audio from system output continuously,
saving recordings in configurable time blocks and managing storage.
"""

import os
import sys
import argparse
import tkinter as tk
import logging

from utils.logging_setup import setup_logger
from core.audio_recorder import AudioRecorder
from gui.main_window import RecorderGUI

def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Continuous Audio Recorder")
    
    parser.add_argument(
        "--config", 
        type=str, 
        default="config.ini",
        help="Path to configuration file"
    )
    
    parser.add_argument(
        "--headless", 
        action="store_true",
        help="Run in headless mode (no GUI)"
    )
    
    parser.add_argument(
        "--list-devices", 
        action="store_true",
        help="List available audio devices and exit"
    )
    
    parser.add_argument(
        "--device", 
        type=int, 
        help="Device index to use for recording"
    )
    
    parser.add_argument(
        "--start", 
        action="store_true",
        help="Start recording immediately"
    )
    
    parser.add_argument(
        "--stop", 
        action="store_true",
        help="Stop recording"
    )
    
    parser.add_argument(
        "--pause", 
        action="store_true",
        help="Pause recording"
    )
    
    parser.add_argument(
        "--resume", 
        action="store_true",
        help="Resume recording"
    )
    
    parser.add_argument(
        "--status", 
        action="store_true",
        help="Show current status"
    )
    
    return parser.parse_args()

def run_gui(config_path):
    """Run the application with GUI."""
    # Create root window
    root = tk.Tk()
    
    # Create GUI
    app = RecorderGUI(root)
    
    # Start main loop
    root.mainloop()

def run_headless(config_path, device_index=None, start=False):
    """Run the application in headless mode."""
    # Create recorder
    recorder = AudioRecorder(config_path)
    
    # Set device if specified
    if device_index is not None:
        recorder.set_device(device_index)
    
    # Start recording if requested
    if start:
        if recorder.start_recording():
            logger.info("Recording started in headless mode")
            
            # Keep running until interrupted
            try:
                import time
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                logger.info("Keyboard interrupt received, stopping recording")
                recorder.stop_recording()
        else:
            logger.error("Failed to start recording")
            return 1
    
    return 0

def list_devices():
    """List available audio devices and exit."""
    # Create recorder
    recorder = AudioRecorder()
    
    # List devices
    recorder.list_devices()
    
    return 0

def send_command(command):
    """Send a command to a running instance."""
    # Create recorder
    recorder = AudioRecorder()
    
    # Send command
    if recorder._send_command(command):
        logger.info(f"Sent command: {command}")
        return 0
    else:
        logger.error(f"Failed to send command: {command}")
        return 1

def main():
    """Main entry point."""
    # Parse arguments
    args = parse_arguments()
    
    # Setup logger
    global logger
    logger = setup_logger()
    
    # List devices if requested
    if args.list_devices:
        return list_devices()
    
    # Send commands to running instance
    if args.stop:
        return send_command("stop")
    
    if args.pause:
        return send_command("pause")
    
    if args.resume:
        return send_command("resume")
    
    if args.status:
        # Create recorder
        recorder = AudioRecorder()
        
        # Get status
        status = recorder.get_status()
        
        # Print status
        print("\nRecording Status:")
        print("----------------")
        print(f"Recording: {'Yes' if status['recording'] else 'No'}")
        print(f"Paused: {'Yes' if status['paused'] else 'No'}")
        print(f"Device: {status['device_name']} (Index: {status['device_index']})")
        print(f"Sample Rate: {status['sample_rate']} Hz")
        print(f"Format: {status['format'].upper()}")
        print(f"Channels: {status['channels']}")
        print(f"Quality: {status['quality']}")
        print(f"Mono: {'Yes' if status['mono'] else 'No'}")
        print(f"Monitor Level: {int(status['monitor_level'] * 100)}%")
        print(f"Current File: {status['current_file']}")
        print(f"Recordings Directory: {status['recordings_dir']}")
        print(f"Retention Days: {status['retention_days']}")
        print(f"Recording Hours: {status['recording_hours']}")
        
        # Display new information
        print("\nStorage Information:")
        print("-------------------")
        if status['current_file']:
            print(f"Current Block Size: {recorder.format_file_size(status['current_block_size'])}")
        
        # Display estimated storage requirements
        print(f"Estimated Block Size ({status['recording_hours']} hours): {recorder.format_file_size(status['estimated_block_size'])}")
        print(f"Estimated Daily Storage: {recorder.format_file_size(status['estimated_day_size'])}")
        print(f"Estimated 90-Day Storage: {recorder.format_file_size(status['estimated_90day_size'])}")
        
        # Display current recordings folder size
        print(f"Current Recordings Folder Size: {recorder.format_file_size(status['recordings_folder_size'])}")
        
        # Display free disk space
        print(f"Free Disk Space: {recorder.format_file_size(status['free_disk_space'])}")
        
        # Display retention fit information if available
        if "retention_fit" in status:
            fit_info = status["retention_fit"]
            if fit_info["fits"]:
                print(f"Retention Period Would Fit: Yes (Using {fit_info['percentage']:.1f}% of free space)")
            else:
                print(f"Retention Period Would Fit: No (Need {recorder.format_file_size(fit_info['needed_space'])})")
        
        print()
        
        return 0
    
    # Run in headless mode if requested
    if args.headless:
        return run_headless(args.config, args.device, args.start)
    
    # Run GUI
    run_gui(args.config)
    return 0

if __name__ == "__main__":
    sys.exit(main()) 
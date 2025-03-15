"""
Status panel for the Continuous Audio Recorder GUI.
"""

import tkinter as tk
from tkinter import ttk
import time
import datetime

class StatusPanel:
    """Panel for displaying recorder status information."""
    
    def __init__(self, parent, recorder):
        """
        Initialize the status panel.
        
        Args:
            parent: Parent widget
            recorder: AudioRecorder instance
        """
        self.recorder = recorder
        
        # Create frame
        self.frame = ttk.Frame(parent, padding="10")
        
        # Create status widgets
        self._create_widgets()
        
        # Initialize status
        self.update_status(self.recorder.get_status())
    
    def _create_widgets(self):
        """Create the status panel widgets."""
        # Status grid
        status_frame = ttk.LabelFrame(self.frame, text="Recorder Status")
        status_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Recording status
        ttk.Label(status_frame, text="Status:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.status_label = ttk.Label(status_frame, text="Stopped")
        self.status_label.grid(row=0, column=1, sticky=tk.W, padx=5, pady=5)
        
        # Recording device
        ttk.Label(status_frame, text="Device:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.device_label = ttk.Label(status_frame, text="None")
        self.device_label.grid(row=1, column=1, sticky=tk.W, padx=5, pady=5)
        
        # Sample rate
        ttk.Label(status_frame, text="Sample Rate:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        self.sample_rate_label = ttk.Label(status_frame, text="44100 Hz")
        self.sample_rate_label.grid(row=2, column=1, sticky=tk.W, padx=5, pady=5)
        
        # Format
        ttk.Label(status_frame, text="Format:").grid(row=3, column=0, sticky=tk.W, padx=5, pady=5)
        self.format_label = ttk.Label(status_frame, text="MP3")
        self.format_label.grid(row=3, column=1, sticky=tk.W, padx=5, pady=5)
        
        # Channels
        ttk.Label(status_frame, text="Channels:").grid(row=4, column=0, sticky=tk.W, padx=5, pady=5)
        self.channels_label = ttk.Label(status_frame, text="2 (Stereo)")
        self.channels_label.grid(row=4, column=1, sticky=tk.W, padx=5, pady=5)
        
        # Quality
        ttk.Label(status_frame, text="Quality:").grid(row=5, column=0, sticky=tk.W, padx=5, pady=5)
        self.quality_label = ttk.Label(status_frame, text="High")
        self.quality_label.grid(row=5, column=1, sticky=tk.W, padx=5, pady=5)
        
        # Current file
        ttk.Label(status_frame, text="Current File:").grid(row=6, column=0, sticky=tk.W, padx=5, pady=5)
        self.file_label = ttk.Label(status_frame, text="None")
        self.file_label.grid(row=6, column=1, sticky=tk.W, padx=5, pady=5)
        
        # Recording time
        ttk.Label(status_frame, text="Recording Time:").grid(row=7, column=0, sticky=tk.W, padx=5, pady=5)
        self.time_label = ttk.Label(status_frame, text="00:00:00")
        self.time_label.grid(row=7, column=1, sticky=tk.W, padx=5, pady=5)
        
        # Storage info frame
        storage_frame = ttk.LabelFrame(self.frame, text="Storage Information")
        storage_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Recordings directory
        ttk.Label(storage_frame, text="Recordings Directory:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.dir_label = ttk.Label(storage_frame, text="Recordings")
        self.dir_label.grid(row=0, column=1, sticky=tk.W, padx=5, pady=5)
        
        # Retention period
        ttk.Label(storage_frame, text="Retention Period:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.retention_label = ttk.Label(storage_frame, text="90 days")
        self.retention_label.grid(row=1, column=1, sticky=tk.W, padx=5, pady=5)
        
        # Recording block size
        ttk.Label(storage_frame, text="Recording Block:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        self.block_label = ttk.Label(storage_frame, text="3 hours")
        self.block_label.grid(row=2, column=1, sticky=tk.W, padx=5, pady=5)
        
        # Estimated block size
        ttk.Label(storage_frame, text="Estimated Block Size:").grid(row=3, column=0, sticky=tk.W, padx=5, pady=5)
        self.block_estimate_label = ttk.Label(storage_frame, text="0 MB")
        self.block_estimate_label.grid(row=3, column=1, sticky=tk.W, padx=5, pady=5)
        
        # Current block size
        ttk.Label(storage_frame, text="Current Block Size:").grid(row=4, column=0, sticky=tk.W, padx=5, pady=5)
        self.block_size_label = ttk.Label(storage_frame, text="0 bytes")
        self.block_size_label.grid(row=4, column=1, sticky=tk.W, padx=5, pady=5)
        
        # Estimated daily storage
        ttk.Label(storage_frame, text="Daily Storage Estimate:").grid(row=5, column=0, sticky=tk.W, padx=5, pady=5)
        self.day_size_label = ttk.Label(storage_frame, text="0 MB")
        self.day_size_label.grid(row=5, column=1, sticky=tk.W, padx=5, pady=5)
        
        # Estimated 90-day storage
        ttk.Label(storage_frame, text="90-Day Storage Estimate:").grid(row=6, column=0, sticky=tk.W, padx=5, pady=5)
        self.storage_estimate_label = ttk.Label(storage_frame, text="0 GB")
        self.storage_estimate_label.grid(row=6, column=1, sticky=tk.W, padx=5, pady=5)
        
        # Recordings folder size
        ttk.Label(storage_frame, text="Recordings Folder Size:").grid(row=7, column=0, sticky=tk.W, padx=5, pady=5)
        self.folder_size_label = ttk.Label(storage_frame, text="0 MB")
        self.folder_size_label.grid(row=7, column=1, sticky=tk.W, padx=5, pady=5)
        
        # Free disk space
        ttk.Label(storage_frame, text="Free Disk Space:").grid(row=8, column=0, sticky=tk.W, padx=5, pady=5)
        self.free_space_label = ttk.Label(storage_frame, text="0 GB")
        self.free_space_label.grid(row=8, column=1, sticky=tk.W, padx=5, pady=5)
        
        # Retention fit
        ttk.Label(storage_frame, text="Retention Would Fit:").grid(row=9, column=0, sticky=tk.W, padx=5, pady=5)
        self.retention_fit_label = ttk.Label(storage_frame, text="Calculating...")
        self.retention_fit_label.grid(row=9, column=1, sticky=tk.W, padx=5, pady=5)
        
        # Initialize recording start time
        self.recording_start_time = None
    
    def update_status(self, status):
        """
        Update the status display with current information.
        
        Args:
            status: Dictionary with status information
        """
        # Update recording status
        if status["recording"]:
            if status["paused"]:
                self.status_label.config(text="Paused")
            else:
                self.status_label.config(text="Recording")
                
                # Initialize recording start time if not set
                if self.recording_start_time is None:
                    self.recording_start_time = time.time()
        else:
            self.status_label.config(text="Stopped")
            self.recording_start_time = None
        
        # Update device info
        self.device_label.config(text=status["device_name"])
        
        # Update audio settings
        self.sample_rate_label.config(text=f"{status['sample_rate']} Hz")
        self.format_label.config(text=status["format"].upper())
        
        if status["mono"]:
            self.channels_label.config(text="1 (Mono)")
        else:
            self.channels_label.config(text=f"{status['channels']} (Stereo)")
        
        self.quality_label.config(text=status["quality"].capitalize())
        
        # Update current file
        if status["current_file"]:
            self.file_label.config(text=status["current_file"])
        else:
            self.file_label.config(text="None")
        
        # Update recording time
        if self.recording_start_time:
            elapsed = time.time() - self.recording_start_time
            hours, remainder = divmod(int(elapsed), 3600)
            minutes, seconds = divmod(remainder, 60)
            self.time_label.config(text=f"{hours:02d}:{minutes:02d}:{seconds:02d}")
        else:
            self.time_label.config(text="00:00:00")
        
        # Update storage info
        self.dir_label.config(text=status["recordings_dir"])
        self.retention_label.config(text=f"{status['retention_days']} days")
        
        recording_hours = self.recorder.config["general"]["recording_hours"]
        self.block_label.config(text=f"{recording_hours} hours")
        
        # Update estimated block size
        if "estimated_block_size" in status:
            self.block_estimate_label.config(text=self.recorder.format_file_size(status["estimated_block_size"]))
        
        # Update current block size
        if "current_block_size" in status:
            self.block_size_label.config(text=self.recorder.format_file_size(status["current_block_size"]))
        
        # Update daily storage estimate
        if "estimated_day_size" in status:
            self.day_size_label.config(text=self.recorder.format_file_size(status["estimated_day_size"]))
        
        # Update 90-day storage estimate
        if "estimated_90day_size" in status:
            self.storage_estimate_label.config(text=self.recorder.format_file_size(status["estimated_90day_size"]))
            
        # Update recordings folder size
        if "recordings_folder_size" in status:
            self.folder_size_label.config(text=self.recorder.format_file_size(status["recordings_folder_size"]))
            
        # Update free disk space
        if "free_disk_space" in status:
            self.free_space_label.config(text=self.recorder.format_file_size(status["free_disk_space"]))
            
        # Update retention fit information
        if "retention_fit" in status:
            fit_info = status["retention_fit"]
            if fit_info["fits"]:
                self.retention_fit_label.config(
                    text=f"Yes ({fit_info['percentage']:.1f}% of free space)",
                    foreground="green"
                )
            else:
                self.retention_fit_label.config(
                    text=f"No (Need {self.recorder.format_file_size(fit_info['needed_space'])})",
                    foreground="red"
                ) 
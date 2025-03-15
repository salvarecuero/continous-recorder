"""
Main GUI window for the Continuous Audio Recorder.
"""

import os
import sys
import time
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import logging
import psutil
import numpy as np
import math

# Import core components
from core.audio_recorder import AudioRecorder, HAS_WASAPI

# Get logger
logger = logging.getLogger("ContinuousRecorder")

class DbMeter(tk.Canvas):
    """A decibel meter visualization for audio levels."""
    
    def __init__(self, parent, width=200, height=20, **kwargs):
        """Initialize the dB meter."""
        super().__init__(parent, width=width, height=height, **kwargs)
        self.width = width
        self.height = height
        self.configure(bg='#1E1E1E')  # Dark background
        self.level = 0  # Current level (0-1)
        self.peak_level = 0  # Peak level
        self.peak_hold_time = 30  # Frames to hold peak
        self.peak_hold_counter = 0
        self.draw_meter()
        
    def set_level(self, level):
        """Set the current audio level (0-1)."""
        self.level = max(0, min(1, level))
        if self.level > self.peak_level:
            self.peak_level = self.level
            self.peak_hold_counter = self.peak_hold_time
        elif self.peak_hold_counter > 0:
            self.peak_hold_counter -= 1
        else:
            self.peak_level = max(0, self.peak_level - 0.01)  # Gradually decrease peak
        self.draw_meter()
    
    def draw_meter(self):
        """Draw the meter with the current level."""
        self.delete("all")
        
        # Draw background segments with rounded corners
        segment_width = self.width / 30
        segment_height = self.height - 4  # Leave space for border
        segment_spacing = 1  # Space between segments
        
        for i in range(30):
            # Determine color based on position (gradient from green to yellow to red)
            if i < 18:  # Green zone (0-60%)
                r = int(((i / 18) * 255))
                g = 255
                b = 0
                color = f"#{r:02x}{g:02x}{b:02x}"
            elif i < 27:  # Yellow zone (60-90%)
                r = 255
                g = int(255 - ((i - 18) / 9) * 255)
                b = 0
                color = f"#{r:02x}{g:02x}{b:02x}"
            else:  # Red zone (90-100%)
                color = "#FF0000"
            
            # Draw segment if it's within the current level
            if i / 30 <= self.level:
                x = 2 + i * segment_width
                y = 2
                # Draw rounded rectangle
                self.create_rectangle(
                    x, y,
                    x + segment_width - segment_spacing, y + segment_height,
                    fill=color, outline="", width=0,
                    tags="segment"
                )
        
        # Draw peak indicator
        peak_x = 2 + self.peak_level * (self.width - 4)
        self.create_line(
            peak_x, 2, peak_x, self.height - 2,
            fill="white", width=2
        )
        
        # Draw border
        self.create_rectangle(
            1, 1, self.width - 1, self.height - 1,
            outline="#444444", width=1
        )
        
        # Draw dB scale markers
        for db in [-60, -50, -40, -30, -20, -10, -3, 0]:
            # Convert dB to linear position (0-1)
            if db == -60:  # Minimum visible level
                pos = 0
            else:
                pos = (db + 60) / 60  # Scale -60dB to 0dB to 0-1 range
            
            x = 2 + pos * (self.width - 4)
            self.create_line(x, self.height-6, x, self.height-2, fill="#888888")
            if db in [-60, -30, -10, 0]:  # Only show some labels to avoid clutter
                self.create_text(x, self.height/2, text=f"{db}", fill="#BBBBBB", font=("", 7))

class RecorderGUI:
    """GUI wrapper for the Continuous Audio Recorder."""
    
    def __init__(self, root):
        """Initialize the GUI."""
        try:
            self.root = root
            self.root.title("Continuous Audio Recorder")
            self.log("GUI initialization started")
            
            # Set icon if available
            try:
                self.log("Setting window icon")
                self.root.iconbitmap("recorder.ico")
                self.log("Window icon set")
            except Exception as e:
                self.log(f"Failed to set icon: {e}")
            
            # Initialize recorder
            self.log("Initializing audio recorder")
            self.recorder = AudioRecorder()
            self.log("Audio recorder initialized")
            
            # Create scrollable canvas
            self.log("Creating scrollable frame")
            self.create_scrollable_frame()
            self.log("Scrollable frame created")
            
            # Create GUI elements
            self.log("Creating widgets")
            self.create_widgets()
            self.log("Widgets created")
            
            # Setup update timer
            self.log("Setting up status update timer")
            self.update_status()
            self.log("Status update timer set up")
            
            # Handle window close
            self.log("Setting up window close handler")
            self.root.protocol("WM_DELETE_WINDOW", self.on_close)
            self.log("Window close handler set up")
            
            # Minimize to tray if configured
            if self.recorder.config["general"]["minimize_to_tray"]:
                self.log("Setting up tray icon")
                self.setup_tray_icon()
                self.log("Tray icon set up")
            
            # Update window size after widgets are created
            self.log("Updating root window")
            self.root.update()
            self.log("Root window updated")
            
            self.log("Adjusting window size")
            self.adjust_window_size()
            self.log("Window size adjusted")
            
            self.log("Starting resource monitor")
            self.start_resource_monitor()
            self.log("Resource monitor started")
            
            self.log("GUI initialization completed")
        except Exception as e:
            if hasattr(self, 'log'):
                self.log(f"Error during GUI initialization: {e}")
                import traceback
                self.log(f"Traceback: {traceback.format_exc()}")
            else:
                print(f"Error during GUI initialization (before log was available): {e}")
                import traceback
                print(f"Traceback: {traceback.format_exc()}")
    
    def create_scrollable_frame(self):
        """Create a scrollable frame for the application content."""
        # Create outer frame to hold canvas and scrollbar
        self.outer_frame = ttk.Frame(self.root)
        self.outer_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create canvas with scrollbar
        self.canvas = tk.Canvas(self.outer_frame)
        self.scrollbar = ttk.Scrollbar(self.outer_frame, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = ttk.Frame(self.canvas)
        
        # Configure canvas
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self._update_scrollregion()
        )
        
        # Create window in canvas
        self.canvas_window = self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        
        # Configure canvas to expand with window
        self.canvas.configure(yscrollcommand=self._update_scrollbar)
        
        # Pack canvas and scrollbar
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")
        
        # Bind canvas resize to window resize
        self.canvas.bind("<Configure>", self.on_canvas_resize)
        
        # Bind mousewheel for scrolling
        self.bind_mousewheel()
    
    def _update_scrollregion(self):
        """Update the scroll region of the canvas."""
        self.log("Updating scroll region")
        try:
            self.log("Configuring canvas scrollregion")
            self.canvas.configure(scrollregion=self.canvas.bbox("all"))
            self.log("Canvas scrollregion configured")
            
            self.log("Updating scrollbar visibility")
            self._update_scrollbar_visibility()
            self.log("Scrollbar visibility updated")
        except Exception as e:
            self.log(f"Error in _update_scrollregion: {e}")
            import traceback
            self.log(f"Traceback: {traceback.format_exc()}")
    
    def _update_scrollbar(self, *args):
        """Update the scrollbar position."""
        self.scrollbar.set(*args)
        self._update_scrollbar_visibility()
    
    def _update_scrollbar_visibility(self):
        """Show or hide scrollbar based on content height."""
        self.log("Updating scrollbar visibility")
        try:
            # Get canvas and content heights
            self.log("Getting canvas height")
            canvas_height = self.canvas.winfo_height()
            self.log(f"Canvas height: {canvas_height}")
            
            self.log("Getting content height")
            content_height = self.scrollable_frame.winfo_reqheight()
            self.log(f"Content height: {content_height}")
            
            # Show scrollbar only if content is taller than canvas
            self.log(f"Comparing heights: content {content_height} vs canvas {canvas_height}")
            if content_height > canvas_height:
                self.log("Content taller than canvas, showing scrollbar")
                self.scrollbar.pack(side="right", fill="y")
            else:
                self.log("Content not taller than canvas, hiding scrollbar")
                self.scrollbar.pack_forget()
            self.log("Scrollbar visibility update complete")
        except Exception as e:
            self.log(f"Error in _update_scrollbar_visibility: {e}")
            import traceback
            self.log(f"Traceback: {traceback.format_exc()}")
    
    def on_canvas_resize(self, event):
        """Handle canvas resize event."""
        # Update the width of the canvas window to match the canvas width
        canvas_width = event.width
        self.canvas.itemconfig(self.canvas_window, width=canvas_width)
        
        # Update scrollbar visibility
        self._update_scrollbar_visibility()
    
    def bind_mousewheel(self):
        """Bind mousewheel events for scrolling."""
        def _on_mousewheel_windows(event):
            # Windows mousewheel event
            self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        
        def _on_mousewheel_linux(event):
            # Linux mousewheel event
            if event.num == 4:
                self.canvas.yview_scroll(-1, "units")
            elif event.num == 5:
                self.canvas.yview_scroll(1, "units")
        
        def _on_mousewheel_macos(event):
            # macOS mousewheel event
            self.canvas.yview_scroll(int(-1 * event.delta), "units")
        
        # Bind for different platforms
        if sys.platform == "win32":
            self.canvas.bind_all("<MouseWheel>", _on_mousewheel_windows)
        elif sys.platform == "darwin":
            self.canvas.bind_all("<MouseWheel>", _on_mousewheel_macos)
        else:
            # Linux and other platforms
            self.canvas.bind_all("<Button-4>", _on_mousewheel_linux)
            self.canvas.bind_all("<Button-5>", _on_mousewheel_linux)
    
    def adjust_window_size(self):
        """Adjust the window size based on content."""
        self.log("Adjusting window size")
        try:
            # Update the scrollregion
            self.log("Calling _update_scrollregion")
            self._update_scrollregion()
            self.log("Returned from _update_scrollregion")
            
            # Get screen dimensions
            self.log("Getting screen dimensions")
            screen_width = self.root.winfo_screenwidth()
            screen_height = self.root.winfo_screenheight()
            self.log(f"Screen dimensions: {screen_width}x{screen_height}")
            
            # Calculate desired window size (80% of screen size)
            desired_width = int(screen_width * 0.8)
            desired_height = int(screen_height * 0.8)
            
            # Get the required size for the content
            self.log("Getting content size")
            self.scrollable_frame.update_idletasks()
            content_width = self.scrollable_frame.winfo_reqwidth()
            content_height = self.scrollable_frame.winfo_reqheight()
            self.log(f"Content size: {content_width}x{content_height}")
            
            # Add padding for scrollbars and window decorations
            padding_width = 50
            padding_height = 50
            
            # Calculate window size
            window_width = min(desired_width, content_width + padding_width)
            window_height = min(desired_height, content_height + padding_height)
            
            # Ensure minimum size
            window_width = max(window_width, 800)  # Minimum width of 800 pixels
            window_height = max(window_height, 600)  # Minimum height of 600 pixels
            self.log(f"Calculated window size: {window_width}x{window_height}")
            
            # Set window size
            self.log("Setting window geometry")
            self.root.geometry(f"{window_width}x{window_height}")
            
            # Center window on screen
            x = (screen_width - window_width) // 2
            y = (screen_height - window_height) // 2
            self.root.geometry(f"+{x}+{y}")
            self.log(f"Window positioned at {x},{y}")
            
            # Update scrollregion again after resize
            self.log("Updating idletasks")
            self.root.update_idletasks()
            self.log("Calling _update_scrollregion again")
            self._update_scrollregion()
            self.log("Window size adjustment complete")
        except Exception as e:
            self.log(f"Error in adjust_window_size: {e}")
            import traceback
            self.log(f"Traceback: {traceback.format_exc()}")
    
    def create_widgets(self):
        """Create the GUI widgets."""
        # Initialize labels dictionary
        self.labels = {}
        
        # Create styles for colored labels
        self._create_colored_styles()
        
        # Main frame
        main_frame = ttk.Frame(self.scrollable_frame, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Status frame with improved styling
        status_frame = ttk.LabelFrame(main_frame, text="Status", padding="10")
        status_frame.pack(fill=tk.X, pady=5)
        
        # Status indicators with better styling
        status_header_frame = ttk.Frame(status_frame)
        status_header_frame.pack(fill=tk.X, pady=5)
        
        self.status_var = tk.StringVar(value="Stopped")
        ttk.Label(status_header_frame, text="Recording Status:", font=("", 10, "bold")).pack(side=tk.LEFT, padx=5)
        self.status_label = ttk.Label(status_header_frame, textvariable=self.status_var, font=("", 10, "bold"))
        self.status_label.pack(side=tk.LEFT, padx=5)
        
        self.device_var = tk.StringVar(value="No device selected")
        ttk.Label(status_header_frame, text="Device:", font=("", 10, "bold")).pack(side=tk.LEFT, padx=(20, 5))
        device_label = ttk.Label(status_header_frame, textvariable=self.device_var)
        device_label.pack(side=tk.LEFT, padx=5)
        
        # Add dB meter visualization
        db_frame = ttk.Frame(status_frame)
        db_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(db_frame, text="Audio Level:", font=("", 9, "bold")).pack(side=tk.LEFT, padx=5)
        self.db_meter = DbMeter(db_frame, width=400, height=30, highlightthickness=0)
        self.db_meter.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        self.db_level_var = tk.StringVar(value="-∞ dB")
        ttk.Label(db_frame, textvariable=self.db_level_var, width=8).pack(side=tk.LEFT, padx=5)
        
        # Storage info frame with two columns
        storage_frame = ttk.LabelFrame(main_frame, text="Recording Information", padding="10")
        storage_frame.pack(fill=tk.X, pady=5)
        
        # Create two column frames
        left_column = ttk.Frame(storage_frame)
        left_column.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        right_column = ttk.Frame(storage_frame)
        right_column.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Left column items
        # Current block size
        self._create_info_row(left_column, "Current Block Size:", "block_size_var", "0 bytes")
        
        # Recording time duration
        self._create_info_row(left_column, "Recording Time:", "recording_time_var", "00:00:00")
        
        # Time until next block
        self._create_info_row(left_column, "Time Until Next Block:", "next_block_var", "00:00:00")
        
        # Estimated block size
        self._create_info_row(left_column, "Estimated Block Size:", "block_estimate_var", "0 MB")
        
        # Right column items
        # Daily storage estimate
        self._create_info_row(right_column, "Daily Storage Estimate:", "day_size_var", "0 MB")
        
        # 90-day storage estimate
        self._create_info_row(right_column, "90-Day Storage Estimate:", "storage_estimate_var", "0 GB")
        
        # Recordings folder size
        self._create_info_row(right_column, "Recordings Folder Size:", "folder_size_var", "0 MB")
        
        # Free disk space
        self._create_info_row(right_column, "Free Disk Space:", "free_space_var", "0 GB")
        
        # Retention fit
        self._create_info_row(right_column, "Retention Would Fit:", "retention_fit_var", "Calculating...")
        self.retention_fit_label = self.labels["retention_fit_var"]
        
        # Control frame
        control_frame = ttk.LabelFrame(main_frame, text="Controls", padding="10")
        control_frame.pack(fill=tk.X, pady=5)
        
        # Control buttons
        self.start_button = ttk.Button(control_frame, text="Start Recording", command=self.start_recording)
        self.start_button.pack(side=tk.LEFT, padx=5)
        
        self.stop_button = ttk.Button(control_frame, text="Stop Recording", command=self.stop_recording, state=tk.DISABLED)
        self.stop_button.pack(side=tk.LEFT, padx=5)
        
        self.pause_button = ttk.Button(control_frame, text="Pause", command=self.pause_recording, state=tk.DISABLED)
        self.pause_button.pack(side=tk.LEFT, padx=5)
        
        self.resume_button = ttk.Button(control_frame, text="Resume", command=self.resume_recording, state=tk.DISABLED)
        self.resume_button.pack(side=tk.LEFT, padx=5)
        
        # Settings frame
        settings_frame = ttk.LabelFrame(main_frame, text="Settings", padding="10")
        settings_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Device selection
        device_frame = ttk.Frame(settings_frame)
        device_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(device_frame, text="Recording Device:", font=("", 9, "bold")).pack(side=tk.LEFT, padx=5)
        
        self.device_list = ttk.Combobox(device_frame, width=40, state="readonly")
        self.device_list.pack(side=tk.LEFT, padx=5)
        
        refresh_button = ttk.Button(device_frame, text="Refresh", command=self.refresh_devices)
        refresh_button.pack(side=tk.LEFT, padx=5)
        
        set_device_button = ttk.Button(device_frame, text="Set", command=self.set_device)
        set_device_button.pack(side=tk.LEFT, padx=5)
        
        # Format selection
        self.format_frame = ttk.Frame(settings_frame)
        self.format_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(self.format_frame, text="Audio Format:", font=("", 9, "bold")).pack(side=tk.LEFT, padx=5)
        
        self.format_var = tk.StringVar(value=self.recorder.config["audio"]["format"])
        format_combo = ttk.Combobox(self.format_frame, textvariable=self.format_var, state="readonly", width=10)
        format_combo["values"] = ["wav", "mp3"]
        format_combo.pack(side=tk.LEFT, padx=5)
        format_combo.bind("<<ComboboxSelected>>", self._on_format_change)
        
        set_format_button = ttk.Button(self.format_frame, text="Apply", command=self.set_audio_format)
        set_format_button.pack(side=tk.LEFT, padx=5)
        
        # Quality selection
        self.quality_frame = ttk.Frame(settings_frame)
        if self.recorder.config["audio"]["format"] == "mp3":
            self.quality_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(self.quality_frame, text="MP3 Quality:", font=("", 9, "bold")).pack(side=tk.LEFT, padx=5)
        
        self.quality_var = tk.StringVar(value=self.recorder.config["audio"]["quality"])
        self.quality_high = ttk.Radiobutton(self.quality_frame, text="High (320kbps)", variable=self.quality_var, value="high")
        self.quality_high.pack(side=tk.LEFT, padx=5)
        
        self.quality_medium = ttk.Radiobutton(self.quality_frame, text="Medium (192kbps)", variable=self.quality_var, value="medium")
        self.quality_medium.pack(side=tk.LEFT, padx=5)
        
        self.quality_low = ttk.Radiobutton(self.quality_frame, text="Low (128kbps)", variable=self.quality_var, value="low")
        self.quality_low.pack(side=tk.LEFT, padx=5)
        
        set_quality_button = ttk.Button(self.quality_frame, text="Apply", command=self.set_audio_quality)
        set_quality_button.pack(side=tk.LEFT, padx=5)
        
        # Initialize quality radio buttons state based on format
        if self.recorder.config["audio"]["format"] != "mp3":
            self.quality_high.configure(state="disabled")
            self.quality_medium.configure(state="disabled")
            self.quality_low.configure(state="disabled")
        
        # Mono/Stereo selection
        self.mono_frame = ttk.Frame(settings_frame)
        self.mono_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(self.mono_frame, text="Recording Mode:", font=("", 9, "bold")).pack(side=tk.LEFT, padx=5)
        
        self.mono_var = tk.BooleanVar(value=self.recorder.config["audio"]["mono"])
        mono_check = ttk.Checkbutton(self.mono_frame, text="Mono (reduces file size)", variable=self.mono_var)
        mono_check.pack(side=tk.LEFT, padx=5)
        
        set_mono_button = ttk.Button(self.mono_frame, text="Apply", command=self.set_mono_mode)
        set_mono_button.pack(side=tk.LEFT, padx=5)
        
        # Monitor level
        monitor_frame = ttk.Frame(settings_frame)
        monitor_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(monitor_frame, text="Monitor Level:", font=("", 9, "bold")).pack(side=tk.LEFT, padx=5)
        
        self.monitor_var = tk.DoubleVar(value=self.recorder.config["audio"]["monitor_level"])
        monitor_scale = ttk.Scale(monitor_frame, from_=0.0, to=1.0, variable=self.monitor_var, command=self.set_monitor_level)
        monitor_scale.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        self.monitor_text = tk.StringVar(value="0%")
        
        def update_monitor_text(*args):
            self.monitor_text.set(f"{int(self.monitor_var.get() * 100)}%")
        
        self.monitor_var.trace_add("write", update_monitor_text)
        
        ttk.Label(monitor_frame, textvariable=self.monitor_text, width=4).pack(side=tk.LEFT, padx=5)
        
        # Directory settings
        dir_frame = ttk.Frame(settings_frame)
        dir_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(dir_frame, text="Recordings Directory:", font=("", 9, "bold")).pack(side=tk.LEFT, padx=5)
        
        self.dir_var = tk.StringVar(value=self.recorder.config["paths"]["recordings_dir"])
        dir_entry = ttk.Entry(dir_frame, textvariable=self.dir_var, width=30)
        dir_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        browse_button = ttk.Button(dir_frame, text="Browse", command=self.browse_directory)
        browse_button.pack(side=tk.LEFT, padx=5)
        
        open_button = ttk.Button(dir_frame, text="Open", command=self.open_directory)
        open_button.pack(side=tk.LEFT, padx=5)
        
        # Retention settings
        retention_frame = ttk.Frame(settings_frame)
        retention_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(retention_frame, text="Retention Period (days):", font=("", 9, "bold")).pack(side=tk.LEFT, padx=5)
        
        self.retention_var = tk.IntVar(value=self.recorder.config["general"]["retention_days"])
        retention_entry = ttk.Entry(retention_frame, textvariable=self.retention_var, width=5)
        retention_entry.pack(side=tk.LEFT, padx=5)
        
        ttk.Label(retention_frame, text="Recording Block (hours):", font=("", 9, "bold")).pack(side=tk.LEFT, padx=5)
        
        self.block_var = tk.IntVar(value=self.recorder.config["general"]["recording_hours"])
        block_entry = ttk.Entry(retention_frame, textvariable=self.block_var, width=5)
        block_entry.pack(side=tk.LEFT, padx=5)
        
        # Autostart settings
        autostart_frame = ttk.Frame(settings_frame)
        autostart_frame.pack(fill=tk.X, pady=5)
        
        self.autostart_var = tk.BooleanVar(value=self.recorder.config["general"]["run_on_startup"])
        autostart_check = ttk.Checkbutton(autostart_frame, text="Run on system startup", variable=self.autostart_var)
        autostart_check.pack(side=tk.LEFT, padx=5)
        
        self.minimize_var = tk.BooleanVar(value=self.recorder.config["general"]["minimize_to_tray"])
        minimize_check = ttk.Checkbutton(autostart_frame, text="Minimize to system tray", variable=self.minimize_var)
        minimize_check.pack(side=tk.LEFT, padx=5)
        
        # Save settings button
        save_button = ttk.Button(settings_frame, text="Save Settings", command=self.save_settings)
        save_button.pack(anchor=tk.E, padx=5, pady=10)
        
        # Log frame
        log_frame = ttk.LabelFrame(main_frame, text="Log", padding="10")
        log_frame.pack(fill=tk.X, pady=5)
        
        # Log text
        self.log_text = tk.Text(log_frame, height=5, wrap=tk.WORD)
        self.log_text.pack(fill=tk.X, expand=False, side=tk.LEFT)
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(log_frame, command=self.log_text.yview)
        scrollbar.pack(fill=tk.Y, side=tk.RIGHT)
        self.log_text.config(yscrollcommand=scrollbar.set)
        
        # Create footer for system resources
        self.create_footer(main_frame)
        
        # Populate device list
        self.refresh_devices()
    
    def _create_info_row(self, parent, label_text, var_name, default_value):
        """Create a row with a label and value in the info section."""
        frame = ttk.Frame(parent)
        frame.pack(fill=tk.X, pady=2)
        
        ttk.Label(frame, text=label_text, font=("", 9, "bold")).pack(side=tk.LEFT, padx=5)
        
        setattr(self, var_name, tk.StringVar(value=default_value))
        label = ttk.Label(frame, textvariable=getattr(self, var_name))
        label.pack(side=tk.LEFT, padx=5)
        
        # Store label reference
        self.labels[var_name] = label
        
        return frame
    
    def create_footer(self, parent):
        """Create a fixed footer with system resource information."""
        # Footer frame
        footer_frame = ttk.Frame(parent, padding="5")
        footer_frame.pack(fill=tk.X, side=tk.BOTTOM, pady=5)
        
        # Add separator above footer
        ttk.Separator(parent, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=5)
        
        # System resources in footer
        # App CPU usage
        ttk.Label(footer_frame, text="App CPU:", font=("", 8)).pack(side=tk.LEFT, padx=(5, 0))
        self.cpu_var = tk.StringVar(value="0%")
        self.cpu_label = ttk.Label(footer_frame, textvariable=self.cpu_var, width=6, style="Normal.TLabel", font=("", 8))
        self.cpu_label.pack(side=tk.LEFT, padx=(0, 10))
        
        # System CPU usage
        ttk.Label(footer_frame, text="System CPU:", font=("", 8)).pack(side=tk.LEFT, padx=(5, 0))
        self.system_cpu_var = tk.StringVar(value="0%")
        self.system_cpu_label = ttk.Label(footer_frame, textvariable=self.system_cpu_var, width=6, style="Normal.TLabel", font=("", 8))
        self.system_cpu_label.pack(side=tk.LEFT, padx=(0, 10))
        
        # App RAM usage
        ttk.Label(footer_frame, text="App RAM:", font=("", 8)).pack(side=tk.LEFT, padx=(5, 0))
        self.ram_var = tk.StringVar(value="0 MB")
        self.ram_label = ttk.Label(footer_frame, textvariable=self.ram_var, width=8, style="Normal.TLabel", font=("", 8))
        self.ram_label.pack(side=tk.LEFT, padx=(0, 10))
        
        # System RAM usage
        ttk.Label(footer_frame, text="System RAM:", font=("", 8)).pack(side=tk.LEFT, padx=(5, 0))
        self.system_ram_var = tk.StringVar(value="0 MB / 0 GB")
        self.system_ram_label = ttk.Label(footer_frame, textvariable=self.system_ram_var, width=16, style="Normal.TLabel", font=("", 8))
        self.system_ram_label.pack(side=tk.LEFT, padx=(0, 5))
    
    def _create_colored_styles(self):
        """Create ttk styles for colored labels and better UI appearance."""
        style = ttk.Style()
        
        # Create styles for different colors
        style.configure("Normal.TLabel", foreground="black")
        style.configure("Green.TLabel", foreground="green")
        style.configure("Orange.TLabel", foreground="orange")
        style.configure("Red.TLabel", foreground="red")
        
        # Create styles for headers and titles
        style.configure("Header.TLabel", font=("", 10, "bold"))
        style.configure("Title.TLabel", font=("", 12, "bold"))
        
        # Create styles for frames
        style.configure("TLabelframe", font=("", 10, "bold"))
        style.configure("TLabelframe.Label", font=("", 10, "bold"))
        
        # Create styles for buttons
        style.configure("TButton", font=("", 9))
    
    def refresh_devices(self):
        """Refresh the list of available audio devices."""
        # Clear device list
        self.device_list.set("")
        
        # Get devices
        devices = self.recorder.list_devices()
        
        # Create device map
        self.device_map = {}
        device_names = []
        
        for device in devices:
            # Create display name
            name = device["name"]
            if device.get("is_default", False):
                name += " (Default)"
            if device.get("is_loopback", False):
                name += " (Loopback)"
            
            # Add to map and list
            self.device_map[name] = device["index"]
            device_names.append(name)
        
        # Update combobox
        self.device_list["values"] = device_names
        
        # Select current device
        current_device = self.recorder.device_index
        if current_device is not None:
            for name, index in self.device_map.items():
                if index == current_device:
                    self.device_list.set(name)
                    break
        
        # Log
        self.log(f"Found {len(devices)} audio devices XDDDD")
    
    def set_device(self):
        """Set the recording device."""
        # Get selected device
        device_name = self.device_list.get()
        if not device_name:
            messagebox.showerror("Error", "No device selected")
            return
        
        # Get device index
        device_index = self.device_map.get(device_name)
        if device_index is None:
            messagebox.showerror("Error", "Invalid device selected")
            return
        
        # Set device
        if self.recorder.set_device(device_index):
            self.log(f"Set recording device to {device_name}")
            
            # Force immediate dB meter update
            self._force_db_meter_update()
        else:
            messagebox.showerror("Error", "Failed to set recording device")
    
    def _force_db_meter_update(self):
        """Force an immediate update of the dB meter."""
        try:
            # Reset the last update time to force update
            self.last_db_update = 0
            
            # Check if the device is still valid
            device_valid = self.recorder.is_device_valid()
            
            if not device_valid:
                self.db_meter.set_level(0)
                self.db_level_var.set("-∞ dB")
                # Handle invalid device
                self._handle_invalid_device()
                return
            
            # Device is valid, get the level
            level = self.recorder.get_device_level()
            
            # Update meter with the level
            self.db_meter.set_level(level)
            
            # Only show dB value if we have a valid level
            if level > 0:
                # Estimate dB from level
                db = (level * 60) - 60
                self.db_level_var.set(f"{db:.1f} dB")
            else:
                self.db_level_var.set("-∞ dB")
        except Exception as e:
            logger.error(f"Error forcing dB meter update: {e}")
            # Set meter to zero in case of error
            self.db_meter.set_level(0)
            self.db_level_var.set("-∞ dB")
            
            # Try to handle the device error
            self._handle_invalid_device()
    
    def _on_format_change(self, event):
        """Handle format selection changes."""
        format_value = self.format_var.get()
        if format_value == "mp3":
            # Show and enable quality selection
            self.quality_frame.pack_forget()  # Remove first to ensure proper ordering
            self.quality_frame.pack(fill=tk.X, pady=5, after=self.format_frame, before=self.mono_frame)
            
            # Enable the quality radio buttons
            self.quality_high.configure(state="normal")
            self.quality_medium.configure(state="normal")
            self.quality_low.configure(state="normal")
        else:
            # Hide quality selection for WAV format
            self.quality_frame.pack_forget()
    
    def set_audio_format(self):
        """Set audio format."""
        format_value = self.format_var.get()
        self.recorder.config["audio"]["format"] = format_value
        self.recorder._save_config()
        self.log(f"Audio format set to {format_value.upper()}")
        
        # Update quality radio buttons state
        self._on_format_change(None)
        
        # Immediately update storage-related stats
        self._update_storage_stats()
    
    def set_audio_quality(self):
        """Set the audio quality."""
        quality = self.quality_var.get()
        self.recorder.config["audio"]["quality"] = quality
        if self.recorder._save_config():
            self.log(f"Set audio quality to {quality}")
            # Immediately update storage-related stats
            self._update_storage_stats()
        else:
            messagebox.showerror("Error", "Failed to set audio quality")
    
    def set_mono_mode(self):
        """Set mono/stereo recording mode."""
        mono = self.mono_var.get()
        if self.recorder.set_mono(mono):
            self.log(f"Set recording mode to {'mono' if mono else 'stereo'}")
            # Immediately update storage-related stats
            self._update_storage_stats()
        else:
            messagebox.showerror("Error", "Failed to set recording mode")
    
    def set_monitor_level(self, *args):
        """Set the monitor level."""
        level = self.monitor_var.get()
        self.recorder.set_monitor_level(level)
    
    def start_recording(self):
        """Start recording."""
        # Check if device is selected
        if self.recorder.device_index is None:
            messagebox.showerror("Error", "No recording device selected")
            return
        
        # Start recording
        if self.recorder.start_recording():
            # Initialize recording start time
            self.recording_start_time = time.time()
            
            # Update UI
            self.start_button.config(state=tk.DISABLED)
            self.stop_button.config(state=tk.NORMAL)
            self.pause_button.config(state=tk.NORMAL)
            self.resume_button.config(state=tk.DISABLED)
            
            # Log
            self.log("Recording started")
        else:
            messagebox.showerror("Error", "Failed to start recording")
    
    def stop_recording(self):
        """Stop recording."""
        if self.recorder.stop_recording():
            # Reset recording start time
            self.recording_start_time = None
            
            # Update UI
            self.start_button.config(state=tk.NORMAL)
            self.stop_button.config(state=tk.DISABLED)
            self.pause_button.config(state=tk.DISABLED)
            self.resume_button.config(state=tk.DISABLED)
            
            # Log
            self.log("Recording stopped")
        else:
            messagebox.showerror("Error", "Failed to stop recording")
    
    def pause_recording(self):
        """Pause recording."""
        if self.recorder.pause_recording():
            # Store elapsed time when pausing
            if hasattr(self, 'recording_start_time') and self.recording_start_time is not None:
                self.paused_elapsed_time = time.time() - self.recording_start_time
            
            # Update UI
            self.pause_button.config(state=tk.DISABLED)
            self.resume_button.config(state=tk.NORMAL)
            
            # Log
            self.log("Recording paused")
        else:
            messagebox.showerror("Error", "Failed to pause recording")
    
    def resume_recording(self):
        """Resume recording."""
        if self.recorder.resume_recording():
            # Adjust recording start time when resuming
            if hasattr(self, 'paused_elapsed_time'):
                self.recording_start_time = time.time() - self.paused_elapsed_time
            
            # Update UI
            self.pause_button.config(state=tk.NORMAL)
            self.resume_button.config(state=tk.DISABLED)
            
            # Log
            self.log("Recording resumed")
        else:
            messagebox.showerror("Error", "Failed to resume recording")
    
    def save_settings(self):
        """Save settings."""
        try:
            # Store original values to check for changes
            original_retention = self.recorder.config["general"]["retention_days"]
            original_recording_hours = self.recorder.config["general"]["recording_hours"]
            original_format = self.recorder.config["audio"]["format"]
            original_quality = self.recorder.config["audio"]["quality"]
            
            # Update config
            self.recorder.config["general"]["retention_days"] = self.retention_var.get()
            self.recorder.config["general"]["recording_hours"] = self.block_var.get()
            self.recorder.config["general"]["run_on_startup"] = self.autostart_var.get()
            self.recorder.config["general"]["minimize_to_tray"] = self.minimize_var.get()
            self.recorder.config["paths"]["recordings_dir"] = self.dir_var.get()
            self.recorder.config["audio"]["format"] = self.format_var.get()
            self.recorder.config["audio"]["quality"] = self.quality_var.get()
            
            # Save config
            if self.recorder._save_config():
                # Configure autostart
                if self.autostart_var.get() != self.recorder.config["general"]["run_on_startup"]:
                    self.recorder.setup_autostart(self.autostart_var.get())
                
                # Create recordings directory
                os.makedirs(self.recorder.config["paths"]["recordings_dir"], exist_ok=True)
                
                # Check if storage-related settings changed
                if (original_retention != self.recorder.config["general"]["retention_days"] or
                    original_recording_hours != self.recorder.config["general"]["recording_hours"] or
                    original_format != self.recorder.config["audio"]["format"] or
                    original_quality != self.recorder.config["audio"]["quality"]):
                    # Update storage stats immediately
                    self._update_storage_stats()
                
                # Log
                self.log("Settings saved")
            else:
                messagebox.showerror("Error", "Failed to save settings")
        except Exception as e:
            messagebox.showerror("Error", f"Error saving settings: {e}")
    
    def browse_directory(self):
        """Browse for recordings directory."""
        directory = filedialog.askdirectory(
            initialdir=self.dir_var.get(),
            title="Select Recordings Directory"
        )
        
        if directory:
            # Update directory variable
            self.dir_var.set(directory)
            
            # Update folder size immediately
            self._update_folder_stats()
    
    def open_directory(self):
        """Open recordings directory."""
        directory = self.dir_var.get()
        
        if not os.path.exists(directory):
            messagebox.showerror("Error", f"Directory does not exist: {directory}")
            return
        
        # Open directory in file explorer
        try:
            if sys.platform == "win32":
                os.startfile(directory)
            elif sys.platform == "darwin":
                os.system(f"open '{directory}'")
            else:
                os.system(f"xdg-open '{directory}'")
        except Exception as e:
            messagebox.showerror("Error", f"Error opening directory: {e}")
    
    def update_status(self):
        """Update status display."""
        try:
            current_time = int(time.time())
            
            # Get recorder status - only do this every second to reduce overhead
            if not hasattr(self, 'last_status_update') or current_time - self.last_status_update >= 1:
                self.last_status_update = current_time
                status = self.recorder.get_status()
                
                # Update status label
                self.status_var.set(status["status"])
                
                # Set status label color
                if status["status"] == "Recording":
                    self.status_label.configure(foreground="green")
                elif status["status"] == "Paused":
                    self.status_label.configure(foreground="orange")
                else:
                    self.status_label.configure(foreground="black")
                
                # Update device label
                if status["device"]:
                    self.device_var.set(status["device"])
                
                # Update recording time
                if status["recording_time"]:
                    hours, remainder = divmod(int(status["recording_time"]), 3600)
                    minutes, seconds = divmod(remainder, 60)
                    self.recording_time_var.set(f"{hours:02d}:{minutes:02d}:{seconds:02d}")
                else:
                    self.recording_time_var.set("00:00:00")
                
                # Update time until next block
                if status["next_block_time"]:
                    hours, remainder = divmod(int(status["next_block_time"]), 3600)
                    minutes, seconds = divmod(remainder, 60)
                    self.next_block_var.set(f"{hours:02d}:{minutes:02d}:{seconds:02d}")
                else:
                    self.next_block_var.set("00:00:00")
                
                # Update current block size
                if status["recording"] or status["paused"]:
                    block_size = self.recorder.get_current_block_size()
                    self.block_size_var.set(self.recorder.format_file_size(block_size))
                else:
                    self.block_size_var.set("0 bytes")
            
            # Update less frequently changing stats (every 10 seconds)
            if not hasattr(self, 'last_stats_update') or current_time - self.last_stats_update >= 10:
                self.last_stats_update = current_time
                
                # Update estimated block size
                block_size = self.recorder.calculate_block_size()
                self.block_estimate_var.set(self.recorder.format_file_size(block_size))
                
                # Update daily storage estimate
                day_size = self.recorder.calculate_day_size()
                self.day_size_var.set(self.recorder.format_file_size(day_size))
                
                # Update 90-day storage estimate
                storage_size = self.recorder.calculate_90day_size()
                self.storage_estimate_var.set(self.recorder.format_file_size(storage_size))
                
                # Update recordings folder size
                folder_size = self.recorder.get_recordings_folder_size()
                self.folder_size_var.set(self.recorder.format_file_size(folder_size))
                
                # Update free disk space
                free_space = self.recorder.get_free_disk_space()
                self.free_space_var.set(self.recorder.format_file_size(free_space))
                
                # Update retention fit
                retention_fit = self.recorder.would_retention_fit()
                if retention_fit["fits"]:
                    self.retention_fit_var.set(f"Yes (Using {retention_fit['percentage']:.1f}% of free space)")
                    self.retention_fit_label.configure(style="Green.TLabel")
                else:
                    self.retention_fit_var.set(f"No (Requires {retention_fit['percentage']:.1f}% of free space)")
                    self.retention_fit_label.configure(style="Red.TLabel")
                    
                    # Show warning if disk space is low
                    if free_space < retention_fit["needed_space"]:
                        self._show_disk_warning(free_space)
            
            # Update dB meter (every 200ms for better performance)
            current_time_ms = time.time()
            if not hasattr(self, 'last_db_update') or current_time_ms - self.last_db_update >= 0.2:
                self.last_db_update = current_time_ms
                
                # Always try to update the dB meter
                try:
                    # Check if we're recording
                    if self.recorder.recording:
                        try:
                            # Get audio level using the recording method
                            rms, db, level = self.recorder.get_audio_level()
                            
                            if rms > 0:
                                # Update meter
                                self.db_meter.set_level(level)
                                
                                # Update dB text
                                self.db_level_var.set(f"{db:.1f} dB")
                            else:
                                self.db_meter.set_level(0)
                                self.db_level_var.set("-∞ dB")
                        except Exception as e:
                            # Log the error but don't crash
                            logger.error(f"Error getting audio level during recording: {e}")
                            self.db_meter.set_level(0)
                            self.db_level_var.set("-∞ dB")
                    else:
                        # When not recording, get audio level from device directly
                        level = self.recorder.get_device_level()
                        
                        # Update meter with the level
                        self.db_meter.set_level(level)
                        
                        # Only show dB value if we have a valid level
                        if level > 0:
                            # Estimate dB from level
                            db = (level * 60) - 60
                            self.db_level_var.set(f"{db:.1f} dB")
                        else:
                            self.db_level_var.set("-∞ dB")
                            
                            # Check device validity occasionally when we get a zero level
                            if not hasattr(self, 'last_zero_check') or current_time_ms - self.last_zero_check >= 5.0:
                                self.last_zero_check = current_time_ms
                                if not self.recorder.is_device_valid():
                                    self._handle_invalid_device()
                except Exception as e:
                    # Log the error but don't crash
                    logger.error(f"Error updating dB meter: {e}")
                    self.db_meter.set_level(0)
                    self.db_level_var.set("-∞ dB")
            
            # Schedule next update (300ms is a good balance between responsiveness and performance)
            self.root.after(300, self.update_status)
        except Exception as e:
            logger.error(f"Error updating status: {e}")
            # Schedule next update even if there was an error
            self.root.after(1000, self.update_status)
    
    def start_resource_monitor(self):
        """Start monitoring system resources."""
        try:
            # Get process
            self.process = psutil.Process()
            
            # Update resources
            self.update_resource_monitor()
        except Exception as e:
            logger.error(f"Error in start_resource_monitor: {e}")
    
    def update_resource_monitor(self):
        """Update resource monitor display."""
        try:
            # Get CPU usage (percent) - interval=None to avoid blocking
            cpu_percent = self.process.cpu_percent(interval=None)
            self.cpu_var.set(f"{cpu_percent:.1f}%")
            
            # Set color based on CPU usage
            self._set_label_color(self.cpu_label, cpu_percent)
            
            # Get memory usage (MB) - only once per update
            memory_info = self.process.memory_info()
            memory_mb = memory_info.rss / (1024 * 1024)
            self.ram_var.set(f"{memory_mb:.1f} MB")
            
            # Get system memory info - only once per update
            system_ram = psutil.virtual_memory()
            total_ram = system_ram.total / (1024 * 1024)
            
            # Set color based on RAM usage
            ram_percent = (memory_mb / total_ram) * 100
            self._set_label_color(self.ram_label, ram_percent)
            
            # Get system-wide CPU usage - non-blocking
            system_cpu = psutil.cpu_percent(interval=None)
            self.system_cpu_var.set(f"{system_cpu:.1f}%")
            
            # Set color based on system CPU usage
            self._set_label_color(self.system_cpu_label, system_cpu)
            
            # Format system RAM usage
            used_ram_gb = system_ram.used / (1024 * 1024 * 1024)
            total_ram_gb = system_ram.total / (1024 * 1024 * 1024)
            self.system_ram_var.set(f"{used_ram_gb:.1f}/{total_ram_gb:.1f} GB")
            
            # Set color based on system RAM usage percentage
            system_ram_percent = system_ram.percent
            self._set_label_color(self.system_ram_label, system_ram_percent)
        except Exception as e:
            logger.error(f"Error updating resource monitor: {e}")
        
        # Schedule next update (5 seconds is enough for system stats)
        self.root.after(5000, self.update_resource_monitor)
    
    def _set_label_color(self, label, percent):
        """Set label color based on usage percentage."""
        if percent < 50:
            label.configure(style="Green.TLabel")
        elif percent < 80:
            label.configure(style="Orange.TLabel")
        else:
            label.configure(style="Red.TLabel")
    
    def _show_disk_warning(self, free_space):
        """Show a warning dialog for critically low disk space."""
        messagebox.showwarning(
            "Critical Disk Space Warning",
            f"Disk space is critically low!\n\n"
            f"Only {self.recorder.format_file_size(free_space)} remaining.\n\n"
            f"Please free up disk space or reduce the retention period to avoid data loss."
        )
    
    def log(self, message):
        """Add message to log."""
        # Add timestamp
        timestamp = time.strftime("%H:%M:%S")
        log_message = f"[{timestamp}] {message}\n"
        
        # Add to log text widget if it exists
        if hasattr(self, 'log_text') and self.log_text is not None:
            try:
                self.log_text.insert(tk.END, log_message)
                self.log_text.see(tk.END)
            except Exception as e:
                print(f"Error writing to log_text: {e}")
        else:
            print(log_message.strip())  # Print to console if log_text doesn't exist yet
        
        # Log to logger
        logger.info(message)
    
    def setup_tray_icon(self):
        """Setup system tray icon."""
        try:
            import pystray
            from PIL import Image, ImageDraw
            
            # Create icon image
            icon_image = Image.new("RGB", (64, 64), color="red")
            draw = ImageDraw.Draw(icon_image)
            draw.ellipse((10, 10, 54, 54), fill="white")
            draw.ellipse((20, 20, 44, 44), fill="red")
            
            # Define menu items
            def on_quit(icon, item):
                icon.stop()
                self.on_close()
            
            def on_show(icon, item):
                icon.stop()
                self.root.after(0, self.root.deiconify)
            
            # Create menu
            menu = pystray.Menu(
                pystray.MenuItem("Show", on_show),
                pystray.MenuItem("Quit", on_quit)
            )
            
            # Create icon
            self.tray_icon = pystray.Icon("recorder", icon_image, "Continuous Recorder", menu)
            
            # Setup minimize handler
            def on_minimize():
                self.root.withdraw()
                self.tray_icon.run()
            
            # Bind to minimize event
            self.root.bind("<Unmap>", lambda e: on_minimize() if self.recorder.config["general"]["minimize_to_tray"] and e.widget is self.root else None)
            
        except ImportError:
            logger.warning("pystray not available, system tray icon disabled")
            self.tray_icon = None
    
    def on_close(self):
        """Handle window close event."""
        if self.recorder.recording:
            if messagebox.askyesno("Confirm Exit", "Recording is in progress. Stop recording and exit?"):
                self.recorder.stop_recording()
                self.root.destroy()
        else:
            self.root.destroy()
    
    def _update_storage_stats(self):
        """Update all storage-related statistics immediately."""
        try:
            # Update estimated block size
            block_size = self.recorder.calculate_block_size()
            self.block_estimate_var.set(self.recorder.format_file_size(block_size))
            
            # Update daily storage estimate
            day_size = self.recorder.calculate_day_size()
            self.day_size_var.set(self.recorder.format_file_size(day_size))
            
            # Update 90-day storage estimate
            storage_size = self.recorder.calculate_90day_size()
            self.storage_estimate_var.set(self.recorder.format_file_size(storage_size))
            
            # Update recordings folder size
            folder_size = self.recorder.get_recordings_folder_size()
            self.folder_size_var.set(self.recorder.format_file_size(folder_size))
            
            # Update free disk space
            free_space = self.recorder.get_free_disk_space()
            self.free_space_var.set(self.recorder.format_file_size(free_space))
            
            # Update retention fit
            retention_fit = self.recorder.would_retention_fit()
            if retention_fit["fits"]:
                self.retention_fit_var.set(f"Yes (Using {retention_fit['percentage']:.1f}% of free space)")
                self.retention_fit_label.configure(style="Green.TLabel")
            else:
                self.retention_fit_var.set(f"No (Requires {retention_fit['percentage']:.1f}% of free space)")
                self.retention_fit_label.configure(style="Red.TLabel")
                
                # Show warning if disk space is low
                if free_space < retention_fit["needed_space"]:
                    self._show_disk_warning(free_space)
                    
            # Update last stats update time to prevent immediate re-update
            self.last_stats_update = int(time.time())
        except Exception as e:
            logger.error(f"Error updating storage stats: {e}")
    
    def _update_folder_stats(self):
        """Update folder-related statistics immediately."""
        try:
            # Update recordings folder size
            folder_size = self.recorder.get_recordings_folder_size()
            self.folder_size_var.set(self.recorder.format_file_size(folder_size))
            
            # Update free disk space
            free_space = self.recorder.get_free_disk_space()
            self.free_space_var.set(self.recorder.format_file_size(free_space))
            
            # Update retention fit
            retention_fit = self.recorder.would_retention_fit()
            if retention_fit["fits"]:
                self.retention_fit_var.set(f"Yes (Using {retention_fit['percentage']:.1f}% of free space)")
                self.retention_fit_label.configure(style="Green.TLabel")
            else:
                self.retention_fit_var.set(f"No (Requires {retention_fit['percentage']:.1f}% of free space)")
                self.retention_fit_label.configure(style="Red.TLabel")
        except Exception as e:
            logger.error(f"Error updating folder stats: {e}")
    
    def _handle_invalid_device(self):
        """Handle the case where the device is invalid or unavailable.
        
        This method will show a message to the user and reset the device selection.
        It will also try to select an alternative device automatically.
        """
        # Only show the message once per session
        if not hasattr(self, '_device_error_shown') or not self._device_error_shown:
            self._device_error_shown = True
            
            # Try to select an alternative device
            if self._try_select_alternative_device():
                return
            
            # If we couldn't select an alternative device, show a message
            # Show message in a non-blocking way
            self.root.after(100, lambda: messagebox.showwarning(
                "Audio Device Error",
                "The selected audio device is no longer available or is invalid.\n\n"
                "This could be because the device was disconnected, is being used by another application, "
                "or there was a system change.\n\n"
                "Please select a different audio device from the list."
            ))
            
            # Reset device selection in the UI
            self.device_var.set("No device selected")
            
            # Log the event
            logger.info("Audio device is invalid or unavailable, user notification shown")
    
    def _try_select_alternative_device(self):
        """Try to select an alternative device if the current one is invalid.
        
        This method will try to find a working device and select it automatically.
        
        Returns:
            bool: True if a working device was found and set, False otherwise
        """
        logger.info("Trying to select an alternative device")
        
        # Use the new find_working_device method
        if self.recorder.find_working_device():
            # Get the new device info
            device_index = self.recorder.device_index
            device_info = self.recorder.get_device_info()
            device_name = device_info["name"] if device_info else "Unknown device"
            
            logger.info(f"New device selected: {device_name} (index {device_index})")
            
            # Update the device selection in the UI
            for name, index in self.device_map.items():
                if index == device_index:
                    self.device_list.set(name)
                    self.device_var.set(device_name)
                    break
            
            # Show a message to the user
            self.root.after(100, lambda: messagebox.showinfo(
                "Device Changed",
                f"The previous audio device was unavailable.\n\n"
                f"The application has automatically switched to: {device_name}"
            ))
            
            # Reset the device error flag
            self._device_error_shown = False
            
            return True
        
        # If we couldn't find a working device, refresh the device list in the UI
        self.refresh_devices()
        
        logger.warning("No working devices found")
        return False

def main():
    """Main entry point for the GUI."""
    # Create root window
    root = tk.Tk()
    
    # Create GUI
    app = RecorderGUI(root)
    
    # Start main loop
    root.mainloop()

if __name__ == "__main__":
    main() 
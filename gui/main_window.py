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

# Import core components
from core.audio_recorder import AudioRecorder, HAS_WASAPI

# Get logger
logger = logging.getLogger("ContinuousRecorder")

class RecorderGUI:
    """GUI wrapper for the Continuous Audio Recorder."""
    
    def __init__(self, root):
        """Initialize the GUI."""
        self.root = root
        self.root.title("Continuous Audio Recorder")
        
        # Set icon if available
        try:
            self.root.iconbitmap("recorder.ico")
        except:
            pass
        
        # Initialize recorder
        self.recorder = AudioRecorder()
        
        # Create scrollable canvas
        self.create_scrollable_frame()
        
        # Create GUI elements
        self.create_widgets()
        
        # Setup update timer
        self.update_status()
        
        # Handle window close
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        
        # Minimize to tray if configured
        if self.recorder.config["general"]["minimize_to_tray"]:
            self.setup_tray_icon()
        
        # Update window size after widgets are created
        self.root.update()
        self.adjust_window_size()
    
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
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        self._update_scrollbar_visibility()
    
    def _update_scrollbar(self, *args):
        """Update the scrollbar position."""
        self.scrollbar.set(*args)
        self._update_scrollbar_visibility()
    
    def _update_scrollbar_visibility(self):
        """Show or hide scrollbar based on content height."""
        # Get canvas and content heights
        canvas_height = self.canvas.winfo_height()
        content_height = self.scrollable_frame.winfo_reqheight()
        
        # Show scrollbar only if content is taller than canvas
        if content_height > canvas_height:
            self.scrollbar.pack(side="right", fill="y")
        else:
            self.scrollbar.pack_forget()
    
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
        """Adjust window size to fit content."""
        # Wait for all widgets to be properly measured
        self.root.update_idletasks()
        
        # Get required height for all widgets
        required_height = self.scrollable_frame.winfo_reqheight() + 20  # Add some padding
        
        # Get screen dimensions
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        
        # Set window height to required height, but not more than 90% of screen height
        window_height = min(required_height, screen_height * 0.9)
        
        # Set window width (fixed width or percentage of screen width)
        window_width = min(800, screen_width * 0.7)
        
        # Set window size
        self.root.geometry(f"{int(window_width)}x{int(window_height)}")
        
        # Set minimum size
        self.root.minsize(600, 400)
        
        # Center window on screen
        x_position = (screen_width - window_width) // 2
        y_position = (screen_height - window_height) // 2
        self.root.geometry(f"+{int(x_position)}+{int(y_position)}")
        
        # Update scrollbar visibility
        self._update_scrollbar_visibility()
    
    def create_widgets(self):
        """Create the GUI widgets."""
        # Create styles for colored labels
        self._create_colored_styles()
        
        # Main frame
        main_frame = ttk.Frame(self.scrollable_frame, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Status frame
        status_frame = ttk.LabelFrame(main_frame, text="Status", padding="10")
        status_frame.pack(fill=tk.X, pady=5)
        
        # Status indicators
        self.status_var = tk.StringVar(value="Stopped")
        self.status_label = ttk.Label(status_frame, textvariable=self.status_var, font=("", 12, "bold"))
        self.status_label.pack(side=tk.LEFT, padx=5)
        
        self.device_var = tk.StringVar(value="No device selected")
        device_label = ttk.Label(status_frame, textvariable=self.device_var)
        device_label.pack(side=tk.RIGHT, padx=5)
        
        # Storage info frame
        storage_frame = ttk.LabelFrame(main_frame, text="Storage Information", padding="10")
        storage_frame.pack(fill=tk.X, pady=5)
        
        # Current block size
        block_size_frame = ttk.Frame(storage_frame)
        block_size_frame.pack(fill=tk.X, pady=2)
        ttk.Label(block_size_frame, text="Current Block Size:").pack(side=tk.LEFT, padx=5)
        self.block_size_var = tk.StringVar(value="0 bytes")
        ttk.Label(block_size_frame, textvariable=self.block_size_var).pack(side=tk.LEFT, padx=5)
        
        # Estimated block size
        block_estimate_frame = ttk.Frame(storage_frame)
        block_estimate_frame.pack(fill=tk.X, pady=2)
        ttk.Label(block_estimate_frame, text="Estimated Block Size:").pack(side=tk.LEFT, padx=5)
        self.block_estimate_var = tk.StringVar(value="0 MB")
        ttk.Label(block_estimate_frame, textvariable=self.block_estimate_var).pack(side=tk.LEFT, padx=5)
        
        # Daily storage estimate
        day_size_frame = ttk.Frame(storage_frame)
        day_size_frame.pack(fill=tk.X, pady=2)
        ttk.Label(day_size_frame, text="Daily Storage Estimate:").pack(side=tk.LEFT, padx=5)
        self.day_size_var = tk.StringVar(value="0 MB")
        ttk.Label(day_size_frame, textvariable=self.day_size_var).pack(side=tk.LEFT, padx=5)
        
        # 90-day storage estimate
        storage_estimate_frame = ttk.Frame(storage_frame)
        storage_estimate_frame.pack(fill=tk.X, pady=2)
        ttk.Label(storage_estimate_frame, text="90-Day Storage Estimate:").pack(side=tk.LEFT, padx=5)
        self.storage_estimate_var = tk.StringVar(value="0 GB")
        ttk.Label(storage_estimate_frame, textvariable=self.storage_estimate_var).pack(side=tk.LEFT, padx=5)
        
        # Recordings folder size
        folder_size_frame = ttk.Frame(storage_frame)
        folder_size_frame.pack(fill=tk.X, pady=2)
        ttk.Label(folder_size_frame, text="Recordings Folder Size:").pack(side=tk.LEFT, padx=5)
        self.folder_size_var = tk.StringVar(value="0 MB")
        ttk.Label(folder_size_frame, textvariable=self.folder_size_var).pack(side=tk.LEFT, padx=5)
        
        # Free disk space
        free_space_frame = ttk.Frame(storage_frame)
        free_space_frame.pack(fill=tk.X, pady=2)
        ttk.Label(free_space_frame, text="Free Disk Space:").pack(side=tk.LEFT, padx=5)
        self.free_space_var = tk.StringVar(value="0 GB")
        ttk.Label(free_space_frame, textvariable=self.free_space_var).pack(side=tk.LEFT, padx=5)
        
        # Retention fit
        retention_fit_frame = ttk.Frame(storage_frame)
        retention_fit_frame.pack(fill=tk.X, pady=2)
        ttk.Label(retention_fit_frame, text="Retention Would Fit:").pack(side=tk.LEFT, padx=5)
        self.retention_fit_var = tk.StringVar(value="Calculating...")
        self.retention_fit_label = ttk.Label(retention_fit_frame, textvariable=self.retention_fit_var)
        self.retention_fit_label.pack(side=tk.LEFT, padx=5)
        
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
        
        ttk.Label(device_frame, text="Recording Device:").pack(side=tk.LEFT, padx=5)
        
        self.device_list = ttk.Combobox(device_frame, width=40, state="readonly")
        self.device_list.pack(side=tk.LEFT, padx=5)
        
        refresh_button = ttk.Button(device_frame, text="Refresh", command=self.refresh_devices)
        refresh_button.pack(side=tk.LEFT, padx=5)
        
        set_device_button = ttk.Button(device_frame, text="Set", command=self.set_device)
        set_device_button.pack(side=tk.LEFT, padx=5)
        
        # Quality selection
        quality_frame = ttk.Frame(settings_frame)
        quality_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(quality_frame, text="Audio Quality:").pack(side=tk.LEFT, padx=5)
        
        self.quality_var = tk.StringVar(value=self.recorder.config["audio"]["quality"])
        quality_high = ttk.Radiobutton(quality_frame, text="High", variable=self.quality_var, value="high")
        quality_high.pack(side=tk.LEFT, padx=5)
        
        quality_medium = ttk.Radiobutton(quality_frame, text="Medium", variable=self.quality_var, value="medium")
        quality_medium.pack(side=tk.LEFT, padx=5)
        
        quality_low = ttk.Radiobutton(quality_frame, text="Low", variable=self.quality_var, value="low")
        quality_low.pack(side=tk.LEFT, padx=5)
        
        set_quality_button = ttk.Button(quality_frame, text="Apply", command=self.set_audio_quality)
        set_quality_button.pack(side=tk.LEFT, padx=5)
        
        # Mono/Stereo selection
        mono_frame = ttk.Frame(settings_frame)
        mono_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(mono_frame, text="Recording Mode:").pack(side=tk.LEFT, padx=5)
        
        self.mono_var = tk.BooleanVar(value=self.recorder.config["audio"]["mono"])
        mono_check = ttk.Checkbutton(mono_frame, text="Mono (reduces file size)", variable=self.mono_var)
        mono_check.pack(side=tk.LEFT, padx=5)
        
        set_mono_button = ttk.Button(mono_frame, text="Apply", command=self.set_mono_mode)
        set_mono_button.pack(side=tk.LEFT, padx=5)
        
        # Monitor level
        monitor_frame = ttk.Frame(settings_frame)
        monitor_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(monitor_frame, text="Monitor Level:").pack(side=tk.LEFT, padx=5)
        
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
        
        ttk.Label(dir_frame, text="Recordings Directory:").pack(side=tk.LEFT, padx=5)
        
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
        
        ttk.Label(retention_frame, text="Retention Period (days):").pack(side=tk.LEFT, padx=5)
        
        self.retention_var = tk.IntVar(value=self.recorder.config["general"]["retention_days"])
        retention_entry = ttk.Entry(retention_frame, textvariable=self.retention_var, width=5)
        retention_entry.pack(side=tk.LEFT, padx=5)
        
        ttk.Label(retention_frame, text="Recording Block (hours):").pack(side=tk.LEFT, padx=5)
        
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
        
        # System resource monitor frame
        resource_frame = ttk.LabelFrame(main_frame, text="System Resources", padding="10")
        resource_frame.pack(fill=tk.X, pady=5)
        
        # CPU usage
        cpu_frame = ttk.Frame(resource_frame)
        cpu_frame.pack(fill=tk.X, pady=2)
        ttk.Label(cpu_frame, text="CPU Usage:").pack(side=tk.LEFT, padx=5)
        self.cpu_var = tk.StringVar(value="0%")
        self.cpu_label = ttk.Label(cpu_frame, textvariable=self.cpu_var, width=8, style="Normal.TLabel")
        self.cpu_label.pack(side=tk.LEFT, padx=5)
        
        # CPU progress bar
        self.cpu_progress = ttk.Progressbar(cpu_frame, orient=tk.HORIZONTAL, length=200, mode='determinate')
        self.cpu_progress.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        # RAM usage
        ram_frame = ttk.Frame(resource_frame)
        ram_frame.pack(fill=tk.X, pady=2)
        ttk.Label(ram_frame, text="RAM Usage:").pack(side=tk.LEFT, padx=5)
        self.ram_var = tk.StringVar(value="0 MB")
        self.ram_label = ttk.Label(ram_frame, textvariable=self.ram_var, width=12, style="Normal.TLabel")
        self.ram_label.pack(side=tk.LEFT, padx=5)
        
        # RAM progress bar
        self.ram_progress = ttk.Progressbar(ram_frame, orient=tk.HORIZONTAL, length=200, mode='determinate')
        self.ram_progress.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        # Total system info
        system_frame = ttk.Frame(resource_frame)
        system_frame.pack(fill=tk.X, pady=2)
        ttk.Label(system_frame, text="System CPU:").pack(side=tk.LEFT, padx=5)
        self.system_cpu_var = tk.StringVar(value="0%")
        self.system_cpu_label = ttk.Label(system_frame, textvariable=self.system_cpu_var, width=8, style="Normal.TLabel")
        self.system_cpu_label.pack(side=tk.LEFT, padx=5)
        
        ttk.Label(system_frame, text="System RAM:").pack(side=tk.LEFT, padx=5)
        self.system_ram_var = tk.StringVar(value="0 MB / 0 GB")
        self.system_ram_label = ttk.Label(system_frame, textvariable=self.system_ram_var, width=16, style="Normal.TLabel")
        self.system_ram_label.pack(side=tk.LEFT, padx=5)
        
        # Populate device list
        self.refresh_devices()
        
        # Start resource monitoring
        self.start_resource_monitor()
    
    def _create_colored_styles(self):
        """Create ttk styles for colored labels."""
        style = ttk.Style()
        
        # Create styles for different colors
        style.configure("Normal.TLabel", foreground="black")
        style.configure("Green.TLabel", foreground="green")
        style.configure("Orange.TLabel", foreground="orange")
        style.configure("Red.TLabel", foreground="red")
    
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
        self.log(f"Found {len(devices)} audio devices")
    
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
        else:
            messagebox.showerror("Error", "Failed to set recording device")
    
    def set_audio_quality(self):
        """Set the audio quality."""
        quality = self.quality_var.get()
        if self.recorder.set_audio_quality(quality):
            self.log(f"Set audio quality to {quality}")
        else:
            messagebox.showerror("Error", "Failed to set audio quality")
    
    def set_mono_mode(self):
        """Set mono/stereo recording mode."""
        mono = self.mono_var.get()
        if self.recorder.set_mono(mono):
            self.log(f"Set recording mode to {'mono' if mono else 'stereo'}")
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
            # Update config
            self.recorder.config["general"]["retention_days"] = self.retention_var.get()
            self.recorder.config["general"]["recording_hours"] = self.block_var.get()
            self.recorder.config["general"]["run_on_startup"] = self.autostart_var.get()
            self.recorder.config["general"]["minimize_to_tray"] = self.minimize_var.get()
            self.recorder.config["paths"]["recordings_dir"] = self.dir_var.get()
            
            # Save config
            if self.recorder._save_config():
                # Configure autostart
                if self.autostart_var.get() != self.recorder.config["general"]["run_on_startup"]:
                    self.recorder.setup_autostart(self.autostart_var.get())
                
                # Create recordings directory
                os.makedirs(self.recorder.config["paths"]["recordings_dir"], exist_ok=True)
                
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
            self.dir_var.set(directory)
    
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
            # Get status
            status = self.recorder.get_status()
            
            # Update status label
            if status["recording"]:
                if status["paused"]:
                    self.status_var.set("Paused")
                    self.status_label.config(foreground="orange")
                else:
                    self.status_var.set("Recording")
                    self.status_label.config(foreground="green")
            else:
                self.status_var.set("Stopped")
                self.status_label.config(foreground="red")
            
            # Update device label
            if status["device_name"] != "Unknown":
                self.device_var.set(f"Device: {status['device_name']}")
            else:
                self.device_var.set("No device selected")
                
            # Update storage information
            if "current_block_size" in status:
                self.block_size_var.set(self.recorder.format_file_size(status["current_block_size"]))
            
            if "estimated_block_size" in status:
                self.block_estimate_var.set(self.recorder.format_file_size(status["estimated_block_size"]))
                
            if "estimated_day_size" in status:
                self.day_size_var.set(self.recorder.format_file_size(status["estimated_day_size"]))
                
            if "estimated_90day_size" in status:
                self.storage_estimate_var.set(self.recorder.format_file_size(status["estimated_90day_size"]))
                
            if "recordings_folder_size" in status:
                self.folder_size_var.set(self.recorder.format_file_size(status["recordings_folder_size"]))
                
            if "free_disk_space" in status:
                free_space = status["free_disk_space"]
                self.free_space_var.set(self.recorder.format_file_size(free_space))
                
                # Check for critically low disk space (less than 5GB or 5% of needed space for retention)
                if "retention_fit" in status:
                    retention_fit = status["retention_fit"]
                    critical_space = min(5 * 1024 * 1024 * 1024, retention_fit["needed_space"] * 0.05)
                    
                    if free_space < critical_space:
                        # Show warning dialog (but not more than once every 30 minutes)
                        current_time = time.time()
                        if not hasattr(self, '_last_disk_warning_time') or current_time - self._last_disk_warning_time > 1800:
                            self._last_disk_warning_time = current_time
                            self.log("CRITICAL: Disk space is critically low!")
                            
                            # Show warning in a separate thread to avoid blocking the UI
                            threading.Thread(target=self._show_disk_warning, args=(free_space,), daemon=True).start()
                
            # Update retention fit information
            if "retention_fit" in status:
                fit_info = status["retention_fit"]
                if fit_info["fits"]:
                    self.retention_fit_var.set(f"Yes ({fit_info['percentage']:.1f}% of free space)")
                    self.retention_fit_label.config(foreground="green")
                else:
                    self.retention_fit_var.set(f"No (Need {self.recorder.format_file_size(fit_info['needed_space'])})")
                    self.retention_fit_label.config(foreground="red")
                    
                    # Log warning if retention won't fit
                    if not hasattr(self, '_retention_warning_logged') or not self._retention_warning_logged:
                        if not fit_info["fits"]:
                            self.log("WARNING: Retention period would not fit in available disk space")
                            self._retention_warning_logged = True
                        else:
                            self._retention_warning_logged = False
        except Exception as e:
            logger.error(f"Error updating status: {e}")
        
        # Schedule next update
        self.root.after(1000, self.update_status)
    
    def start_resource_monitor(self):
        """Start monitoring system resources."""
        # Get process
        self.process = psutil.Process()
        
        # Update resources
        self.update_resource_monitor()
    
    def update_resource_monitor(self):
        """Update resource monitor display."""
        try:
            # Get CPU usage (percent)
            cpu_percent = self.process.cpu_percent(interval=0)
            self.cpu_var.set(f"{cpu_percent:.1f}%")
            self.cpu_progress['value'] = cpu_percent
            
            # Set color based on CPU usage
            self._set_label_color(self.cpu_label, cpu_percent)
            
            # Get memory usage (MB)
            memory_info = self.process.memory_info()
            memory_mb = memory_info.rss / (1024 * 1024)
            self.ram_var.set(f"{memory_mb:.1f} MB")
            
            # Calculate RAM percentage (for progress bar)
            total_ram = psutil.virtual_memory().total / (1024 * 1024)
            ram_percent = (memory_mb / total_ram) * 100
            self.ram_progress['value'] = ram_percent
            
            # Set color based on RAM usage
            self._set_label_color(self.ram_label, ram_percent)
            
            # Get system-wide CPU and RAM usage
            system_cpu = psutil.cpu_percent(interval=0)
            self.system_cpu_var.set(f"{system_cpu:.1f}%")
            
            # Set color based on system CPU usage
            self._set_label_color(self.system_cpu_label, system_cpu)
            
            system_ram = psutil.virtual_memory()
            used_ram_gb = system_ram.used / (1024 * 1024 * 1024)
            total_ram_gb = system_ram.total / (1024 * 1024 * 1024)
            self.system_ram_var.set(f"{used_ram_gb:.1f} GB / {total_ram_gb:.1f} GB")
            
            # Set color based on system RAM usage percentage
            system_ram_percent = system_ram.percent
            self._set_label_color(self.system_ram_label, system_ram_percent)
        except Exception as e:
            logger.error(f"Error updating resource monitor: {e}")
        
        # Schedule next update
        self.root.after(2000, self.update_resource_monitor)
    
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
        
        # Add to log
        self.log_text.insert(tk.END, log_message)
        self.log_text.see(tk.END)
        
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
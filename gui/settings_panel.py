"""
Settings panel for the Continuous Audio Recorder GUI.
"""

import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

class Tooltip:
    """Simple tooltip implementation for tkinter widgets."""
    
    def __init__(self, widget, text):
        """Initialize tooltip for a widget."""
        self.widget = widget
        self.text = text
        self.tooltip = None
        self.widget.bind("<Enter>", self.show_tooltip)
        self.widget.bind("<Leave>", self.hide_tooltip)
    
    def show_tooltip(self, event=None):
        """Show the tooltip."""
        x, y, _, _ = self.widget.bbox("insert")
        x += self.widget.winfo_rootx() + 25
        y += self.widget.winfo_rooty() + 25
        
        # Create tooltip window
        self.tooltip = tk.Toplevel(self.widget)
        self.tooltip.wm_overrideredirect(True)
        self.tooltip.wm_geometry(f"+{x}+{y}")
        
        # Create tooltip content
        label = ttk.Label(self.tooltip, text=self.text, background="#ffffe0", relief="solid", borderwidth=1)
        label.pack()
    
    def hide_tooltip(self, event=None):
        """Hide the tooltip."""
        if self.tooltip:
            self.tooltip.destroy()
            self.tooltip = None

class SettingsPanel:
    """Panel for configuring recorder settings."""
    
    def __init__(self, parent, recorder, save_callback):
        """
        Initialize the settings panel.
        
        Args:
            parent: Parent widget
            recorder: AudioRecorder instance
            save_callback: Function to call when settings are saved
        """
        self.recorder = recorder
        self.save_callback = save_callback
        
        # Create frame
        self.frame = ttk.Frame(parent, padding="10")
        
        # Create settings widgets
        self._create_widgets()
        
        # Load current settings
        self._load_settings()
    
    def _create_widgets(self):
        """Create the settings panel widgets."""
        # Device settings frame
        device_frame = ttk.LabelFrame(self.frame, text="Audio Device")
        device_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Device selection
        ttk.Label(device_frame, text="Recording Device:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.device_var = tk.StringVar()
        self.device_combo = ttk.Combobox(device_frame, textvariable=self.device_var, state="readonly", width=40)
        self.device_combo.grid(row=0, column=1, sticky=tk.W, padx=5, pady=5)
        
        # Refresh devices button
        refresh_button = ttk.Button(device_frame, text="Refresh", command=self._refresh_devices)
        refresh_button.grid(row=0, column=2, padx=5, pady=5)
        
        # Audio settings frame
        audio_frame = ttk.LabelFrame(self.frame, text="Audio Settings")
        audio_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Format selection
        ttk.Label(audio_frame, text="Format:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.format_var = tk.StringVar()
        format_combo = ttk.Combobox(audio_frame, textvariable=self.format_var, state="readonly", width=10)
        format_combo["values"] = ["wav", "mp3"]
        format_combo.grid(row=0, column=1, sticky=tk.W, padx=5, pady=5)
        format_combo.bind("<<ComboboxSelected>>", self._on_format_change)
        Tooltip(format_combo, "Select audio format: WAV (uncompressed) or MP3 (compressed)")
        
        # Quality selection
        ttk.Label(audio_frame, text="MP3 Quality:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.quality_var = tk.StringVar()
        self.quality_combo = ttk.Combobox(audio_frame, textvariable=self.quality_var, state="readonly", width=10)
        self.quality_combo["values"] = ["High", "Medium", "Low"]
        self.quality_combo.grid(row=1, column=1, sticky=tk.W, padx=5, pady=5)
        Tooltip(self.quality_combo, "MP3 quality settings: High (320kbps), Medium (192kbps), Low (128kbps)")
        
        # Mono checkbox
        self.mono_var = tk.BooleanVar()
        mono_check = ttk.Checkbutton(audio_frame, text="Mono Recording", variable=self.mono_var)
        mono_check.grid(row=2, column=0, columnspan=2, sticky=tk.W, padx=5, pady=5)
        
        # Monitor level
        ttk.Label(audio_frame, text="Monitor Level:").grid(row=3, column=0, sticky=tk.W, padx=5, pady=5)
        self.monitor_var = tk.DoubleVar()
        monitor_scale = ttk.Scale(audio_frame, from_=0.0, to=1.0, variable=self.monitor_var, orient=tk.HORIZONTAL)
        monitor_scale.grid(row=3, column=1, sticky=tk.W+tk.E, padx=5, pady=5)
        
        # Storage settings frame
        storage_frame = ttk.LabelFrame(self.frame, text="Storage Settings")
        storage_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Recordings directory
        ttk.Label(storage_frame, text="Recordings Directory:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.dir_var = tk.StringVar()
        dir_entry = ttk.Entry(storage_frame, textvariable=self.dir_var, width=30)
        dir_entry.grid(row=0, column=1, sticky=tk.W+tk.E, padx=5, pady=5)
        
        # Browse button
        browse_button = ttk.Button(storage_frame, text="Browse", command=self._browse_directory)
        browse_button.grid(row=0, column=2, padx=5, pady=5)
        
        # Retention period
        ttk.Label(storage_frame, text="Retention Period (days):").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.retention_var = tk.IntVar()
        retention_spin = ttk.Spinbox(storage_frame, from_=1, to=365, textvariable=self.retention_var, width=5)
        retention_spin.grid(row=1, column=1, sticky=tk.W, padx=5, pady=5)
        
        # Recording block size
        ttk.Label(storage_frame, text="Recording Block (hours):").grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        self.block_var = tk.IntVar()
        block_spin = ttk.Spinbox(storage_frame, from_=1, to=24, textvariable=self.block_var, width=5)
        block_spin.grid(row=2, column=1, sticky=tk.W, padx=5, pady=5)
        
        # General settings frame
        general_frame = ttk.LabelFrame(self.frame, text="General Settings")
        general_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Run on startup
        self.startup_var = tk.BooleanVar()
        startup_check = ttk.Checkbutton(general_frame, text="Run on System Startup", variable=self.startup_var)
        startup_check.grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        
        # Minimize to tray
        self.tray_var = tk.BooleanVar()
        tray_check = ttk.Checkbutton(general_frame, text="Minimize to System Tray", variable=self.tray_var)
        tray_check.grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        
        # Save button
        save_button = ttk.Button(self.frame, text="Save Settings", command=self._save_settings)
        save_button.pack(pady=10)
    
    def _load_settings(self):
        """Load current settings into the UI."""
        # Load device list
        self._refresh_devices()
        
        # Set current device
        status = self.recorder.get_status()
        for i, device in enumerate(self.devices):
            if device["index"] == status["device_index"]:
                self.device_combo.current(i)
                break
        
        # Set audio settings
        self.format_var.set(status["format"])
        self.quality_var.set(status["quality"].capitalize())
        self.mono_var.set(status["mono"])
        self.monitor_var.set(status["monitor_level"])
        
        # Update quality dropdown state based on format
        if status["format"] == "mp3":
            self.quality_combo.config(state="readonly")
        else:
            self.quality_combo.config(state="disabled")
        
        # Set storage settings
        self.dir_var.set(status["recordings_dir"])
        self.retention_var.set(status["retention_days"])
        self.block_var.set(self.recorder.config["general"]["recording_hours"])
        
        # Set general settings
        self.startup_var.set(self.recorder.config["general"]["run_on_startup"])
        self.tray_var.set(self.recorder.config["general"]["minimize_to_tray"])
    
    def _refresh_devices(self):
        """Refresh the list of available devices."""
        # Get devices
        self.devices = self.recorder.list_devices()
        
        # Update combobox
        device_names = [f"{d['name']} (Index: {d['index']})" for d in self.devices]
        self.device_combo["values"] = device_names
        
        # Select first device if none selected
        if not self.device_combo.get():
            self.device_combo.current(0)
    
    def _browse_directory(self):
        """Open directory browser dialog."""
        current_dir = self.dir_var.get()
        if not os.path.exists(current_dir):
            current_dir = os.path.abspath(".")
        
        directory = filedialog.askdirectory(
            initialdir=current_dir,
            title="Select Recordings Directory"
        )
        
        if directory:
            self.dir_var.set(directory)
    
    def _save_settings(self):
        """Save settings and call the save callback."""
        try:
            # Validate settings
            if not self._validate_settings():
                return
            
            # Call save callback
            if self.save_callback:
                self.save_callback()
                
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save settings: {e}")
    
    def _on_format_change(self, event):
        """Handle format selection changes."""
        format_value = self.format_var.get()
        if format_value == "mp3":
            self.quality_combo.config(state="readonly")
        else:
            self.quality_combo.config(state="disabled")
    
    def _validate_settings(self):
        """
        Validate settings before saving.
        
        Returns:
            Boolean indicating if settings are valid
        """
        # Validate recordings directory
        recordings_dir = self.dir_var.get()
        if not recordings_dir:
            messagebox.showerror("Error", "Recordings directory cannot be empty")
            return False
        
        # Validate retention period
        try:
            retention_days = self.retention_var.get()
            if retention_days < 1:
                messagebox.showerror("Error", "Retention period must be at least 1 day")
                return False
        except:
            messagebox.showerror("Error", "Invalid retention period")
            return False
        
        # Validate recording block
        try:
            recording_hours = self.block_var.get()
            if recording_hours < 1 or recording_hours > 24:
                messagebox.showerror("Error", "Recording block must be between 1 and 24 hours")
                return False
        except:
            messagebox.showerror("Error", "Invalid recording block")
            return False
        
        return True
    
    def get_settings(self):
        """
        Get the current settings from the UI.
        
        Returns:
            Dictionary with settings
        """
        # Get selected device
        device_index = None
        selected_index = self.device_combo.current()
        if selected_index >= 0 and selected_index < len(self.devices):
            device_index = self.devices[selected_index]["index"]
        
        # Get quality setting
        quality = self.quality_var.get().lower()
        
        # Create settings dictionary
        settings = {
            "device_index": device_index,
            "format": self.format_var.get(),
            "quality": quality,
            "mono": self.mono_var.get(),
            "monitor_level": self.monitor_var.get(),
            "recordings_dir": self.dir_var.get(),
            "retention_days": self.retention_var.get(),
            "recording_hours": self.block_var.get(),
            "run_on_startup": self.startup_var.get(),
            "minimize_to_tray": self.tray_var.get()
        }
        
        return settings
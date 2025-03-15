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
        self.root.geometry("600x500")
        self.root.minsize(600, 500)
        
        # Set icon if available
        try:
            self.root.iconbitmap("recorder.ico")
        except:
            pass
        
        # Initialize recorder
        self.recorder = AudioRecorder()
        
        # Create GUI elements
        self.create_widgets()
        
        # Setup update timer
        self.update_status()
        
        # Handle window close
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        
        # Minimize to tray if configured
        if self.recorder.config["general"]["minimize_to_tray"]:
            self.setup_tray_icon()
    
    def create_widgets(self):
        """Create the GUI widgets."""
        # Main frame
        main_frame = ttk.Frame(self.root, padding="10")
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
        
        self.device_list = ttk.Combobox(device_frame, width=40)
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
        log_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Log text
        self.log_text = tk.Text(log_frame, height=5, wrap=tk.WORD)
        self.log_text.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(log_frame, command=self.log_text.yview)
        scrollbar.pack(fill=tk.Y, side=tk.RIGHT)
        self.log_text.config(yscrollcommand=scrollbar.set)
        
        # Populate device list
        self.refresh_devices()
    
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
        except Exception as e:
            logger.error(f"Error updating status: {e}")
        
        # Schedule next update
        self.root.after(1000, self.update_status)
    
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
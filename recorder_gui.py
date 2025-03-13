#!/usr/bin/env python3
"""
GUI wrapper for the Continuous Audio Recorder
"""

import os
import sys
import time
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import logging
from continuous_recorder import AudioRecorder, HAS_WASAPI
import pyaudio

class RecorderGUI:
    def __init__(self, root):
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
        # Main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Status frame
        status_frame = ttk.LabelFrame(main_frame, text="Status", padding="10")
        status_frame.pack(fill=tk.X, pady=5)
        
        # Status indicators
        self.status_text = tk.StringVar(value="Not Recording")
        status_label = ttk.Label(status_frame, textvariable=self.status_text, font=("Arial", 12, "bold"))
        status_label.pack(side=tk.LEFT, padx=5)
        
        self.status_indicator = tk.Canvas(status_frame, width=20, height=20, bg="red")
        self.status_indicator.pack(side=tk.LEFT, padx=5)
        self.status_indicator.create_oval(5, 5, 15, 15, fill="red", outline="")
        
        # Current file frame
        file_frame = ttk.LabelFrame(main_frame, text="Current Recording", padding="10")
        file_frame.pack(fill=tk.X, pady=5)
        
        self.current_file_text = tk.StringVar(value="No file")
        current_file_label = ttk.Label(file_frame, textvariable=self.current_file_text, wraplength=550)
        current_file_label.pack(fill=tk.X)
        
        self.next_file_text = tk.StringVar(value="")
        next_file_label = ttk.Label(file_frame, textvariable=self.next_file_text)
        next_file_label.pack(fill=tk.X)
        
        # Device selection frame
        device_frame = ttk.LabelFrame(main_frame, text="Audio Device", padding="10")
        device_frame.pack(fill=tk.X, pady=5)
        
        # Device selection
        self.device_var = tk.StringVar()
        self.device_dropdown = ttk.Combobox(device_frame, textvariable=self.device_var, state="readonly")
        self.device_dropdown.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        refresh_button = ttk.Button(device_frame, text="Refresh", command=self.refresh_devices)
        refresh_button.pack(side=tk.LEFT, padx=5)
        
        set_device_button = ttk.Button(device_frame, text="Set Device", command=self.set_device)
        set_device_button.pack(side=tk.LEFT, padx=5)
        
        # Audio settings
        settings_frame = ttk.LabelFrame(main_frame, text="Audio Settings", padding="10")
        settings_frame.pack(fill=tk.X, pady=5)
        
        # Quality selection
        quality_frame = ttk.Frame(settings_frame)
        quality_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Label(quality_frame, text="Quality:").pack(side="left")
        self.quality_var = tk.StringVar(value=self.recorder.config["audio"]["quality"])
        quality_combo = ttk.Combobox(quality_frame, textvariable=self.quality_var, values=["high", "medium", "low"], state="readonly")
        quality_combo.pack(side="left", padx=5)
        quality_combo.bind("<<ComboboxSelected>>", lambda e: self.set_audio_quality())
        
        # Mono/Stereo selection
        mono_frame = ttk.Frame(settings_frame)
        mono_frame.pack(fill=tk.X, padx=5, pady=5)
        self.mono_var = tk.BooleanVar(value=self.recorder.config["audio"]["mono"])
        mono_check = ttk.Checkbutton(mono_frame, text="Mono", variable=self.mono_var, command=self.set_mono_mode)
        mono_check.pack(side="left")
        
        # Monitor level
        monitor_frame = ttk.Frame(settings_frame)
        monitor_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Label(monitor_frame, text="Monitor Level:").pack(side="left")
        self.monitor_var = tk.DoubleVar(value=self.recorder.config["audio"]["monitor_level"])
        monitor_scale = ttk.Scale(monitor_frame, from_=0.0, to=1.0, variable=self.monitor_var, orient="horizontal")
        monitor_scale.pack(side="left", fill=tk.X, expand=True, padx=5)
        monitor_scale.bind("<ButtonRelease-1>", self.set_monitor_level)
        
        # Add monitor level display
        self.monitor_level_text = tk.StringVar(value=f"{self.monitor_var.get():.2f}")
        ttk.Label(monitor_frame, textvariable=self.monitor_level_text, width=5).pack(side="left")
        
        # Update monitor level text when slider moves
        def update_monitor_text(*args):
            self.monitor_level_text.set(f"{self.monitor_var.get():.2f}")
        self.monitor_var.trace_add("write", update_monitor_text)
        
        # Control buttons frame
        control_frame = ttk.Frame(main_frame, padding="10")
        control_frame.pack(fill=tk.X, pady=5)
        
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
        settings_frame.pack(fill=tk.X, pady=5)
        
        # Retention days
        ttk.Label(settings_frame, text="Retention (days):").grid(row=0, column=0, sticky=tk.W, padx=5, pady=2)
        self.retention_var = tk.IntVar(value=self.recorder.config["general"]["retention_days"])
        retention_spinbox = ttk.Spinbox(settings_frame, from_=1, to=365, textvariable=self.retention_var, width=5)
        retention_spinbox.grid(row=0, column=1, sticky=tk.W, padx=5, pady=2)
        
        # Recording hours
        ttk.Label(settings_frame, text="Recording duration (hours):").grid(row=1, column=0, sticky=tk.W, padx=5, pady=2)
        self.duration_var = tk.IntVar(value=self.recorder.config["general"]["recording_hours"])
        duration_spinbox = ttk.Spinbox(settings_frame, from_=1, to=24, textvariable=self.duration_var, width=5)
        duration_spinbox.grid(row=1, column=1, sticky=tk.W, padx=5, pady=2)
        
        # Format selection
        ttk.Label(settings_frame, text="Format:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=2)
        self.format_var = tk.StringVar(value=self.recorder.config["audio"]["format"])
        format_combo = ttk.Combobox(settings_frame, textvariable=self.format_var, values=["wav", "mp3"], state="readonly", width=5)
        format_combo.grid(row=2, column=1, sticky=tk.W, padx=5, pady=2)
        
        # Autostart
        self.autostart_var = tk.BooleanVar(value=self.recorder.config["general"]["run_on_startup"])
        autostart_check = ttk.Checkbutton(settings_frame, text="Run on startup", variable=self.autostart_var)
        autostart_check.grid(row=0, column=2, sticky=tk.W, padx=5, pady=2)
        
        # Minimize to tray
        self.minimize_var = tk.BooleanVar(value=self.recorder.config["general"]["minimize_to_tray"])
        minimize_check = ttk.Checkbutton(settings_frame, text="Minimize to tray", variable=self.minimize_var)
        minimize_check.grid(row=1, column=2, sticky=tk.W, padx=5, pady=2)
        
        # Save settings button
        save_button = ttk.Button(settings_frame, text="Save Settings", command=self.save_settings)
        save_button.grid(row=3, column=0, columnspan=3, pady=10)
        
        # Recordings directory frame
        dir_frame = ttk.LabelFrame(main_frame, text="Recordings Directory", padding="10")
        dir_frame.pack(fill=tk.X, pady=5)
        
        self.dir_var = tk.StringVar(value=os.path.abspath(self.recorder.config["paths"]["recordings_dir"]))
        dir_entry = ttk.Entry(dir_frame, textvariable=self.dir_var, state="readonly")
        dir_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        browse_button = ttk.Button(dir_frame, text="Browse", command=self.browse_directory)
        browse_button.pack(side=tk.LEFT, padx=5)
        
        open_button = ttk.Button(dir_frame, text="Open", command=self.open_directory)
        open_button.pack(side=tk.LEFT, padx=5)
        
        # Log frame
        log_frame = ttk.LabelFrame(main_frame, text="Log", padding="10")
        log_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        self.log_text = tk.Text(log_frame, height=10, wrap=tk.WORD, state=tk.DISABLED)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        log_scrollbar = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.log_text.yview)
        log_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.config(yscrollcommand=log_scrollbar.set)
        
        # Populate devices
        self.refresh_devices()
    
    def refresh_devices(self):
        """Refresh the list of available audio devices."""
        # Get devices
        p = self.recorder.audio or self.recorder._get_pyaudio_instance()
        devices = []
        recommended_devices = []
        
        try:
            # Get default WASAPI device if available
            if HAS_WASAPI:
                try:
                    default_wasapi = p.get_default_wasapi_device()
                    self.log(f"Default WASAPI device: {default_wasapi['name']} (index {default_wasapi['index']})")
                except Exception as e:
                    self.log(f"Error getting default WASAPI device: {e}")
            
            # Get loopback devices
            if HAS_WASAPI:
                try:
                    for device in p.get_loopback_device_info_generator():
                        devices.append(f"{device['index']}: {device['name']} [LOOPBACK]")
                        recommended_devices.append(device['index'])
                        self.log(f"Found loopback device: {device['name']}")
                except Exception as e:
                    self.log(f"Error getting loopback devices: {e}")
            
            # List all devices
            try:
                for device in p.get_device_info_generator():
                    host_api = p.get_host_api_info_by_index(device.get('hostApi', 0))
                    host_api_name = host_api.get('name', 'Unknown')
                    
                    is_loopback = device.get('isLoopbackDevice', False)
                    is_wasapi = device.get('hostApi', 0) == p.get_host_api_info_by_type(pyaudio.paWASAPI)['index']
                    has_input = device.get('maxInputChannels', 0) > 0
                    
                    # Only show output devices
                    if device.get('maxOutputChannels', 0) > 0:
                        # Build status indicators
                        status = []
                        if is_loopback:
                            status.append("LOOPBACK")
                        if is_wasapi:
                            status.append("WASAPI")
                        if has_input:
                            status.append("INPUT")
                        
                        status_str = f" [{', '.join(status)}]" if status else ""
                        
                        # Determine if this is a recommended device for recording
                        is_recommended = is_loopback and has_input
                        if is_recommended:
                            recommended_devices.append(device['index'])
                        
                        # Add a star to recommended devices
                        rec_str = " ⭐" if is_recommended else ""
                        
                        devices.append(f"{device['index']}: {device['name']}{status_str}{rec_str}")
            except Exception as e:
                self.log(f"Error listing devices: {e}")
            
            # Update dropdown
            self.device_dropdown['values'] = devices
            
            # Select current device if set
            if self.recorder.device_index is not None:
                for i, device in enumerate(devices):
                    if device.startswith(f"{self.recorder.device_index}:"):
                        self.device_dropdown.current(i)
                        break
            
            # Log recommendations
            if recommended_devices:
                self.log("Recommended devices for recording:")
                for idx in recommended_devices:
                    device = p.get_device_info_by_index(idx)
                    self.log(f"  Device {idx}: {device['name']}")
            else:
                self.log("No recommended devices found. Try selecting a WASAPI device.")
                
        except Exception as e:
            self.log(f"Error refreshing devices: {e}")
        finally:
            if not self.recorder.audio:
                p.terminate()
    
    def set_device(self):
        """Set the selected device as the recording device."""
        if not self.device_var.get():
            messagebox.showwarning("No Device Selected", "Please select a device first.")
            return
        
        try:
            device_index = int(self.device_var.get().split(":")[0])
            if self.recorder.set_device(device_index):
                self.log(f"Device set to: {self.device_var.get()}")
                messagebox.showinfo("Device Set", f"Recording device set to {self.device_var.get()}")
            else:
                messagebox.showerror("Error", "Failed to set device.")
        except Exception as e:
            self.log(f"Error setting device: {e}")
            messagebox.showerror("Error", f"Error setting device: {e}")
    
    def set_audio_quality(self):
        """Set the audio quality level."""
        quality = self.quality_var.get()
        if self.recorder.set_audio_quality(quality):
            self.log(f"Audio quality set to {quality}")
        else:
            messagebox.showerror("Error", f"Failed to set audio quality to {quality}")
    
    def set_mono_mode(self):
        """Set mono/stereo recording mode."""
        mono = self.mono_var.get()
        if self.recorder.set_mono(mono):
            self.log(f"Recording mode set to {'mono' if mono else 'stereo'}")
        else:
            messagebox.showerror("Error", "Failed to set recording mode")
    
    def set_monitor_level(self, *args):
        """Set the monitor level."""
        level = self.monitor_var.get()
        if self.recorder.set_monitor_level(level):
            self.log(f"Monitor level set to {level:.2f}")
        else:
            messagebox.showerror("Error", f"Failed to set monitor level to {level:.2f}")
    
    def start_recording(self):
        """Start the recording process."""
        # Apply current settings before starting
        self.set_audio_quality()
        self.set_mono_mode()
        self.set_monitor_level()
        
        if self.recorder.start_recording():
            self.log("Recording started")
            self.status_text.set("Recording")
            self.status_indicator.itemconfig(1, fill="green")
            self.start_button.config(state=tk.DISABLED)
            self.stop_button.config(state=tk.NORMAL)
            self.pause_button.config(state=tk.NORMAL, text="Pause")
            self.resume_button.config(state=tk.DISABLED)
            self.device_dropdown.config(state="disabled")
        else:
            messagebox.showerror("Error", "Failed to start recording.")
    
    def stop_recording(self):
        """Stop the recording process."""
        if self.recorder.stop_recording():
            self.log("Recording stopped")
            self.status_text.set("Not Recording")
            self.status_indicator.itemconfig(1, fill="red")
            self.start_button.config(state=tk.NORMAL)
            self.stop_button.config(state=tk.DISABLED)
            self.pause_button.config(state=tk.DISABLED, text="Pause")
            self.resume_button.config(state=tk.DISABLED)
            self.device_dropdown.config(state="readonly")
            self.current_file_text.set("No file")
            self.next_file_text.set("")
        else:
            messagebox.showerror("Error", "Failed to stop recording.")
    
    def pause_recording(self):
        """Pause or resume the recording."""
        if self.recorder.paused:
            if self.recorder.resume_recording():
                self.log("Recording resumed")
                self.status_text.set("Recording")
                self.status_indicator.itemconfig(1, fill="green")
                self.pause_button.config(text="Pause")
                self.resume_button.config(state=tk.DISABLED)
            else:
                messagebox.showerror("Error", "Failed to resume recording.")
        else:
            if self.recorder.pause_recording():
                self.log("Recording paused")
                self.status_text.set("Paused")
                self.status_indicator.itemconfig(1, fill="yellow")
                self.pause_button.config(text="Resume")
                self.resume_button.config(state=tk.NORMAL)
            else:
                messagebox.showerror("Error", "Failed to pause recording.")
    
    def resume_recording(self):
        """Resume the recording."""
        if self.recorder.resume_recording():
            self.log("Recording resumed")
            self.status_text.set("Recording")
            self.status_indicator.itemconfig(1, fill="green")
            self.resume_button.config(state=tk.DISABLED)
        else:
            messagebox.showerror("Error", "Failed to resume recording.")
    
    def save_settings(self):
        """Save the current settings."""
        try:
            # Update config
            self.recorder.config["general"]["retention_days"] = self.retention_var.get()
            self.recorder.config["general"]["recording_hours"] = self.duration_var.get()
            self.recorder.config["audio"]["format"] = self.format_var.get()
            self.recorder.config["general"]["run_on_startup"] = self.autostart_var.get()
            self.recorder.config["general"]["minimize_to_tray"] = self.minimize_var.get()
            self.recorder.config["paths"]["recordings_dir"] = self.dir_var.get()
            
            # Update audio settings
            self.recorder.config["audio"]["quality"] = self.quality_var.get()
            self.recorder.config["audio"]["mono"] = self.mono_var.get()
            self.recorder.config["audio"]["monitor_level"] = self.monitor_var.get()
            
            # Save to file
            self.recorder._save_config()
            
            # Update autostart if needed
            self.recorder.setup_autostart(self.autostart_var.get())
            
            self.log("Settings saved")
            messagebox.showinfo("Settings Saved", "Settings have been saved successfully.")
        except Exception as e:
            self.log(f"Error saving settings: {e}")
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
        """Open the recordings directory in file explorer."""
        directory = self.dir_var.get()
        if os.path.exists(directory):
            if sys.platform == 'win32':
                os.startfile(directory)
            elif sys.platform == 'darwin':  # macOS
                os.system(f'open "{directory}"')
            else:  # Linux
                os.system(f'xdg-open "{directory}"')
        else:
            messagebox.showerror("Error", "Directory does not exist.")
    
    def update_status(self):
        """Update the status display."""
        try:
            if self.recorder.recording:
                status = self.recorder.get_status()
                
                if status["current_file"]:
                    self.current_file_text.set(status["current_file"])
                
                if status["next_file_time"]:
                    self.next_file_text.set(f"Next file at: {status['next_file_time']}")
                
                # Update queue size in log occasionally
                if hasattr(self, 'last_queue_size') and self.last_queue_size != status["queue_size"]:
                    if status["queue_size"] > 100 or status["queue_size"] == 0:
                        self.log(f"Queue size: {status['queue_size']} chunks")
                self.last_queue_size = status["queue_size"]
        except Exception as e:
            self.log(f"Error updating status: {e}")
        
        # Schedule next update
        self.root.after(1000, self.update_status)
    
    def log(self, message):
        """Add a message to the log display."""
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, f"{time.strftime('%H:%M:%S')} - {message}\n")
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)
    
    def setup_tray_icon(self):
        """Setup system tray icon if available."""
        try:
            import pystray
            from PIL import Image, ImageDraw
            
            # Create a simple icon
            icon_image = Image.new('RGB', (64, 64), color=(0, 0, 0))
            d = ImageDraw.Draw(icon_image)
            d.ellipse((10, 10, 54, 54), fill=(255, 0, 0))
            
            # Define menu
            def on_quit(icon, item):
                icon.stop()
                self.on_close()
            
            def on_show(icon, item):
                icon.stop()
                self.root.after(0, self.root.deiconify)
            
            menu = pystray.Menu(
                pystray.MenuItem("Show", on_show),
                pystray.MenuItem("Quit", on_quit)
            )
            
            # Create icon
            self.icon = pystray.Icon("recorder", icon_image, "Continuous Recorder", menu)
            
            # Override minimize
            def on_minimize():
                self.root.withdraw()
                self.icon.run()
            
            self.root.protocol("WM_DELETE_WINDOW", on_minimize)
            
            self.log("Tray icon support enabled")
        except ImportError:
            self.log("Tray icon support not available (pystray or PIL missing)")
    
    def on_close(self):
        """Handle window close event."""
        if self.recorder.recording:
            if messagebox.askyesno("Confirm Exit", "Recording is in progress. Stop recording and exit?"):
                self.recorder.stop_recording()
                self.root.destroy()
        else:
            self.root.destroy()


def main():
    root = tk.Tk()
    app = RecorderGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main() 
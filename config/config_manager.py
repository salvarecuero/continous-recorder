"""
Configuration management for the Continuous Audio Recorder.
"""

import os
import configparser
from .default_config import DEFAULT_CONFIG

class ConfigManager:
    """Handles loading, saving, and accessing configuration settings."""
    
    def __init__(self, config_path="config.ini"):
        """Initialize the configuration manager with a path to the config file."""
        self.config_path = config_path
        self.config = self._load_config()
    
    def _load_config(self):
        """Load configuration from file or use defaults."""
        config = DEFAULT_CONFIG.copy()
        
        if os.path.exists(self.config_path):
            parser = configparser.ConfigParser()
            parser.read(self.config_path)
            
            # Update config with values from file
            for section in parser.sections():
                if section in config:
                    for key, value in parser.items(section):
                        if key in config[section]:
                            # Convert string values to appropriate types
                            if isinstance(config[section][key], bool):
                                config[section][key] = parser.getboolean(section, key)
                            elif isinstance(config[section][key], int):
                                config[section][key] = parser.getint(section, key)
                            elif isinstance(config[section][key], float):
                                config[section][key] = parser.getfloat(section, key)
                            else:
                                config[section][key] = parser[section][key]
        
        return config
    
    def save_config(self):
        """Save current configuration to file."""
        parser = configparser.ConfigParser()
        
        # Convert dictionary to ConfigParser format
        for section, options in self.config.items():
            parser[section] = {}
            for key, value in options.items():
                parser[section][key] = str(value)
        
        # Write to file
        with open(self.config_path, 'w') as f:
            parser.write(f)
    
    def get(self, section, key, default=None):
        """Get a configuration value."""
        try:
            return self.config[section][key]
        except KeyError:
            return default
    
    def set(self, section, key, value):
        """Set a configuration value."""
        if section in self.config and key in self.config[section]:
            self.config[section][key] = value
            return True
        return False
    
    def get_section(self, section):
        """Get an entire configuration section."""
        return self.config.get(section, {}) 
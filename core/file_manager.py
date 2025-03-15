"""
File management for the Continuous Audio Recorder.
"""

import os
import time
import datetime
import logging
import subprocess
import shutil

logger = logging.getLogger("ContinuousRecorder")

class FileManager:
    """Manages recording files, including creation, conversion, and cleanup."""
    
    def __init__(self, config):
        """
        Initialize the file manager.
        
        Args:
            config: Configuration manager instance
        """
        self.config = config
        self.recordings_dir = self.config.get("paths", "recordings_dir")
        self.ffmpeg_path = self.config.get("paths", "ffmpeg_path")
        
        # Create recordings directory if it doesn't exist
        os.makedirs(self.recordings_dir, exist_ok=True)
    
    def create_file_path(self, block_start_time, actual_start_time=None):
        """
        Create a file path for a new recording.
        
        Args:
            block_start_time: Start time of the recording block
            actual_start_time: Actual start time of the recording (optional)
            
        Returns:
            Tuple of (directory path, file path)
        """
        # Format timestamps
        date_str = block_start_time.strftime("%Y-%m-%d")
        time_str = block_start_time.strftime("%H-%M-%S")
        
        # Create date directory
        date_dir = os.path.join(self.recordings_dir, date_str)
        os.makedirs(date_dir, exist_ok=True)
        
        # Create file name
        if actual_start_time:
            # Calculate offset in seconds
            offset = int((actual_start_time - block_start_time).total_seconds())
            file_name = f"{time_str}_offset_{offset}.wav"
        else:
            file_name = f"{time_str}.wav"
        
        # Create full file path
        file_path = os.path.join(date_dir, file_name)
        
        return date_dir, file_path
    
    def convert_to_mp3(self, wav_file):
        """
        Convert a WAV file to MP3 format.
        
        Args:
            wav_file: Path to the WAV file
            
        Returns:
            Path to the MP3 file or None if conversion failed
        """
        # Check if ffmpeg is available
        if not shutil.which(self.ffmpeg_path):
            logger.error(f"FFmpeg not found at {self.ffmpeg_path}")
            return None
        
        # Create MP3 file path
        mp3_file = os.path.splitext(wav_file)[0] + ".mp3"
        
        # Get audio quality setting
        quality = self.config.get("audio", "quality")
        if quality == "high":
            bitrate = "192k"
        elif quality == "medium":
            bitrate = "128k"
        else:  # low
            bitrate = "96k"
        
        try:
            # Run ffmpeg command
            cmd = [
                self.ffmpeg_path,
                "-i", wav_file,
                "-codec:a", "libmp3lame",
                "-b:a", bitrate,
                "-y",  # Overwrite output file if it exists
                mp3_file
            ]
            
            # Execute command
            subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            # Delete WAV file if conversion successful
            if os.path.exists(mp3_file):
                os.remove(wav_file)
                logger.debug(f"Converted {wav_file} to {mp3_file}")
                return mp3_file
            else:
                logger.error(f"MP3 file not created: {mp3_file}")
                return None
                
        except Exception as e:
            logger.error(f"Error converting {wav_file} to MP3: {e}")
            return None
    
    def cleanup_old_recordings(self):
        """
        Delete recordings older than the retention period.
        
        Returns:
            Number of files deleted
        """
        retention_days = self.config.get("general", "retention_days")
        if retention_days <= 0:
            logger.info("Retention days set to 0 or negative, skipping cleanup")
            return 0
        
        # Calculate cutoff date
        cutoff_time = time.time() - (retention_days * 24 * 60 * 60)
        deleted_count = 0
        
        try:
            # Iterate through date directories
            for date_dir in os.listdir(self.recordings_dir):
                date_path = os.path.join(self.recordings_dir, date_dir)
                
                # Skip if not a directory or doesn't match date format
                if not os.path.isdir(date_path) or not self._is_date_dir(date_dir):
                    continue
                
                # Check if directory is older than retention period
                dir_time = os.path.getmtime(date_path)
                if dir_time < cutoff_time:
                    # Delete entire directory
                    shutil.rmtree(date_path)
                    logger.info(f"Deleted old recording directory: {date_path}")
                    deleted_count += 1
                else:
                    # Check individual files
                    for file in os.listdir(date_path):
                        file_path = os.path.join(date_path, file)
                        if os.path.isfile(file_path):
                            file_time = os.path.getmtime(file_path)
                            if file_time < cutoff_time:
                                os.remove(file_path)
                                logger.debug(f"Deleted old recording file: {file_path}")
                                deleted_count += 1
            
            return deleted_count
            
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
            return deleted_count
    
    def _is_date_dir(self, dir_name):
        """
        Check if a directory name matches the date format (YYYY-MM-DD).
        
        Args:
            dir_name: Directory name to check
            
        Returns:
            Boolean indicating if the directory name matches the date format
        """
        try:
            datetime.datetime.strptime(dir_name, "%Y-%m-%d")
            return True
        except ValueError:
            return False 
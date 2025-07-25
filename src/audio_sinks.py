"""
Audio sink implementations for Discord voice recording.
Supports PCM and WAV format recording with proper file management.
"""
import os
import discord
from datetime import datetime
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)

class PCMRecordingSink(discord.sinks.Sink):
    """
    AudioSink for recording in PCM format.
    Saves individual user audio streams as separate PCM files.
    """
    
    def __init__(self, output_dir: str = "recorded_audio"):
        super().__init__()
        self.output_dir = output_dir
        self.audio_data: Dict[int, discord.sinks.core.AudioData] = {}
        self.encoding = "pcm"
        
        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
        logger.info(f"PCM recording sink initialized with output directory: {output_dir}")
    
    def wants_opus(self) -> bool:
        """Return False to receive decoded PCM audio instead of Opus packets."""
        return False
    
    def write(self, data, user):
        """
        Write PCM audio data for a specific user.
        This is called for every audio frame received.
        """
        user_id = user.id if hasattr(user, 'id') else user
        
        if user_id not in self.audio_data:
            # Initialize audio data for new user
            self.audio_data[user_id] = discord.sinks.core.AudioData()
            logger.info(f"Started recording audio for user {user_id}")
        
        # Write PCM data to the user's audio buffer
        self.audio_data[user_id].write(data)
    
    def cleanup(self):
        """
        Clean up and save all recorded audio to files.
        Called when recording stops.
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        saved_files = []
        
        for user_id, audio in self.audio_data.items():
            if audio.file.tell() > 0:  # Only save if there's actual audio data
                filename = f"user_{user_id}_{timestamp}.{self.encoding}"
                filepath = os.path.join(self.output_dir, filename)
                
                # Reset file pointer and save
                audio.file.seek(0)
                with open(filepath, 'wb') as f:
                    f.write(audio.file.read())
                
                saved_files.append(filepath)
                logger.info(f"Saved PCM audio for user {user_id} to {filepath}")
        
        logger.info(f"Recording cleanup complete. Saved {len(saved_files)} audio files.")
        return saved_files


class WAVRecordingSink(discord.sinks.WaveSink):
    """
    AudioSink for recording in WAV format.
    Extends Pycord's built-in WaveSink with custom output directory handling.
    """
    
    def __init__(self, output_dir: str = "recorded_audio"):
        super().__init__()
        self.output_dir = output_dir
        
        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
        logger.info(f"WAV recording sink initialized with output directory: {output_dir}")
    
    def get_file_path(self, user_id: int) -> str:
        """Generate file path for a user's audio recording."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"user_{user_id}_{timestamp}.{self.encoding}"
        return os.path.join(self.output_dir, filename)


class MultiFormatSink:
    """
    Utility class to manage multiple audio sinks simultaneously.
    Allows recording in multiple formats at once.
    """
    
    def __init__(self, output_dir: str = "recorded_audio"):
        self.pcm_sink = PCMRecordingSink(output_dir)
        self.wav_sink = WAVRecordingSink(output_dir)
        self.active_sinks = []
    
    def get_pcm_sink(self) -> PCMRecordingSink:
        """Get PCM recording sink."""
        return self.pcm_sink
    
    def get_wav_sink(self) -> WAVRecordingSink:
        """Get WAV recording sink.""" 
        return self.wav_sink
    
    def cleanup_all(self):
        """Cleanup all active sinks."""
        results = {}
        if self.pcm_sink:
            results['pcm'] = self.pcm_sink.cleanup()
        if self.wav_sink:
            results['wav'] = self.wav_sink.cleanup()
        return results
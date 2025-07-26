"""
Streaming Audio Sink for continuous Discord voice processing.
Based on brodan's STTAudioSink approach with energy-based VAD.
"""

import asyncio
import logging
import io
import time
from typing import Dict, Any, Optional
import discord
import numpy as np
from collections import deque

logger = logging.getLogger(__name__)

class StreamingAudioSink(discord.sinks.Sink):
    """
    Continuous audio processing sink with energy-based VAD.
    Streams audio in buffered segments to Whisper for real-time transcription.
    """
    
    def __init__(self, whisper_client, config: Optional[Dict[str, Any]] = None):
        """
        Initialize streaming audio sink.
        
        Args:
            whisper_client: WhisperClient instance for transcription
            config: Audio processing configuration
        """
        super().__init__()
        self.whisper_client = whisper_client
        
        # Default configuration based on brodan's approach
        self.config = {
            'energy_threshold': 50,          # Energy-based VAD threshold
            'buffer_duration': 3.0,          # Seconds of audio per segment
            'sample_rate': 48000,            # Discord's native sample rate
            'silence_timeout': 1.0,          # Seconds of silence before processing
            'max_buffer_size': 8.0,          # Maximum buffer size in seconds
            'min_speech_duration': 0.5,      # Minimum speech duration to process
        }
        
        if config:
            self.config.update(config)
        
        # Audio buffers for each user
        self.user_buffers: Dict[int, deque] = {}
        self.user_last_activity: Dict[int, float] = {}
        self.processing_tasks: Dict[int, asyncio.Task] = {}
        
        logger.info(f"StreamingAudioSink initialized with config: {self.config}")
    
    def format_audio(self, audio_data) -> bytes:
        """Convert audio data to bytes format expected by Whisper."""
        return audio_data.raw_data
    
    def calculate_energy(self, audio_data: bytes) -> float:
        """
        Calculate audio energy for VAD.
        Simple energy-based approach from brodan.
        """
        try:
            # Convert bytes to numpy array for energy calculation
            audio_array = np.frombuffer(audio_data, dtype=np.int16)
            if len(audio_array) == 0:
                return 0.0
            
            # Calculate RMS energy
            energy = np.sqrt(np.mean(audio_array.astype(np.float32) ** 2))
            return float(energy)
        
        except Exception as e:
            logger.debug(f"Energy calculation error: {e}")
            return 0.0
    
    def has_speech(self, audio_data: bytes) -> bool:
        """
        Simple energy-based VAD.
        Returns True if audio contains speech above threshold.
        """
        energy = self.calculate_energy(audio_data)
        return energy > self.config['energy_threshold']
    
    async def process_audio_segment(self, user_id: int, audio_segment: bytes):
        """
        Process a complete audio segment through Whisper.
        """
        try:
            # Check minimum duration
            duration = len(audio_segment) / (self.config['sample_rate'] * 2)  # 16-bit = 2 bytes per sample
            if duration < self.config['min_speech_duration']:
                logger.debug(f"Audio segment too short for user {user_id}: {duration:.2f}s")
                return
            
            logger.debug(f"Processing {duration:.2f}s audio segment for user {user_id}")
            
            # Send to Whisper for transcription
            result = await self.whisper_client.transcribe_bytes(
                audio_segment,
                filename=f"stream_user_{user_id}.wav"
            )
            
            if result and result.get('text'):
                transcribed_text = result['text'].strip()
                if transcribed_text:
                    # Send transcription to Discord channel
                    await self.send_transcription(user_id, transcribed_text, duration)
                    logger.info(f"Transcribed for user {user_id}: {transcribed_text}")
            
        except Exception as e:
            logger.error(f"Audio processing error for user {user_id}: {e}")
    
    async def send_transcription(self, user_id: int, text: str, duration: float):
        """
        Send transcription result to Discord channel.
        Override this method to customize transcription delivery.
        """
        # This will be called by the bot to send transcriptions
        # The bot should override this method or handle transcriptions via callback
        logger.info(f"Transcription ready for user {user_id} ({duration:.1f}s): {text}")
    
    async def manage_user_buffer(self, user_id: int):
        """
        Manage audio buffer for a specific user.
        Process segments when buffer is full or after silence timeout.
        """
        while user_id in self.user_buffers:
            try:
                current_time = time.time()
                buffer = self.user_buffers[user_id]
                last_activity = self.user_last_activity.get(user_id, current_time)
                
                # Check if we should process the current buffer
                should_process = False
                
                if len(buffer) > 0:
                    # Calculate current buffer duration
                    total_samples = sum(len(chunk) for chunk in buffer) // 2  # 16-bit = 2 bytes per sample
                    buffer_duration = total_samples / self.config['sample_rate']
                    
                    # Process if buffer is full or silence timeout reached
                    if (buffer_duration >= self.config['buffer_duration'] or
                        (current_time - last_activity) >= self.config['silence_timeout']):
                        should_process = True
                
                if should_process:
                    # Combine buffer chunks into single audio segment
                    audio_segment = b''.join(buffer)
                    buffer.clear()
                    
                    # Process the audio segment
                    if len(audio_segment) > 0:
                        await self.process_audio_segment(user_id, audio_segment)
                
                # Sleep briefly to prevent excessive CPU usage
                await asyncio.sleep(0.1)
                
            except Exception as e:
                logger.error(f"Buffer management error for user {user_id}: {e}")
                await asyncio.sleep(1)  # Longer sleep on error
    
    def write(self, data, user):
        """
        Called by Discord for each audio packet.
        Implements continuous streaming with buffered processing.
        """
        user_id = user.id
        
        # Initialize user buffer if needed
        if user_id not in self.user_buffers:
            self.user_buffers[user_id] = deque()
            self.user_last_activity[user_id] = time.time()
            
            # Start buffer management task for this user
            task = asyncio.create_task(self.manage_user_buffer(user_id))
            self.processing_tasks[user_id] = task
            
            logger.info(f"Started streaming for user {user_id} ({user.display_name})")
        
        # Format audio data
        audio_bytes = self.format_audio(data)
        
        # Apply energy-based VAD
        if self.has_speech(audio_bytes):
            # Add to buffer and update activity time
            self.user_buffers[user_id].append(audio_bytes)
            self.user_last_activity[user_id] = time.time()
            
            # Prevent buffer from growing too large
            buffer = self.user_buffers[user_id]
            while len(buffer) > 0:
                total_samples = sum(len(chunk) for chunk in buffer) // 2
                buffer_duration = total_samples / self.config['sample_rate']
                
                if buffer_duration <= self.config['max_buffer_size']:
                    break
                
                # Remove oldest chunk
                buffer.popleft()
                logger.debug(f"Trimmed buffer for user {user_id}")
    
    def cleanup(self):
        """Clean up resources when sink is stopped."""
        logger.info("Cleaning up StreamingAudioSink")
        
        # Cancel all processing tasks
        for user_id, task in self.processing_tasks.items():
            if not task.done():
                task.cancel()
                logger.debug(f"Cancelled processing task for user {user_id}")
        
        # Clear buffers
        self.user_buffers.clear()
        self.user_last_activity.clear()
        self.processing_tasks.clear()
        
        logger.info("StreamingAudioSink cleanup complete")
    
    @property
    def wants_opus(self) -> bool:
        """We want decoded PCM data, not Opus packets."""
        return False
    
    def get_status(self) -> Dict[str, Any]:
        """Get current streaming status for monitoring."""
        current_time = time.time()
        
        status = {
            'active_users': len(self.user_buffers),
            'config': self.config,
            'users': {}
        }
        
        for user_id, buffer in self.user_buffers.items():
            total_samples = sum(len(chunk) for chunk in buffer) // 2
            buffer_duration = total_samples / self.config['sample_rate']
            last_activity = self.user_last_activity.get(user_id, 0)
            
            status['users'][user_id] = {
                'buffer_duration': round(buffer_duration, 2),
                'last_activity_ago': round(current_time - last_activity, 2),
                'chunks_in_buffer': len(buffer)
            }
        
        return status
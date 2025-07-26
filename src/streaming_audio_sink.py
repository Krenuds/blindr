"""
Streaming Audio Sink for continuous Discord voice processing.
Based on brodan's STTAudioSink approach with energy-based VAD.
"""

import asyncio
import logging
import io
import time
import struct
import wave
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
    
    def __init__(self, whisper_client, bot_event_loop, config: Optional[Dict[str, Any]] = None):
        """
        Initialize streaming audio sink.
        
        Args:
            whisper_client: WhisperClient instance for transcription
            bot_event_loop: The bot's main event loop for cross-thread communication
            config: Audio processing configuration
        """
        super().__init__()
        self.whisper_client = whisper_client
        self.bot_event_loop = bot_event_loop
        
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
        self.user_speech_start: Dict[int, float] = {}
        self.processing_locks: Dict[int, bool] = {}
        
        logger.info(f"StreamingAudioSink initialized with config: {self.config}")
    
    def _stereo_to_mono(self, stereo_data: bytes) -> bytes:
        """Convert stereo PCM to mono by mixing both channels (from brodan)"""
        try:
            if len(stereo_data) < 4:  # Need at least 4 bytes for one stereo sample
                return stereo_data
            
            # Convert stereo to mono by averaging left and right channels
            mono_samples = []
            for i in range(0, len(stereo_data), 4):  # 4 bytes = 1 stereo frame (16-bit L + 16-bit R)
                if i + 3 < len(stereo_data):
                    # Extract left and right samples
                    left_sample = struct.unpack('<h', stereo_data[i:i+2])[0]
                    right_sample = struct.unpack('<h', stereo_data[i+2:i+4])[0]
                    
                    # Mix by averaging (prevent overflow)
                    mixed_sample = (left_sample + right_sample) // 2
                    mono_samples.append(mixed_sample)
            
            if not mono_samples:
                return b''
            
            return struct.pack(f'<{len(mono_samples)}h', *mono_samples)
            
        except Exception as e:
            logger.debug(f"Stereo to mono conversion error: {e}")
            # Fallback: return original data truncated to valid length
            return stereo_data[:len(stereo_data) - (len(stereo_data) % 4)]
    
    def format_audio(self, audio_data) -> bytes:
        """Convert audio data to bytes format expected by Whisper."""
        # Handle both AudioData objects and raw bytes
        if hasattr(audio_data, 'raw_data'):
            pcm_data = audio_data.raw_data
        else:
            pcm_data = audio_data
        
        # Convert stereo to mono (Discord sends stereo, Whisper expects mono)
        mono_data = self._stereo_to_mono(pcm_data)
        return mono_data
    
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
        has_speech = energy > self.config['energy_threshold']
        if has_speech:
            logger.debug(f"Speech detected with energy {energy:.2f} (threshold: {self.config['energy_threshold']})")
        return has_speech
    
    def pcm_to_wav(self, pcm_data: bytes, sample_rate: int = 48000) -> bytes:
        """
        Convert raw PCM data to WAV format with proper headers.
        Resamples to 16kHz if needed for Whisper compatibility.
        
        Args:
            pcm_data: Raw PCM audio data (16-bit mono)
            sample_rate: Sample rate (default: 48000 Hz)
            
        Returns:
            WAV file data as bytes at 16kHz
        """
        # Convert bytes to numpy array
        audio_array = np.frombuffer(pcm_data, dtype=np.int16)
        
        # Resample to 16kHz if needed (Whisper standard)
        if sample_rate != 16000:
            # Simple downsampling by taking every nth sample
            resample_factor = sample_rate // 16000
            audio_array = audio_array[::resample_factor]
            sample_rate = 16000
        
        wav_buffer = io.BytesIO()
        
        with wave.open(wav_buffer, 'wb') as wav_file:
            wav_file.setnchannels(1)  # Mono
            wav_file.setsampwidth(2)  # 16-bit
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(audio_array.tobytes())
        
        wav_buffer.seek(0)
        return wav_buffer.read()
    
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
            
            # Convert PCM to WAV format
            wav_data = self.pcm_to_wav(audio_segment, self.config['sample_rate'])
            
            # Send to Whisper for transcription
            logger.info(f"Sending {duration:.2f}s audio to Whisper for user {user_id}")
            result = await self.whisper_client.transcribe_bytes(
                wav_data,
                filename=f"stream_user_{user_id}.wav"
            )
            
            if result and result.get('text'):
                transcribed_text = result['text'].strip()
                if transcribed_text:
                    # Send transcription to Discord channel
                    await self.send_transcription(user_id, transcribed_text, duration)
                    logger.info(f"✅ Transcribed for user {user_id}: {transcribed_text}")
                else:
                    logger.debug(f"Empty transcription result for user {user_id}")
            else:
                logger.warning(f"No text in Whisper result for user {user_id}: {result}")
            
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
    
    async def process_user_buffer(self, user_id: int):
        """
        Process accumulated audio buffer for a user.
        Called from the Discord thread via run_coroutine_threadsafe.
        """
        # Prevent concurrent processing for the same user
        if self.processing_locks.get(user_id, False):
            return
        
        self.processing_locks[user_id] = True
        
        try:
            buffer = self.user_buffers.get(user_id)
            if not buffer or len(buffer) == 0:
                return
            
            # Combine buffer chunks into single audio segment
            audio_segment = b''.join(buffer)
            buffer.clear()
            
            # Reset speech start time
            if user_id in self.user_speech_start:
                del self.user_speech_start[user_id]
            
            # Process the audio segment if it's long enough
            duration = len(audio_segment) / (self.config['sample_rate'] * 2)
            if duration >= self.config['min_speech_duration']:
                logger.info(f"Processing {duration:.2f}s audio buffer for user {user_id}")
                await self.process_audio_segment(user_id, audio_segment)
            else:
                logger.debug(f"Discarding short audio segment ({duration:.2f}s) for user {user_id}")
        
        except Exception as e:
            logger.error(f"Buffer processing error for user {user_id}: {e}", exc_info=True)
        
        finally:
            self.processing_locks[user_id] = False
    
    def write(self, data, user):
        """
        Called by Discord for each audio packet.
        Implements continuous streaming with buffered processing.
        """
        # Handle both user object and user_id integer
        user_id = user.id if hasattr(user, 'id') else user
        current_time = time.time()
        
        # Initialize user buffer if needed
        if user_id not in self.user_buffers:
            self.user_buffers[user_id] = deque()
            self.user_last_activity[user_id] = current_time
            self.processing_locks[user_id] = False
            logger.info(f"Started streaming for user {user_id}")
        
        # Format audio data
        audio_bytes = self.format_audio(data)
        
        # Log first few packets to confirm audio reception
        if len(self.user_buffers[user_id]) < 5:
            logger.debug(f"Received audio packet from user {user_id}, size: {len(audio_bytes)} bytes")
        
        # Apply energy-based VAD
        if self.has_speech(audio_bytes):
            # Track when speech started
            if user_id not in self.user_speech_start:
                self.user_speech_start[user_id] = current_time
                logger.debug(f"Speech detected for user {user_id}")
            
            # Add to buffer and update activity time
            self.user_buffers[user_id].append(audio_bytes)
            self.user_last_activity[user_id] = current_time
            
            # Check if we should process the buffer
            buffer = self.user_buffers[user_id]
            total_samples = sum(len(chunk) for chunk in buffer) // 2
            buffer_duration = total_samples / self.config['sample_rate']
            
            # Process if buffer is full
            if buffer_duration >= self.config['buffer_duration']:
                logger.debug(f"Buffer full for user {user_id} ({buffer_duration:.2f}s), processing...")
                # Use run_coroutine_threadsafe to process in the bot's event loop
                asyncio.run_coroutine_threadsafe(
                    self.process_user_buffer(user_id),
                    self.bot_event_loop
                )
            
            # Prevent buffer from growing too large
            if buffer_duration > self.config['max_buffer_size']:
                # Remove oldest chunks
                while buffer and buffer_duration > self.config['max_buffer_size']:
                    buffer.popleft()
                    total_samples = sum(len(chunk) for chunk in buffer) // 2
                    buffer_duration = total_samples / self.config['sample_rate']
                logger.debug(f"Trimmed buffer for user {user_id} to {buffer_duration:.2f}s")
        
        else:
            # Silence detected - check if we should process accumulated speech
            if (user_id in self.user_speech_start and 
                user_id in self.user_buffers and 
                len(self.user_buffers[user_id]) > 0):
                
                # Calculate silence duration
                last_activity = self.user_last_activity.get(user_id, current_time)
                silence_duration = current_time - last_activity
                
                # Process buffer if silence timeout reached
                if silence_duration >= self.config['silence_timeout']:
                    buffer = self.user_buffers[user_id]
                    total_samples = sum(len(chunk) for chunk in buffer) // 2
                    buffer_duration = total_samples / self.config['sample_rate']
                    
                    logger.debug(f"Silence timeout for user {user_id}, processing {buffer_duration:.2f}s buffer")
                    
                    # Use run_coroutine_threadsafe to process in the bot's event loop
                    asyncio.run_coroutine_threadsafe(
                        self.process_user_buffer(user_id),
                        self.bot_event_loop
                    )
    
    def cleanup(self):
        """Clean up resources when sink is stopped."""
        logger.info("Cleaning up StreamingAudioSink")
        
        # Process any remaining buffers
        for user_id in list(self.user_buffers.keys()):
            if len(self.user_buffers[user_id]) > 0:
                logger.info(f"Processing remaining buffer for user {user_id}")
                # Process remaining audio synchronously
                asyncio.run_coroutine_threadsafe(
                    self.process_user_buffer(user_id),
                    self.bot_event_loop
                )
        
        # Clear buffers
        self.user_buffers.clear()
        self.user_last_activity.clear()
        self.user_speech_start.clear()
        self.processing_locks.clear()
        
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
                'chunks_in_buffer': len(buffer),
                'is_speaking': user_id in self.user_speech_start,
                'processing': self.processing_locks.get(user_id, False)
            }
        
        return status
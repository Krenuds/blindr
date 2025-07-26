"""
Streaming Audio Sink for continuous Discord voice processing.
Uses Discord's built-in VAD with timeout-based segmentation.
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
    Continuous audio processing sink that trusts Discord's built-in VAD.
    Uses timeout-based segmentation to process speech segments sent by Discord.
    Discord only sends audio packets during detected speech activity.
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
        
        # Trust Discord VAD configuration
        self.config = {
            'trust_discord_vad': True,       # Trust Discord's built-in VAD
            'buffer_duration': 5.0,          # Seconds of audio per segment
            'sample_rate': 48000,            # Discord's native sample rate
            'silence_timeout': 1.0,          # Seconds after last packet before processing
            'segment_timeout': 2.0,          # Longer timeout to complete segments
            'max_buffer_size': 10.0,         # Maximum buffer size in seconds
            'force_process_threshold': 8.0,  # Force processing at this threshold to prevent accumulation
            'min_speech_duration': 0.3,      # Minimum speech duration to process
            # overlap_duration removed - using clean segment isolation
        }
        
        if config:
            self.config.update(config)
        
        # Audio buffers for each user
        self.user_buffers: Dict[int, deque] = {}
        self.user_last_activity: Dict[int, float] = {}
        self.user_speech_start: Dict[int, float] = {}
        self.user_last_packet_time: Dict[int, float] = {}  # Track last packet time for timeout detection
        self.user_timeout_tasks: Dict[int, asyncio.Task] = {}  # Background tasks for timeout detection
        self.processing_locks: Dict[int, bool] = {}
        # Removed overlap buffers and transcription merging for clean segment isolation
        
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
        
        # Basic silence trimming
        if len(audio_array) > 320:  # At least 20ms of audio
            window_size = 160  # 10ms at 16kHz
            energy_threshold = np.max(np.abs(audio_array)) * 0.02  # 2% of max amplitude
            
            # Find first non-silent sample
            start_idx = 0
            for i in range(0, len(audio_array) - window_size, window_size):
                window_energy = np.mean(np.abs(audio_array[i:i+window_size]))
                if window_energy > energy_threshold:
                    start_idx = max(0, i - window_size)  # Include one window before speech
                    break
            
            # Find last non-silent sample
            end_idx = len(audio_array)
            for i in range(len(audio_array) - window_size, window_size, -window_size):
                window_energy = np.mean(np.abs(audio_array[i:i+window_size]))
                if window_energy > energy_threshold:
                    end_idx = min(len(audio_array), i + 2 * window_size)  # Include one window after speech
                    break
            
            # Trim the audio if we found speech
            if start_idx < end_idx - window_size:
                audio_array = audio_array[start_idx:end_idx]
        
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
            
            # Basic transcription parameters
            transcription_params = {
                "filename": f"stream_user_{user_id}.wav",
                "language": "en",
                "task": "transcribe"
            }
            
            result = await self.whisper_client.transcribe_bytes(wav_data, **transcription_params)
            
            if result and result.get('text'):
                transcribed_text = result['text'].strip()
                if transcribed_text:
                    # Clean segment isolation - no merging with previous transcriptions
                    await self.send_transcription(user_id, transcribed_text, duration)
                    logger.info(f"✅ Transcribed for user {user_id}: {transcribed_text}")
                else:
                    logger.debug(f"Empty transcription result for user {user_id}")
            else:
                logger.warning(f"No text in Whisper result for user {user_id}: {result}")
            
        except Exception as e:
            logger.error(f"Audio processing error for user {user_id}: {e}")
    
    # Removed merge_transcriptions method - using clean segment isolation
    
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
            
            # Clean segment isolation - no overlap between buffers
            
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
        
        Note: Discord only calls this during detected speech activity.
        We trust Discord's VAD and focus on timeout-based segmentation.
        """
        # Handle both user object and user_id integer
        user_id = user.id if hasattr(user, 'id') else user
        current_time = time.time()
        
        # Initialize user buffer if needed
        if user_id not in self.user_buffers:
            self.user_buffers[user_id] = deque()
            self.user_last_activity[user_id] = current_time
            self.user_last_packet_time[user_id] = current_time
            self.processing_locks[user_id] = False
            logger.info(f"Started streaming for user {user_id}")
        
        # Format audio data
        audio_bytes = self.format_audio(data)
        
        # Log first few packets to confirm audio reception
        if len(self.user_buffers[user_id]) < 5:
            logger.debug(f"Received audio packet from user {user_id}, size: {len(audio_bytes)} bytes")
        
        # Trust Discord VAD - any packet means speech detected
        if self.config.get('trust_discord_vad', True):
            # Track when speech started
            if user_id not in self.user_speech_start:
                self.user_speech_start[user_id] = current_time
                logger.debug(f"Speech segment started for user {user_id}")
            
            # Add to buffer and update activity time
            self.user_buffers[user_id].append(audio_bytes)
            self.user_last_activity[user_id] = current_time
            
            # Check if we should process the buffer
            buffer = self.user_buffers[user_id]
            total_samples = sum(len(chunk) for chunk in buffer) // 2
            buffer_duration = total_samples / self.config['sample_rate']
            
            # Force processing at threshold to prevent massive buffer accumulation
            force_threshold = self.config.get('force_process_threshold', 8.0)
            if buffer_duration >= force_threshold and not self.processing_locks.get(user_id, False):
                logger.warning(f"⚠️ Force processing buffer for user {user_id} ({buffer_duration:.2f}s) to prevent accumulation")
                asyncio.run_coroutine_threadsafe(
                    self.process_user_buffer(user_id),
                    self.bot_event_loop
                )
            # Process if buffer reaches normal duration  
            elif buffer_duration >= self.config['buffer_duration'] and not self.processing_locks.get(user_id, False):
                logger.debug(f"Buffer full for user {user_id} ({buffer_duration:.2f}s), processing...")
                asyncio.run_coroutine_threadsafe(
                    self.process_user_buffer(user_id),
                    self.bot_event_loop
                )
        
        # Update last packet time
        self.user_last_packet_time[user_id] = current_time
        
        # Cancel and recreate timeout task for each speech segment
        # This ensures each new speech gets its own timeout handler
        if user_id in self.user_timeout_tasks:
            self.user_timeout_tasks[user_id].cancel()
            self.user_timeout_tasks.pop(user_id, None)
        
        # Always create fresh timeout task for current speech segment
        timeout_duration = self.config.get('segment_timeout', 2.0)
        future = asyncio.run_coroutine_threadsafe(
            self.timeout_handler(user_id, timeout_duration),
            self.bot_event_loop
        )
        self.user_timeout_tasks[user_id] = future
    
    
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
            'mode': 'trust_discord_vad',
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
                'last_packet_ago': round(current_time - last_activity, 2),
                'chunks_in_buffer': len(buffer),
                'speech_segment_active': user_id in self.user_speech_start,
                'processing': self.processing_locks.get(user_id, False)
            }
        
        return status
    
    async def timeout_handler(self, user_id: int, timeout_duration: float):
        """
        Handle speech timeout for a user.
        Single-execution model to prevent conflicts.
        """
        try:
            start_time = self.user_last_packet_time.get(user_id, 0)
            
            # Wait for timeout, but check for new packets during wait
            await asyncio.sleep(timeout_duration)
            
            # Process if enough time has passed since last packet
            current_time = time.time()
            time_since_last_packet = current_time - self.user_last_packet_time.get(user_id, 0)
            
            if time_since_last_packet >= timeout_duration:
                logger.info(f"⏰ Speech segment timeout ({timeout_duration:.1f}s) - processing buffer for user {user_id}")
                
                if (user_id in self.user_buffers and 
                    len(self.user_buffers[user_id]) > 0):
                    await self.process_user_buffer(user_id)
            else:
                logger.debug(f"Timeout cancelled - new speech detected for user {user_id}")
                    
        except Exception as e:
            logger.error(f"Error in timeout handler for user {user_id}: {e}")
        finally:
            # Always clean up timeout task reference
            self.user_timeout_tasks.pop(user_id, None)
    

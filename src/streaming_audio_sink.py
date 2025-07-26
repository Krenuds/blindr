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
            'buffer_duration': 5.0,          # Seconds of audio per segment (increased for better context)
            'sample_rate': 48000,            # Discord's native sample rate
            'silence_timeout': 0.5,          # Seconds of silence before processing (reduced for faster response)
            'max_buffer_size': 10.0,         # Maximum buffer size in seconds
            'min_speech_duration': 0.3,      # Minimum speech duration to process (reduced)
            'overlap_duration': 0.5,         # Seconds of audio to keep for overlap between buffers
            # Prompt mode configuration
            'prompt_mode': False,            # Enable prompt mode for longer inputs
            'prompt_silence_timeout': 2.0,   # Longer silence timeout for prompts
            'prompt_max_duration': 30.0,     # Maximum prompt duration in seconds
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
        self.user_overlap_buffers: Dict[int, bytes] = {}  # Store overlap audio for continuity
        self.user_last_transcription: Dict[int, str] = {}  # Store last transcription for merging
        # Prompt mode state
        self.user_prompt_active: Dict[int, bool] = {}  # Track if user is in prompt mode
        self.user_prompt_start: Dict[int, float] = {}  # Track prompt start time
        self.user_prompt_transcriptions: Dict[int, list] = {}  # Accumulate prompt transcriptions
        self.user_prompt_finalizing: Dict[int, bool] = {}  # Track if prompt is being finalized
        
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
        
        # Trim silence from beginning and end to reduce hallucinations
        # Simple energy-based silence trimming
        if len(audio_array) > 160:  # At least 10ms of audio
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
            
            # Add prompt-specific parameters for better accuracy
            # Avoid repetitive prompts that might appear in the output
            initial_prompt = None
            if self.config['prompt_mode'] and len(audio_segment) > 48000:  # Only for longer segments
                # Use simple, non-repetitive prompts
                initial_prompt = ""
            
            result = await self.whisper_client.transcribe_bytes(
                wav_data,
                filename=f"stream_user_{user_id}.wav",
                language="en",  # Force English to reduce hallucinations
                initial_prompt=initial_prompt
            )
            
            if result and result.get('text'):
                transcribed_text = result['text'].strip()
                if transcribed_text:
                    # Merge with previous transcription if needed
                    final_text = await self.merge_transcriptions(user_id, transcribed_text)
                    
                    # In prompt mode, accumulate transcriptions
                    if self.config['prompt_mode'] and self.user_prompt_active.get(user_id, False):
                        if user_id not in self.user_prompt_transcriptions:
                            self.user_prompt_transcriptions[user_id] = []
                        self.user_prompt_transcriptions[user_id].append(final_text)
                        logger.info(f"📝 Accumulated prompt segment for user {user_id}: {final_text}")
                    else:
                        # Send transcription to Discord channel
                        await self.send_transcription(user_id, final_text, duration)
                        logger.info(f"✅ Transcribed for user {user_id}: {final_text}")
                    
                    # Store for next merge
                    self.user_last_transcription[user_id] = transcribed_text
                else:
                    logger.debug(f"Empty transcription result for user {user_id}")
            else:
                logger.warning(f"No text in Whisper result for user {user_id}: {result}")
            
        except Exception as e:
            logger.error(f"Audio processing error for user {user_id}: {e}")
    
    async def merge_transcriptions(self, user_id: int, new_text: str) -> str:
        """
        Merge new transcription with previous to handle overlap.
        Removes duplicate words at the boundary.
        """
        if user_id not in self.user_last_transcription:
            return new_text
        
        last_text = self.user_last_transcription[user_id]
        if not last_text:
            return new_text
        
        # Split into words
        last_words = last_text.split()
        new_words = new_text.split()
        
        if not last_words or not new_words:
            return new_text
        
        # Find overlap by checking if end of last matches beginning of new
        overlap_found = False
        for i in range(min(len(last_words), len(new_words))):
            # Check if last i words of previous match first i words of new
            if i > 0 and last_words[-i:] == new_words[:i]:
                # Remove the overlapping words from the beginning of new text
                merged_words = new_words[i:]
                overlap_found = True
                logger.debug(f"Found {i} word overlap for user {user_id}")
                break
        
        if overlap_found and merged_words:
            return ' '.join(merged_words)
        else:
            # No overlap found, return as is
            return new_text
    
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
            
            # Calculate overlap samples to keep
            overlap_samples = int(self.config['overlap_duration'] * self.config['sample_rate'] * 2)  # 2 bytes per sample
            
            # Store overlap for next buffer (last part of current buffer)
            if len(audio_segment) > overlap_samples:
                self.user_overlap_buffers[user_id] = audio_segment[-overlap_samples:]
            
            # Prepend previous overlap if exists
            if user_id in self.user_overlap_buffers:
                audio_segment = self.user_overlap_buffers[user_id] + audio_segment
            
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
            self.user_last_packet_time[user_id] = current_time
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
                
                # In prompt mode, activate prompt tracking
                if self.config['prompt_mode'] and not self.user_prompt_active.get(user_id, False) and not self.user_prompt_finalizing.get(user_id, False):
                    self.user_prompt_active[user_id] = True
                    self.user_prompt_finalizing[user_id] = False
                    self.user_prompt_start[user_id] = current_time
                    self.user_prompt_transcriptions[user_id] = []
                    logger.info(f"🎙️ Prompt started for user {user_id}")
            
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
            
            # In prompt mode, check for hard cap
            if self.config['prompt_mode'] and self.user_prompt_active.get(user_id, False):
                prompt_duration = current_time - self.user_prompt_start.get(user_id, current_time)
                if prompt_duration >= self.config['prompt_max_duration']:
                    # Check if we're already finalizing to prevent duplicates
                    if not self.user_prompt_finalizing.get(user_id, False):
                        logger.info(f"⏱️ Prompt hard cap reached for user {user_id} ({prompt_duration:.1f}s)")
                        # Mark as finalizing BEFORE setting inactive
                        self.user_prompt_finalizing[user_id] = True
                        # Mark prompt as inactive to prevent multiple finalizations
                        self.user_prompt_active[user_id] = False
                        logger.info(f"📋 Finalizing prompt for user {user_id} with {len(self.user_prompt_transcriptions.get(user_id, []))} segments")
                        # Process remaining buffer
                        asyncio.run_coroutine_threadsafe(
                            self.process_user_buffer(user_id),
                            self.bot_event_loop
                        )
                        # Finalize the prompt
                        asyncio.run_coroutine_threadsafe(
                            self.finalize_prompt(user_id),
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
        
        # Update last packet time and start/restart timeout task
        self.user_last_packet_time[user_id] = current_time
        
        # Cancel existing timeout task if any
        if user_id in self.user_timeout_tasks:
            self.user_timeout_tasks[user_id].cancel()
        
        # Start new timeout task
        timeout_duration = (self.config['prompt_silence_timeout'] 
                           if self.config['prompt_mode'] and self.user_prompt_active.get(user_id, False)
                           else self.config['silence_timeout'])
        
        # Schedule the timeout handler in the bot's event loop
        future = asyncio.run_coroutine_threadsafe(
            self.timeout_handler(user_id, timeout_duration),
            self.bot_event_loop
        )
        self.user_timeout_tasks[user_id] = future
    
    async def finalize_prompt(self, user_id: int):
        """
        Finalize a prompt by combining all accumulated transcriptions.
        """
        logger.info(f"🔄 finalize_prompt called for user {user_id}")
        # Check if there are no transcriptions to finalize
        transcriptions = self.user_prompt_transcriptions.get(user_id, [])
        if not transcriptions:
            logger.warning(f"⚠️ No transcriptions found for user {user_id} during finalization")
            # Reset finalizing flag even if no transcriptions
            self.user_prompt_finalizing[user_id] = False
            return
        
        try:
            # Combine all transcriptions into complete prompt
            complete_prompt = ' '.join(transcriptions)
            
            # Calculate total prompt duration
            prompt_duration = time.time() - self.user_prompt_start.get(user_id, time.time())
            
            # Send complete prompt as a single message
            await self.send_transcription(user_id, f"[PROMPT {prompt_duration:.1f}s] {complete_prompt}", prompt_duration)
            logger.info(f"🎯 Prompt completed for user {user_id} ({prompt_duration:.1f}s): {complete_prompt[:100]}...")
            
            # Reset prompt state
            self.user_prompt_active[user_id] = False
            self.user_prompt_finalizing[user_id] = False
            self.user_prompt_transcriptions[user_id] = []
            if user_id in self.user_prompt_start:
                del self.user_prompt_start[user_id]
        
        except Exception as e:
            logger.error(f"Error finalizing prompt for user {user_id}: {e}")
    
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
        self.user_overlap_buffers.clear()
        self.user_last_transcription.clear()
        
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
    
    async def timeout_handler(self, user_id: int, timeout_duration: float):
        """
        Handle speech timeout for a user.
        Called after silence timeout to process accumulated audio.
        """
        try:
            # Wait for the timeout duration
            await asyncio.sleep(timeout_duration)
            
            logger.info(f"⏰ Speech timeout ({timeout_duration:.1f}s) reached for user {user_id}")
            
            # Check if user still has audio to process
            if (user_id in self.user_buffers and 
                len(self.user_buffers[user_id]) > 0):
                
                # Process the accumulated buffer
                logger.info(f"Processing accumulated buffer after timeout for user {user_id}")
                await self.process_user_buffer(user_id)
                
                # In prompt mode, finalize the prompt
                if self.config['prompt_mode'] and self.user_prompt_active.get(user_id, False):
                    # Check if we're already finalizing to prevent duplicates
                    if not self.user_prompt_finalizing.get(user_id, False):
                        logger.info(f"📋 Finalizing prompt after timeout for user {user_id}")
                        self.user_prompt_finalizing[user_id] = True
                        self.user_prompt_active[user_id] = False
                        await self.finalize_prompt(user_id)
            
            # Clean up the timeout task reference
            if user_id in self.user_timeout_tasks:
                del self.user_timeout_tasks[user_id]
                
        except asyncio.CancelledError:
            # Task was cancelled (new speech detected), this is normal
            logger.debug(f"Timeout task cancelled for user {user_id} (new speech detected)")
        except Exception as e:
            logger.error(f"Error in timeout handler for user {user_id}: {e}")
    
    async def finalize_prompt(self, user_id: int):
        """
        Finalize a prompt by combining all accumulated transcriptions.
        """
        logger.info(f"🔄 finalize_prompt called for user {user_id}")
        # Check if there are no transcriptions to finalize
        transcriptions = self.user_prompt_transcriptions.get(user_id, [])
        if not transcriptions:
            logger.warning(f"⚠️ No transcriptions found for user {user_id} during finalization")
            # Reset finalizing flag even if no transcriptions
            self.user_prompt_finalizing[user_id] = False
            return
        
        # Combine all transcriptions into one prompt
        combined_text = " ".join(transcriptions)
        prompt_start_time = self.user_prompt_start.get(user_id, time.time())
        prompt_duration = time.time() - prompt_start_time
        
        # Send the combined prompt
        await self.send_transcription(user_id, f"[PROMPT {prompt_duration:.1f}s] {combined_text}", prompt_duration)
        logger.info(f"🎯 Prompt completed for user {user_id} ({prompt_duration:.1f}s): {combined_text[:100]}...")
        
        # Clean up prompt state
        self.user_prompt_transcriptions[user_id] = []
        self.user_prompt_finalizing[user_id] = False
        if user_id in self.user_prompt_start:
            del self.user_prompt_start[user_id]
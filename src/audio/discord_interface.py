"""
Discord Audio Interface

Discord-specific implementation of audio capture and processing.
Wraps core audio processing components to work with Discord's voice system.
"""

import asyncio
import logging
import discord
from typing import Dict, Any, Optional
from .streaming_sink import AudioProcessor, BufferManager, TimeoutManager

logger = logging.getLogger(__name__)


class DiscordAudioSink(discord.sinks.Sink):
    """
    Discord-specific audio sink that bridges Discord voice capture
    to core audio processing components.
    
    This class handles Discord integration while delegating audio
    processing to domain-specific components.
    """

    def __init__(
        self, whisper_client, bot_event_loop, config: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize Discord audio sink.

        Args:
            whisper_client: WhisperClient instance for transcription
            bot_event_loop: The bot's main event loop for cross-thread communication
            config: Audio processing configuration
        """
        super().__init__()
        self.whisper_client = whisper_client
        self.bot_event_loop = bot_event_loop
        self.config = {
            "trust_discord_vad": True,
            "buffer_duration": 5.0,
            "sample_rate": 48000,
            "silence_timeout": 1.0,
            "segment_timeout": 2.0,
            "max_buffer_size": 10.0,
            "force_process_threshold": 8.0,
            "min_speech_duration": 0.3,
        }
        if config:
            self.config.update(config)

        # Core audio processing components
        self.buffer_manager = BufferManager(self.config)
        self.audio_processor = AudioProcessor()
        self.timeout_manager = TimeoutManager(bot_event_loop)

        # Discord-specific callback for sending transcriptions
        self.send_transcription = None

        logger.info(f"DiscordAudioSink initialized with config: {self.config}")

    async def process_audio_segment(self, user_id: int, audio_segment: bytes):
        """
        Process a complete audio segment through the full pipeline.
        
        Args:
            user_id: Discord user ID
            audio_segment: Audio data to process
        """
        try:
            start_time = asyncio.get_event_loop().time()
            
            # Format audio for Whisper
            wav_bytes = self.audio_processor.pcm_to_wav(
                audio_segment, self.config["sample_rate"]
            )
            
            # Send to Whisper for transcription
            result = await self.whisper_client.transcribe_bytes(wav_bytes)
            
            if result and result.get("text", "").strip():
                text = result["text"].strip()
                duration = len(audio_segment) / (self.config["sample_rate"] * 2)
                
                # Send transcription through callback if available
                if self.send_transcription:
                    await self.send_transcription(user_id, text, duration)
                    
                processing_time = asyncio.get_event_loop().time() - start_time
                logger.info(
                    f"Processed audio: user={user_id}, duration={duration:.2f}s, "
                    f"processing_time={processing_time:.2f}s, text='{text[:100]}'"
                )
            
        except Exception as e:
            logger.error(f"Error processing audio segment for user {user_id}: {e}")

    def write(self, data, user):
        """
        Discord sink write method - receives audio data from Discord.
        
        Args:
            data: Audio data from Discord
            user: Discord user object
        """
        try:
            user_id = user.id
            
            # Initialize user if needed
            if not self.buffer_manager.is_user_initialized(user_id):
                self.buffer_manager.initialize_user(user_id)
                logger.debug(f"Initialized new user: {user_id}")

            # Process audio through buffer manager
            self._process_discord_audio(user_id, data)
            
        except Exception as e:
            logger.error(f"Error in Discord audio write: {e}")

    def _process_discord_audio(self, user_id: int, audio_data):
        """Process incoming Discord audio data."""
        try:
            # Convert Discord audio format
            processed_audio = self.audio_processor.format_audio(audio_data)
            mono_audio = self.audio_processor.stereo_to_mono(processed_audio)
            
            # Add to buffer
            should_process = self.buffer_manager.add_audio_chunk(user_id, mono_audio)
            
            # Handle timeout scheduling
            if self.config.get("trust_discord_vad", True):
                self._handle_discord_vad_timeout(user_id, should_process)
                
        except Exception as e:
            logger.error(f"Error processing Discord audio for user {user_id}: {e}")

    def _handle_discord_vad_timeout(self, user_id: int, should_process: bool):
        """Handle Discord VAD-based timeout logic."""
        if should_process:
            # Schedule timeout for end of speech detection
            self.timeout_manager.schedule_timeout(
                user_id,
                self.config["segment_timeout"],
                self._process_user_timeout
            )
        else:
            # Cancel timeout if speech continues
            self.timeout_manager.cancel_timeout(user_id)

    async def _process_user_timeout(self, user_id: int):
        """Process user timeout and send audio for transcription."""
        try:
            audio_buffer = self.buffer_manager.get_user_buffer(user_id)
            if not audio_buffer:
                return

            buffer_duration = self.buffer_manager.get_buffer_duration(user_id)
            
            # Check if buffer meets minimum requirements
            if buffer_duration < self.config["min_speech_duration"]:
                logger.debug(f"Buffer too short ({buffer_duration:.2f}s), skipping user {user_id}")
                self.buffer_manager.clear_user_buffer(user_id)
                return

            # Get and clear buffer
            audio_segment = self.buffer_manager.extract_user_buffer(user_id)
            
            # Process asynchronously
            await self.process_audio_segment(user_id, audio_segment)
            
        except Exception as e:
            logger.error(f"Error processing timeout for user {user_id}: {e}")

    def cleanup(self):
        """Clean up resources."""
        try:
            self.timeout_manager.cleanup_all_timeouts()
            self.buffer_manager.clear_all_buffers()
            logger.info("DiscordAudioSink cleanup completed")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """Get audio processing statistics."""
        return {
            "mode": "trust_discord_vad",
            "config": self.config,
            "active_users": len(self.buffer_manager.user_buffers),
            "timeout_tasks": len(self.timeout_manager.user_timeout_tasks),
        }
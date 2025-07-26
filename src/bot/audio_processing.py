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


class AudioProcessor:
    """
    Handles all audio format conversions for voice processing.
    Responsible for stereo-to-mono conversion, PCM formatting, and WAV generation.
    """

    @staticmethod
    def stereo_to_mono(stereo_data: bytes) -> bytes:
        """Convert stereo PCM to mono by mixing both channels (from brodan)"""
        try:
            if len(stereo_data) < 4:
                return stereo_data

            mono_samples = []
            for i in range(0, len(stereo_data), 4):
                if i + 3 < len(stereo_data):
                    left_sample = struct.unpack("<h", stereo_data[i : i + 2])[0]
                    right_sample = struct.unpack("<h", stereo_data[i + 2 : i + 4])[0]
                    mixed_sample = (left_sample + right_sample) // 2
                    mono_samples.append(mixed_sample)

            if not mono_samples:
                return b""

            return struct.pack(f"<{len(mono_samples)}h", *mono_samples)
        except Exception as e:
            logger.debug(f"Stereo to mono conversion error: {e}")
            return stereo_data[: len(stereo_data) - (len(stereo_data) % 4)]

    @staticmethod
    def format_audio(audio_data) -> bytes:
        """Convert audio data to bytes format expected by Whisper."""
        if hasattr(audio_data, "raw_data"):
            pcm_data = audio_data.raw_data
        else:
            pcm_data = audio_data

        mono_data = AudioProcessor.stereo_to_mono(pcm_data)
        return mono_data

    @staticmethod
    def pcm_to_wav(pcm_data: bytes, sample_rate: int = 48000) -> bytes:
        """
        Convert raw PCM data to WAV format with proper headers.
        Resamples to 16kHz if needed for Whisper compatibility.

        Args:
            pcm_data: Raw PCM audio data (16-bit mono)
            sample_rate: Sample rate (default: 48000 Hz)

        Returns:
            WAV file data as bytes at 16kHz
        """
        audio_array = np.frombuffer(pcm_data, dtype=np.int16)

        if sample_rate != 16000:
            resample_factor = sample_rate // 16000
            audio_array = audio_array[::resample_factor]
            sample_rate = 16000

        if len(audio_array) > 320:
            window_size = 160
            energy_threshold = np.max(np.abs(audio_array)) * 0.02

            start_idx = 0
            for i in range(0, len(audio_array) - window_size, window_size):
                window_energy = np.mean(np.abs(audio_array[i : i + window_size]))
                if window_energy > energy_threshold:
                    start_idx = max(0, i - window_size)
                    break

            end_idx = len(audio_array)
            for i in range(len(audio_array) - window_size, window_size, -window_size):
                window_energy = np.mean(np.abs(audio_array[i : i + window_size]))
                if window_energy > energy_threshold:
                    end_idx = min(len(audio_array), i + 2 * window_size)
                    break

            if start_idx < end_idx - window_size:
                audio_array = audio_array[start_idx:end_idx]

        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(audio_array.tobytes())

        wav_buffer.seek(0)
        return wav_buffer.read()


class BufferManager:
    """
    Manages user audio buffers and speech activity tracking.
    Responsible for buffer state, timing, and user-specific data management.
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.user_buffers: Dict[int, deque] = {}
        self.user_last_activity: Dict[int, float] = {}
        self.user_speech_start: Dict[int, float] = {}
        self.user_last_packet_time: Dict[int, float] = {}
        self.processing_locks: Dict[int, bool] = {}

    def initialize_user(self, user_id: int, current_time: float):
        """Initialize buffer and tracking data for a new user."""
        if user_id not in self.user_buffers:
            self.user_buffers[user_id] = deque()
            self.user_last_activity[user_id] = current_time
            self.user_last_packet_time[user_id] = current_time
            self.processing_locks[user_id] = False
            logger.info(f"Started streaming for user {user_id}")

    def add_audio_chunk(self, user_id: int, audio_bytes: bytes, current_time: float):
        """Add audio chunk to user's buffer and update timestamps."""
        if user_id not in self.user_speech_start:
            self.user_speech_start[user_id] = current_time
            logger.debug(f"Speech segment started for user {user_id}")

        self.user_buffers[user_id].append(audio_bytes)
        self.user_last_activity[user_id] = current_time
        self.user_last_packet_time[user_id] = current_time

    def get_buffer_duration(self, user_id: int) -> float:
        """Calculate total duration of audio in user's buffer."""
        if user_id not in self.user_buffers:
            return 0.0

        buffer = self.user_buffers[user_id]
        total_samples = sum(len(chunk) for chunk in buffer) // 2
        return total_samples / self.config["sample_rate"]

    def clear_user_buffer(self, user_id: int) -> bytes:
        """Clear user's buffer and return the accumulated audio data."""
        if user_id not in self.user_buffers or len(self.user_buffers[user_id]) == 0:
            return b""

        audio_segment = b"".join(self.user_buffers[user_id])
        self.user_buffers[user_id].clear()

        if user_id in self.user_speech_start:
            del self.user_speech_start[user_id]

        return audio_segment

    def should_force_process(self, user_id: int) -> bool:
        """Check if buffer should be force-processed due to size."""
        if self.processing_locks.get(user_id, False):
            return False

        buffer_duration = self.get_buffer_duration(user_id)
        force_threshold = self.config.get("force_process_threshold", 8.0)
        return buffer_duration >= force_threshold

    def should_process_buffer(self, user_id: int) -> bool:
        """Check if buffer should be processed due to normal size limit."""
        if self.processing_locks.get(user_id, False):
            return False

        buffer_duration = self.get_buffer_duration(user_id)
        return buffer_duration >= self.config["buffer_duration"]

    def set_processing_lock(self, user_id: int, locked: bool):
        """Set processing lock state for user."""
        self.processing_locks[user_id] = locked

    def is_processing_locked(self, user_id: int) -> bool:
        """Check if user buffer is currently being processed."""
        return self.processing_locks.get(user_id, False)

    def get_status(self) -> Dict[str, Any]:
        """Get current buffer status for all users."""
        current_time = time.time()
        users_status = {}

        for user_id, buffer in self.user_buffers.items():
            buffer_duration = self.get_buffer_duration(user_id)
            last_activity = self.user_last_activity.get(user_id, 0)
            users_status[user_id] = {
                "buffer_duration": round(buffer_duration, 2),
                "last_packet_ago": round(current_time - last_activity, 2),
                "chunks_in_buffer": len(buffer),
                "speech_segment_active": user_id in self.user_speech_start,
                "processing": self.processing_locks.get(user_id, False),
            }

        return users_status

    def cleanup_all_buffers(self):
        """Clean up all user buffers."""
        remaining_users = []
        for user_id in list(self.user_buffers.keys()):
            if len(self.user_buffers[user_id]) > 0:
                remaining_users.append(user_id)

        self.user_buffers.clear()
        self.user_last_activity.clear()
        self.user_speech_start.clear()
        self.processing_locks.clear()

        return remaining_users


class TimeoutManager:
    """
    Manages speech timeout scheduling for users.
    Responsible for timeout task lifecycle and cancellation.
    """

    def __init__(self, bot_event_loop):
        self.bot_event_loop = bot_event_loop
        self.user_timeout_tasks: Dict[int, asyncio.Task] = {}

    def schedule_timeout(
        self, user_id: int, timeout_duration: float, handler_coroutine
    ):
        """Schedule a timeout task for a user, canceling any existing timeout."""
        if user_id in self.user_timeout_tasks:
            self.user_timeout_tasks[user_id].cancel()
            self.user_timeout_tasks.pop(user_id, None)

        future = asyncio.run_coroutine_threadsafe(
            handler_coroutine, self.bot_event_loop
        )
        self.user_timeout_tasks[user_id] = future

    def cancel_timeout(self, user_id: int):
        """Cancel timeout for a specific user."""
        if user_id in self.user_timeout_tasks:
            self.user_timeout_tasks[user_id].cancel()
            self.user_timeout_tasks.pop(user_id, None)

    def cleanup_timeout(self, user_id: int):
        """Clean up timeout task for a user (called from timeout handler)."""
        self.user_timeout_tasks.pop(user_id, None)

    def cleanup_all_timeouts(self):
        """Cancel all pending timeout tasks."""
        for user_id in list(self.user_timeout_tasks.keys()):
            self.cancel_timeout(user_id)


class StreamingAudioSink(discord.sinks.Sink):
    """
    Main coordinator for Discord voice processing pipeline.

    Orchestrates audio processing components:
    - AudioProcessor: handles format conversions
    - BufferManager: manages user buffer state and tracking
    - TimeoutManager: handles speech timeout scheduling

    Focuses on Discord integration and Whisper communication.
    """

    def __init__(
        self, whisper_client, bot_event_loop, config: Optional[Dict[str, Any]] = None
    ):
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

        self.buffer_manager = BufferManager(self.config)
        self.audio_processor = AudioProcessor()
        self.timeout_manager = TimeoutManager(bot_event_loop)

        logger.info(f"StreamingAudioSink initialized with config: {self.config}")

    async def process_audio_segment(self, user_id: int, audio_segment: bytes):
        """
        Process a complete audio segment through Whisper.
        """
        try:
            duration = len(audio_segment) / (self.config["sample_rate"] * 2)
            if duration < self.config["min_speech_duration"]:
                logger.debug(
                    f"Audio segment too short for user {user_id}: {duration:.2f}s"
                )
                return
            logger.debug(f"Processing {duration:.2f}s audio segment for user {user_id}")
            wav_data = self.audio_processor.pcm_to_wav(
                audio_segment, self.config["sample_rate"]
            )
            logger.info(f"Sending {duration:.2f}s audio to Whisper for user {user_id}")
            transcription_params = {
                "filename": f"stream_user_{user_id}.wav",
                "language": "en",
                "task": "transcribe",
            }
            result = await self.whisper_client.transcribe_bytes(
                wav_data, **transcription_params
            )
            if result and result.get("text"):
                transcribed_text = result["text"].strip()
                if transcribed_text:
                    await self.send_transcription(user_id, transcribed_text, duration)
                    logger.info(
                        f"✅ Transcribed for user {user_id}: {transcribed_text}"
                    )
                else:
                    logger.debug(f"Empty transcription result for user {user_id}")
            else:
                logger.warning(
                    f"No text in Whisper result for user {user_id}: {result}"
                )
        except Exception as e:
            logger.error(f"Audio processing error for user {user_id}: {e}")

    async def send_transcription(self, user_id: int, text: str, duration: float):
        """
        Send transcription result to Discord channel.
        Override this method to customize transcription delivery.
        """
        logger.info(f"Transcription ready for user {user_id} ({duration:.1f}s): {text}")

    async def process_user_buffer(self, user_id: int):
        """
        Process accumulated audio buffer for a user.
        Called from the Discord thread via run_coroutine_threadsafe.
        """
        if self.buffer_manager.is_processing_locked(user_id):
            return

        self.buffer_manager.set_processing_lock(user_id, True)
        try:
            audio_segment = self.buffer_manager.clear_user_buffer(user_id)
            if not audio_segment:
                return

            duration = len(audio_segment) / (self.config["sample_rate"] * 2)
            if duration >= self.config["min_speech_duration"]:
                logger.info(
                    f"Processing {duration:.2f}s audio buffer for user {user_id}"
                )
                await self.process_audio_segment(user_id, audio_segment)
            else:
                logger.debug(
                    f"Discarding short audio segment ({duration:.2f}s) for user {user_id}"
                )
        except Exception as e:
            logger.error(
                f"Buffer processing error for user {user_id}: {e}", exc_info=True
            )
        finally:
            self.buffer_manager.set_processing_lock(user_id, False)

    def write(self, data, user):
        """
        Called by Discord for each audio packet.

        Note: Discord only calls this during detected speech activity.
        We trust Discord's VAD and focus on timeout-based segmentation.
        """
        user_id = user.id if hasattr(user, "id") else user
        current_time = time.time()

        self.buffer_manager.initialize_user(user_id, current_time)
        audio_bytes = self.audio_processor.format_audio(data)

        if self.buffer_manager.get_buffer_duration(user_id) == 0:
            logger.debug(
                f"Received audio packet from user {user_id}, size: {len(audio_bytes)} bytes"
            )

        if self.config.get("trust_discord_vad", True):
            self.buffer_manager.add_audio_chunk(user_id, audio_bytes, current_time)

            if self.buffer_manager.should_force_process(user_id):
                buffer_duration = self.buffer_manager.get_buffer_duration(user_id)
                logger.warning(
                    f"⚠️ Force processing buffer for user {user_id} ({buffer_duration:.2f}s) to prevent accumulation"
                )
                asyncio.run_coroutine_threadsafe(
                    self.process_user_buffer(user_id), self.bot_event_loop
                )
            elif self.buffer_manager.should_process_buffer(user_id):
                buffer_duration = self.buffer_manager.get_buffer_duration(user_id)
                logger.debug(
                    f"Buffer full for user {user_id} ({buffer_duration:.2f}s), processing..."
                )
                asyncio.run_coroutine_threadsafe(
                    self.process_user_buffer(user_id), self.bot_event_loop
                )

        timeout_duration = self.config.get("segment_timeout", 2.0)
        self.timeout_manager.schedule_timeout(
            user_id, timeout_duration, self.timeout_handler(user_id, timeout_duration)
        )

    def cleanup(self):
        """Clean up resources when sink is stopped."""
        logger.info("Cleaning up StreamingAudioSink")

        remaining_users = self.buffer_manager.cleanup_all_buffers()
        for user_id in remaining_users:
            logger.info(f"Processing remaining buffer for user {user_id}")
            asyncio.run_coroutine_threadsafe(
                self.process_user_buffer(user_id), self.bot_event_loop
            )

        self.timeout_manager.cleanup_all_timeouts()
        logger.info("StreamingAudioSink cleanup complete")

    @property
    def wants_opus(self) -> bool:
        """We want decoded PCM data, not Opus packets."""
        return False

    def get_status(self) -> Dict[str, Any]:
        """Get current streaming status for monitoring."""
        users_status = self.buffer_manager.get_status()
        status = {
            "mode": "trust_discord_vad",
            "active_users": len(users_status),
            "config": self.config,
            "users": users_status,
        }
        return status

    async def timeout_handler(self, user_id: int, timeout_duration: float):
        """
        Handle speech timeout for a user.
        Single-execution model to prevent conflicts.
        """
        try:
            start_time = self.buffer_manager.user_last_packet_time.get(user_id, 0)
            await asyncio.sleep(timeout_duration)
            current_time = time.time()
            time_since_last_packet = (
                current_time - self.buffer_manager.user_last_packet_time.get(user_id, 0)
            )
            if time_since_last_packet >= timeout_duration:
                logger.info(
                    f"⏰ Speech segment timeout ({timeout_duration:.1f}s) - processing buffer for user {user_id}"
                )
                if self.buffer_manager.get_buffer_duration(user_id) > 0:
                    await self.process_user_buffer(user_id)
            else:
                logger.debug(
                    f"Timeout cancelled - new speech detected for user {user_id}"
                )
        except Exception as e:
            logger.error(f"Error in timeout handler for user {user_id}: {e}")
        finally:
            self.timeout_manager.cleanup_timeout(user_id)
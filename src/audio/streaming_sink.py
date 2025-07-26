"""
Core Audio Processing Components

Pure audio processing classes for format conversion, buffer management,
and timeout handling. Independent of any specific interface (Discord, web, etc).
"""

import asyncio
import logging
import io
import time
import struct
import wave
from typing import Dict, Any, Optional
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
        
        # Prompt mode state
        self.user_prompt_active: Dict[int, bool] = {}  # Track if user is in prompt mode
        self.user_prompt_start: Dict[int, float] = {}  # Track prompt start time
        self.user_prompt_transcriptions: Dict[int, list] = {}  # Accumulate prompt transcriptions
        self.user_last_speech_time: Dict[int, float] = {}  # Track last speech time for prompt finalization

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
        self.user_prompt_active.clear()
        self.user_prompt_start.clear()
        self.user_prompt_transcriptions.clear()

        return remaining_users
    
    def start_prompt(self, user_id: int, current_time: float):
        """Start prompt mode for a user."""
        self.user_prompt_active[user_id] = True
        self.user_prompt_start[user_id] = current_time
        self.user_prompt_transcriptions[user_id] = []
        logger.info(f"🎙️ Prompt started for user {user_id}")
    
    def add_prompt_transcription(self, user_id: int, text: str):
        """Add a transcription to the prompt accumulator."""
        if user_id not in self.user_prompt_transcriptions:
            self.user_prompt_transcriptions[user_id] = []
        self.user_prompt_transcriptions[user_id].append(text)
        logger.info(f"📝 Accumulated prompt segment for user {user_id}: {text}")
    
    def get_prompt_transcriptions(self, user_id: int) -> list:
        """Get all accumulated transcriptions for a user."""
        return self.user_prompt_transcriptions.get(user_id, [])
    
    def clear_prompt(self, user_id: int):
        """Clear prompt state for a user."""
        self.user_prompt_active[user_id] = False
        self.user_prompt_transcriptions[user_id] = []
        if user_id in self.user_prompt_start:
            del self.user_prompt_start[user_id]


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
        """Schedule a timeout task for a user. Does not cancel existing timeouts."""
        # Don't schedule if one is already active
        if user_id in self.user_timeout_tasks:
            logger.debug(f"Timeout already scheduled for user {user_id}, skipping")
            return

        logger.debug(f"Scheduling timeout for user {user_id}, duration {timeout_duration}s")
        future = asyncio.run_coroutine_threadsafe(
            handler_coroutine, self.bot_event_loop
        )
        self.user_timeout_tasks[user_id] = future
        logger.debug(f"Timeout scheduled for user {user_id}, future: {future}")

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


# The StreamingAudioSink class has been moved to discord_interface.py as DiscordAudioSink
# This file now contains only the core audio processing components
"""
Audio Processing Domain

Core audio processing functionality including streaming audio capture,
format conversion, and integration with speech recognition services.
"""

from .streaming_sink import AudioProcessor, BufferManager, TimeoutManager
from .discord_interface import DiscordAudioSink

__all__ = [
    "AudioProcessor", 
    "BufferManager",
    "TimeoutManager",
    "DiscordAudioSink"
]
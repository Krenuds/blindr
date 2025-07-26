"""
Discord Bot Package

This package contains all Discord voice bot functionality including:
- VoiceBot: Main Discord bot class
- StreamingAudioSink: Audio processing coordination
- AudioProcessor: Audio format conversions
- BufferManager: User buffer state management
- TimeoutManager: Speech timeout scheduling
"""

from .voice_bot import VoiceBot
from .audio_processing import (
    StreamingAudioSink,
    AudioProcessor,
    BufferManager,
    TimeoutManager,
)

__all__ = [
    "VoiceBot",
    "StreamingAudioSink",
    "AudioProcessor",
    "BufferManager",
    "TimeoutManager",
]
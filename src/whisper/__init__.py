"""
Whisper Package

This package contains Whisper speech-to-text service components:
- WhisperClient: HTTP client for communicating with Whisper service
- WhisperService: FastAPI service providing speech recognition
"""

from .client import WhisperClient, transcribe_audio_file, check_whisper_health
from .service import WhisperService

__all__ = [
    "WhisperClient",
    "WhisperService", 
    "transcribe_audio_file",
    "check_whisper_health",
]
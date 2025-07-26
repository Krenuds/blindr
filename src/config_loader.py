#!/usr/bin/env python3
"""
Simple configuration loader for audio processing settings
"""

import json
import os
from pathlib import Path
from typing import Dict, Any

def load_audio_config() -> Dict[str, Any]:
    """Load audio configuration from config file"""
    config_path = Path(__file__).parent.parent / "config" / "audio_config.json"
    
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")
    
    with open(config_path, 'r') as f:
        return json.load(f)

def get_streaming_config() -> Dict[str, Any]:
    """Get configuration for StreamingAudioSink"""
    config = load_audio_config()
    
    # Trust Discord VAD configuration
    streaming_config = {
        'trust_discord_vad': config['audio_processing'].get('trust_discord_vad', True),
        'buffer_duration': config['audio_processing']['buffer_duration'],
        'sample_rate': 48000,  # Discord's native sample rate
        'silence_timeout': config['audio_processing']['silence_timeout'],
        'segment_timeout': config['audio_processing'].get('segment_timeout', 2.0),
        'max_buffer_size': config['audio_processing']['max_buffer_size'],
        'min_speech_duration': config['audio_processing']['min_speech_duration'],
        'overlap_duration': config['audio_processing']['overlap_duration'],
    }
    
    return streaming_config

def get_whisper_config() -> Dict[str, Any]:
    """Get configuration for Whisper service"""
    config = load_audio_config()
    return config['whisper']


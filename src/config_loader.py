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
    
    # Merge audio_processing and prompt_mode configs
    streaming_config = {
        'energy_threshold': config['audio_processing']['energy_threshold'],
        'buffer_duration': config['audio_processing']['buffer_duration'],
        'sample_rate': 48000,  # Discord's native sample rate
        'silence_timeout': config['audio_processing']['silence_timeout'],
        'max_buffer_size': config['audio_processing']['max_buffer_size'],
        'min_speech_duration': config['audio_processing']['min_speech_duration'],
        'overlap_duration': config['audio_processing']['overlap_duration'],
        'prompt_mode': config['prompt_mode']['enabled'],
        'prompt_silence_timeout': config['prompt_mode']['silence_timeout'],
        'prompt_max_duration': config['prompt_mode']['max_duration'],
    }
    
    return streaming_config

def get_whisper_config() -> Dict[str, Any]:
    """Get configuration for Whisper service"""
    config = load_audio_config()
    return config['whisper']

def get_experimental_config() -> Dict[str, Any]:
    """Get experimental configuration options"""
    config = load_audio_config()
    return config['experimental']
# Streaming Audio Design Document

**Objective**: Replace manual recording with continuous audio streaming using brodan's proven approach

## Current State → Target State

**Current**: Manual start/stop commands → chunk recording → file processing → transcription  
**Target**: Continuous audio stream → buffered segments → real-time Whisper transcription

## Brodan's Proven Solution

Use brodan's **STTAudioSink** approach with buffered streaming:

### Audio Pipeline
```
Discord 48kHz → STTAudioSink → Energy-based VAD → Buffered segments (3s) → Whisper → Real-time transcription
```

**Simple VAD**: Energy threshold (configurable) filters silence  
**Buffered Processing**: 3-8 second audio segments sent to Whisper  
**Auto-join**: Starts streaming immediately on voice connection

## Implementation Plan

### 1. Adapt from Brodan Repository
**Copy and modify these files:**
- `brodan/src/audio_processor.py` → `blindr/src/streaming_audio_sink.py` (adapt STTAudioSink class)
- `brodan/src/stt_client.py` → `blindr/src/whisper_client.py` (merge buffered processing)
- `brodan/config/stt_config.json` → `blindr/config/audio_config.json` (simplified config)

### 2. Modify Existing Files
**bot.py changes:**
- Remove: `!start_recording`, `!stop_recording` commands
- Remove: connections, recording_sinks globals  
- Add: Auto-join voice channel and start STTAudioSink immediately
- Update: Status command to show streaming status

**Remove files:**
- `audio_sinks.py` - Replace with brodan's streaming approach

### 3. Key Components from Brodan
- **STTAudioSink**: Continuous `write()` method processing
- **Energy-based VAD**: Simple threshold detection (energy_threshold: 50)
- **Buffered segments**: 3-second audio chunks to Whisper
- **Auto-join**: Immediate streaming on voice connection

## Key Features
- **Proven approach** - Production-tested from brodan
- **Simple VAD** - Energy threshold instead of complex detection
- **Real-time processing** - 3-second buffered segments
- **Auto-operation** - No manual commands needed

## Success Criteria  
- Continuous streaming with 3-second transcription segments
- Energy-based silence filtering
- No manual intervention required
# Git Log - blindr

Generated on: 2025-07-26 14:36:45
Directory: /home/travis/blindr

## Last 5 Commits

### 1. Commit: 3f2f4372

- **Author:** Claude Code
- **Date:** 2025-07-26 14:21:17 -0400
- **Subject:** fix: resolve timeout scheduling race condition in Discord VAD processing - TESTED ✅

**Full Commit Message:**
```
fix: resolve timeout scheduling race condition in Discord VAD processing - TESTED ✅

## Problem Identified
The audio streaming would start but never properly process speech segments due to a
timeout scheduling race condition. Timeouts were being scheduled on every Discord
audio packet instead of once per speech segment, preventing the timeout handlers
from ever executing and processing buffered audio for transcription.

## Root Cause
- Discord VAD sends audio packets continuously during speech
- Each packet triggered a new timeout schedule via `_handle_discord_vad_timeout()`
- Previous timeouts were cancelled and replaced before they could complete
- Result: Audio buffers accumulated but were never sent to Whisper for processing

## Solution Applied
1. **Single Timeout Per User**: Added check `if user_id not in self.timeout_manager.user_timeout_tasks:`
   - Prevents scheduling multiple concurrent timeouts for the same user
   - Allows timeout to complete its full duration and process the audio buffer

2. **Enhanced Debug Logging**: Added detailed timeout lifecycle logging
   - Track timeout scheduling, sleep duration, and processing decisions
   - Helps identify timing issues in speech segmentation

## Testing Results
✅ Audio streaming starts correctly
✅ Timeouts now execute after speech segments end
✅ Audio buffers are processed and sent to Whisper
✅ No more hanging "started streaming" state

## Ready For
- End-to-end voice transcription testing with real speech input
- LLM integration phase with working audio → text pipeline

🤖 Generated with [Claude Code](https://claude.ai/code)

Co-Authored-By: Claude <noreply@anthropic.com>
```

---

### 2. Commit: 30bbe2db

- **Author:** Claude Code
- **Date:** 2025-07-26 14:08:42 -0400
- **Subject:** fix: resolve audio processing errors in reorganized architecture - TESTED ✅

**Full Commit Message:**
```
fix: resolve audio processing errors in reorganized architecture - TESTED ✅

## Audio Processing Fixes
Fixed critical runtime errors in the Discord audio interface after domain reorganization.

## Issues Resolved:
1. **User ID Extraction**: Fixed `'int' object has no attribute 'id'` error
   - Added proper handling: `user_id = user.id if hasattr(user, "id") else user`
   - Matches original Discord.py behavior

2. **Buffer Manager Integration**: Fixed method signature mismatches
   - Updated `add_audio_chunk()` calls to include `current_time` parameter
   - Fixed `_process_user_timeout()` to use `clear_user_buffer()` correctly

3. **Timeout Handler**: Implemented proper async timeout pattern
   - Added `_timeout_handler()` coroutine for speech segmentation
   - Maintains original timeout logic for VAD-based processing

4. **Import Dependencies**: Made Whisper service import optional
   - Bot can run in client-only mode when torch not available
   - Graceful degradation for development environments

## Testing Results:
✅ Bot connects to Discord successfully
✅ Joins voice channel without errors
✅ Audio processing pipeline initializes correctly
✅ No runtime errors in audio write operations

## Ready For:
- Voice transcription testing with Whisper service
- End-to-end audio → transcription → Discord workflow

🤖 Generated with [Claude Code](https://claude.ai/code)

Co-Authored-By: Claude <noreply@anthropic.com>
```

---

### 3. Commit: 2028b8fa

- **Author:** Claude Code
- **Date:** 2025-07-26 14:03:12 -0400
- **Subject:** refactor: reorganize into audio-centric domain architecture - UNTESTED

**Full Commit Message:**
```
refactor: reorganize into audio-centric domain architecture - UNTESTED

## Domain Reorganization Complete
Successfully inverted the architecture to make audio processing the core domain
instead of Discord being central. This creates a cleaner, more extensible structure.

## New Architecture:
- **Audio Domain**: Core audio processing (AudioProcessor, BufferManager, TimeoutManager)
- **Discord Interface**: Lightweight wrapper around audio core (DiscordAudioSink)
- **Bot Package**: Pure Discord I/O, commands, and channel management

## Changes Made:
1. **Created `src/audio/` package** - Core audio processing domain
   - `streaming_sink.py` - Pure audio processing components
   - `discord_interface.py` - Discord-specific audio capture

2. **Simplified `src/bot/voice_bot.py`** - Now uses audio domain
   - Removed audio processing logic
   - Clean import from audio domain
   - Focus on Discord ceremony only

3. **Removed `src/bot/audio_processing.py`** - Moved to audio domain

## Benefits:
- **Reusable Core**: Audio processing independent of Discord
- **Clean Separation**: Discord is just one interface to audio core
- **Extensible**: Easy to add web interface, mobile app, API endpoints
- **Maintainable**: Clear domain boundaries

## Ready For:
- LLM integration can now coordinate audio → Whisper → classification → model routing
- Additional interfaces (web, mobile) can reuse the same audio core
- Microservices architecture when needed

🤖 Generated with [Claude Code](https://claude.ai/code)

Co-Authored-By: Claude <noreply@anthropic.com>
```

---

### 4. Commit: c7c9f346

- **Author:** Claude Code
- **Date:** 2025-07-26 13:37:17 -0400
- **Subject:** docs: enhance architecture with 3-way classification and rename tts to piper - UNTESTED

**Full Commit Message:**
```
docs: enhance architecture with 3-way classification and rename tts to piper - UNTESTED
```

---

### 5. Commit: dd0fc05d

- **Author:** Claude Code
- **Date:** 2025-07-26 13:32:29 -0400
- **Subject:** docs: final prep for LLM integration - architecture and package planning

**Full Commit Message:**
```
docs: final prep for LLM integration - architecture and package planning

## Updated Architecture Documentation
- Cleaned up CLAUDE.md with simplified flow diagram
- Defined complete LLM integration stack: DistilBERT → LangChain → LiteLLM → Ollama
- Streamlined architecture representation for better clarity

## Key Components Defined:
- **DistilBERT**: Intent classification (conversational vs agentic)
- **LangChain**: Prompt templates and chain orchestration
- **LiteLLM**: Unified model routing with OpenAI-compatible API
- **Ollama**: Model hosting (Llama 3.2 3B + Qwen 2.5-Coder 7B)

## Package Structure Updated:
```
src/llm/
├── client.py       # LiteLLM client for model routing
├── classifier.py   # DistilBERT intent classification
└── chains.py       # LangChain prompt templates and chains
```

## Architecture Benefits:
- Minimal complexity approach avoiding unnecessary microservices
- Clean domain separation within bot process
- Foundation ready for production LLM integration

Ready to begin Phase 3: LLM package implementation with modern AI stack.

🤖 Generated with [Claude Code](https://claude.ai/code)

Co-Authored-By: Claude <noreply@anthropic.com>
```

---


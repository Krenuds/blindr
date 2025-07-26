# Git Log - blindr

Generated on: 2025-07-26 07:23:13
Directory: /home/travis/blindr

## Last 5 Commits

### 1. Commit: 3c4aa790

- **Author:** Claude Code
- **Date:** 2025-07-26 07:18:36 -0400
- **Subject:** fix: Resolve Whisper hallucination issues causing duplicate text

**Full Commit Message:**
```
fix: Resolve Whisper hallucination issues causing duplicate text

## Issues Fixed:
1. WhisperClient parameter errors - removed unsupported parameters
2. Improved prompt mode activation with debug logging
3. Enhanced silence trimming to reduce audio artifacts
4. Better audio quality filtering to prevent repetitive transcriptions

## Key Changes:
- Remove unsupported temperature/no_speech_threshold parameters
- Add debug logging for prompt mode state tracking
- Stricter silence trimming (5% threshold vs 2%)
- Empty initial_prompt for longer segments to prevent patterns
- More aggressive audio artifact filtering

## Expected Result:
- No more repetitive "9 9 9 9..." transcriptions
- Proper prompt mode activation and accumulation
- Cleaner audio processing with fewer artifacts
- Better handling of short audio segments

🤖 Generated with [Claude Code](https://claude.ai/code)

Co-Authored-By: Claude <noreply@anthropic.com>
```

---

### 2. Commit: 01d812e4

- **Author:** Claude Code
- **Date:** 2025-07-26 07:09:49 -0400
- **Subject:** fix: Remove duplicate finalize_prompt method causing transcription issues

**Full Commit Message:**
```
fix: Remove duplicate finalize_prompt method causing transcription issues

The StreamingAudioSink class had two finalize_prompt methods defined (lines 464-497 and 590-616), causing the second definition to overwrite the first. This led to missing error handling and potential issues with prompt finalization.

🤖 Generated with [Claude Code](https://claude.ai/code)

Co-Authored-By: Claude <noreply@anthropic.com>
```

---

### 3. Commit: 9b30683a

- **Author:** Claude Code
- **Date:** 2025-07-26 07:08:26 -0400
- **Subject:** fix: Remove duplicate words in prompt mode transcriptions

**Full Commit Message:**
```
fix: Remove duplicate words in prompt mode transcriptions

## Issue:
When counting 'one twice three four', the word 'twice' appeared duplicated
in transcriptions due to incorrect merge logic being applied in prompt mode.

## Root Cause:
merge_transcriptions() was being called for every segment in prompt mode,
but this merge logic is designed for continuous streaming, not prompt
accumulation. The overlap buffer already handles audio overlap properly.

## Fix:
- Skip merge_transcriptions() in prompt mode
- Accumulate raw transcribed_text without merging
- Only apply merge logic in continuous (non-prompt) mode
- This preserves natural speech boundaries in prompts

## Expected Result:
- No more duplicate words in prompt transcriptions
- Cleaner, more accurate prompt accumulation
- 'one twice three four' will appear as intended without duplicates

🤖 Generated with [Claude Code](https://claude.ai/code)

Co-Authored-By: Claude <noreply@anthropic.com>
```

---

### 4. Commit: e26f21f3

- **Author:** Claude Code
- **Date:** 2025-07-26 07:03:47 -0400
- **Subject:** fix: Replace broken packet-based silence detection with time-based detection

**Full Commit Message:**
```
fix: Replace broken packet-based silence detection with time-based detection

## Critical Bug Fix:
Discord only sends audio packets during speech (built-in VAD), so our
packet-based silence detection never triggered, causing 157s delays.

## Changes:
- Remove broken 'else' block in write() that waited for silence packets
- Add time-based timeout detection using background asyncio tasks
- Track user_last_packet_time and user_timeout_tasks
- Cancel/restart timeout tasks on new speech packets
- Process accumulated prompts after 2s timeout (configurable)
- Add proper timeout_handler() and finalize_prompt() methods

## Expected Result:
- Consistent 2-3 second response times instead of minutes
- Proper silence detection regardless of background noise
- No more indefinite prompt accumulation

This fixes the fundamental architectural flaw in silence detection.

🤖 Generated with [Claude Code](https://claude.ai/code)

Co-Authored-By: Claude <noreply@anthropic.com>
```

---

### 5. Commit: e432e0ac

- **Author:** Claude Code
- **Date:** 2025-07-26 06:39:04 -0400
- **Subject:** feat: Add members intent for efficient username resolution

**Full Commit Message:**
```
feat: Add members intent for efficient username resolution

- Add intents.members = True to bot configuration
- This enables access to Discord's member cache for fast username lookup
- Now uses guild.get_member() (cached) instead of guild.fetch_member() (API call)
- Significantly improves performance of transcription username display

Thanks to Discord API documentation for identifying the missing intent\!

🤖 Generated with [Claude Code](https://claude.ai/code)

Co-Authored-By: Claude <noreply@anthropic.com>
```

---


# Git Log - blindr

Generated on: 2025-07-26 06:12:49
Directory: /home/travis/blindr

## Last 5 Commits

### 1. Commit: fbfb033d

- **Author:** Claude Code
- **Date:** 2025-07-26 06:11:05 -0400
- **Subject:** feat: Add !clear command and remove Discord mentions from transcriptions

**Full Commit Message:**
```
feat: Add !clear command and remove Discord mentions from transcriptions

- Added !clear command to delete all transcription messages from channel
- Replace Discord mentions (@user) with display names to avoid pings
- Updated help text to include new !clear command

🤖 Generated with [Claude Code](https://claude.ai/code)

Co-Authored-By: Claude <noreply@anthropic.com>
```

---

### 2. Commit: e4c33840

- **Author:** Claude Code
- **Date:** 2025-07-26 06:00:16 -0400
- **Subject:** Update git logs

**Full Commit Message:**
```
Update git logs
```

---

### 3. Commit: 7065cc4e

- **Author:** Claude Code
- **Date:** 2025-07-26 05:57:16 -0400
- **Subject:** fix: Resolve Whisper hallucination issues causing duplicate text

**Full Commit Message:**
```
fix: Resolve Whisper hallucination issues causing duplicate text

## Changes Made
✅ Fixed duplicate prompt posting when hitting 30s hard cap
✅ Added silence trimming to reduce Whisper hallucinations
✅ Removed repetitive initial prompts that appeared in transcriptions
✅ Improved prompt state management with finalizing flag

## Technical Details
- Added `user_prompt_finalizing` flag to prevent race conditions
- Implemented audio silence trimming (2% energy threshold)
- Simplified initial_prompt to avoid repetitive text in output
- Fixed variable reference error (audio_data -> audio_segment)

## Results
- No more duplicate Discord messages when prompts hit 30s limit
- Significantly reduced repetitive text patterns in transcriptions
- Cleaner, more natural transcription output

Tested with continuous voice input and verified improvements.

🤖 Generated with [Claude Code](https://claude.ai/code)

Co-Authored-By: Claude <noreply@anthropic.com>
```

---

### 4. Commit: 7e6b3649

- **Author:** Claude Code
- **Date:** 2025-07-25 23:05:39 -0400
- **Subject:** feat: Implement prompt mode for 30-second voice inputs 🎙️

**Full Commit Message:**
```
feat: Implement prompt mode for 30-second voice inputs 🎙️

## Major Changes
✅ Added prompt mode configuration to Discord bot
✅ Implemented 30-second hard cap for voice prompts
✅ Extended silence timeout to 2 seconds for natural pauses
✅ Accumulate transcriptions until prompt completion
✅ Output combined prompt as [PROMPT X.Xs] format

## Technical Implementation
- Added prompt_mode, prompt_silence_timeout, prompt_max_duration configs
- Track prompt state with user_prompt_active/start/transcriptions
- Accumulate segments with 📝 indicator
- Finalize prompts on silence timeout or hard cap
- Prevent multiple finalizations with state management

## Whisper Optimization
- Force English language detection to reduce hallucinations
- Add initial_prompt for better transcription context
- Maintain existing overlap buffer strategy

The bot now intelligently handles longer voice inputs up to 30 seconds,
perfect for complex prompts that will be sent to LLMs for processing.

🤖 Generated with [Claude Code](https://claude.ai/code)

Co-Authored-By: Claude <noreply@anthropic.com>
```

---

### 5. Commit: 5310afc6

- **Author:** Claude Code
- **Date:** 2025-07-25 22:46:17 -0400
- **Subject:** Update CLAUDE.md with PROJECT SETUP section and add numpy to requirements.txt

**Full Commit Message:**
```
Update CLAUDE.md with PROJECT SETUP section and add numpy to requirements.txt
```

---


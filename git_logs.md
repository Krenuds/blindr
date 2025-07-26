# Git Log - blindr

Generated on: 2025-07-26 07:06:47
Directory: /home/travis/blindr

## Last 5 Commits

### 1. Commit: e26f21f3

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

### 2. Commit: e432e0ac

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

### 3. Commit: 82c8ee89

- **Author:** Claude Code
- **Date:** 2025-07-26 06:28:08 -0400
- **Subject:** fix: Improve username lookup for transcriptions

**Full Commit Message:**
```
fix: Improve username lookup for transcriptions

- Add multiple fallback methods for getting usernames
- Try guild.get_member(), then guild.fetch_member(), then bot.get_user()
- Use text_channel.guild instead of channel.guild for more reliable access
- Add better logging to show which username was resolved

This should fix the 'User 1080530572365004830' display issue.

🤖 Generated with [Claude Code](https://claude.ai/code)

Co-Authored-By: Claude <noreply@anthropic.com>
```

---

### 4. Commit: 0c5a71c9

- **Author:** Claude Code
- **Date:** 2025-07-26 06:24:48 -0400
- **Subject:** feat: Simplify commands and add transcription toggle

**Full Commit Message:**
```
feat: Simplify commands and add transcription toggle

- Remove status, stream_info, and clear commands
- Keep only transcribe and clearall commands
- Convert transcribe to toggle transcription on/off globally
- Add transcription_enabled flag to control message sending
- Update help text to show simplified command set
- Transcribe command shows status and available commands

🤖 Generated with [Claude Code](https://claude.ai/code)

Co-Authored-By: Claude <noreply@anthropic.com>
```

---

### 5. Commit: e235c345

- **Author:** Claude Code
- **Date:** 2025-07-26 06:16:19 -0400
- **Subject:** feat: Improve clear commands with bulk delete and add clearall

**Full Commit Message:**
```
feat: Improve clear commands with bulk delete and add clearall

- Replace slow individual deletion with Discord's bulk delete API
- \!clear now uses channel.purge() for instant deletion (100 msgs at once)
- Add \!clearall command to clear entire channel with confirmation
- For channels >1000 messages, clearall uses clone/delete method
- Update help text to include both clear commands
- Fix Discord rate limiting issues during message deletion

🤖 Generated with [Claude Code](https://claude.ai/code)

Co-Authored-By: Claude <noreply@anthropic.com>
```

---


# Git Log - blindr

Generated on: 2025-07-26 06:38:46
Directory: /home/travis/blindr

## Last 5 Commits

### 1. Commit: 82c8ee89

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

### 2. Commit: 0c5a71c9

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

### 3. Commit: e235c345

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

### 4. Commit: fbfb033d

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

### 5. Commit: e4c33840

- **Author:** Claude Code
- **Date:** 2025-07-26 06:00:16 -0400
- **Subject:** Update git logs

**Full Commit Message:**
```
Update git logs
```

---


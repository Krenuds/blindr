# Phase 2 Testing Requirements 🧪

**Status**: Implementation complete, ready for live Discord testing

## ✅ Completed Tests

### Infrastructure Tests
- **✅ Whisper Service**: Healthy on CUDA with 'small' model (RTX 2080)
- **✅ Dependencies**: All Python modules import successfully  
- **✅ Environment**: All required environment variables present
- **✅ Directories**: Logs and recorded_audio directories with write permissions
- **✅ Bot Initialization**: Discord bot creates successfully with proper intents

### Component Tests  
- **✅ WhisperClient**: Connects to service and retrieves health status
- **✅ StreamingAudioSink**: Creates, configures, and cleans up properly
- **✅ Integration**: All components work together in isolation

## 🔄 Pending Live Tests

### Critical Tests (Must Pass for Phase 2 Completion)
1. **Discord Connection**: Bot connects to Discord and joins voice channel
2. **Auto-join**: Bot automatically finds and joins 'blindr' voice channel  
3. **Streaming Start**: StreamingAudioSink begins processing on voice connection
4. **Voice Detection**: Energy-based VAD detects speech above threshold (50)
5. **Real-time Transcription**: 3-second audio segments transcribed by Whisper
6. **Discord Feedback**: Transcriptions appear in Discord text channels immediately

### Quality Tests (Should Pass for Production Readiness)
1. **Transcription Accuracy**: >90% accuracy on clear speech
2. **Latency**: <5 seconds from speech to Discord transcription message
3. **Multi-user**: Handles multiple users speaking simultaneously  
4. **Error Recovery**: Graceful handling of network/service interruptions
5. **Resource Usage**: Reasonable CPU/memory consumption during streaming

## 🛠️ Manual Testing Setup

### Prerequisites
1. **Discord Server**: Bot must be invited to a Discord server
2. **Voice Channel**: Create channel named 'blindr' (or update `VOICE_CHANNEL_NAME`)
3. **Permissions**: Bot needs voice channel connect/speak permissions
4. **Test Users**: At least one human user to speak in voice channel

### Testing Commands
```bash
# Start the bot
python3 src/bot.py

# Test commands in Discord text channel
!status       # Verify bot status and streaming
!stream_info  # Check detailed streaming metrics  
!transcribe   # Test Whisper service connection
```

### Expected Behavior
1. **Bot Startup**: Connects to Discord and joins voice channel automatically
2. **Streaming Indicator**: `!status` shows "Continuous streaming active"
3. **Voice Input**: Speaking in voice channel triggers real-time transcriptions
4. **Text Output**: Transcriptions appear as: `🎤 @username (duration): "transcribed text"`

## 🚨 Known Limitations

### Current Constraints
- **Energy-based VAD**: Simple threshold detection (may miss quiet speech)
- **Buffer Size**: 3-second segments (longer sentences may be split)
- **Single Channel**: Only monitors configured voice channel
- **Text Output Only**: No voice responses yet (Phase 4)

### Error Conditions  
- **Missing Voice Channel**: Bot cannot find 'blindr' channel
- **Whisper Service Down**: Transcriptions fail silently
- **Network Issues**: May cause audio buffer overruns
- **Discord Rate Limits**: Too many messages may get throttled

## 📊 Success Criteria

### Phase 2 Completion Requirements
- [ ] Bot connects to Discord successfully
- [ ] Auto-joins configured voice channel  
- [ ] Streaming audio sink activates automatically
- [ ] Real-time voice transcription works for test phrases
- [ ] Transcriptions appear in Discord within 5 seconds
- [ ] System handles basic error scenarios gracefully

### Ready for Phase 3 When:
- All critical tests pass consistently
- Basic transcription accuracy validated
- System demonstrates stability over 15+ minutes
- Error handling prevents crashes

## 🔧 Troubleshooting

### Common Issues
1. **Bot Won't Connect**: Check Discord token in `.env`
2. **No Voice Channel**: Verify 'blindr' channel exists
3. **No Transcriptions**: Check Whisper service with `curl http://localhost:9000/health`
4. **Permission Errors**: Ensure bot has voice channel permissions
5. **Import Errors**: Verify all dependencies installed (discord.py, numpy, etc.)

### Debug Commands
```bash
# Check Whisper service
curl http://localhost:9000/health

# Test imports
python3 -c "import discord; from src.whisper_client import WhisperClient; print('OK')"

# Verify environment
python3 -c "import os; from dotenv import load_dotenv; load_dotenv(); print('Token:', 'OK' if os.getenv('DISCORD_BOT_TOKEN') else 'MISSING')"
```

---

**Next Step**: Run live Discord testing to validate the streaming audio pipeline works end-to-end with real voice input.
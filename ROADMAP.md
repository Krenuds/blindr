# Discord AI Bot - Development Roadmap

## 📋 Development Philosophy
Build and test each component in isolation, then integrate step by step. Start with Discord interaction and work backwards through the pipeline.

---

## 🛠️ Project Infrastructure (COMPLETED)
**Goal**: Establish development workflow, project tracking, and automation systems

### Development Workflow
- [x] Set up git repository with clean structure
- [x] Create comprehensive project documentation (CLAUDE.md, ROADMAP.md)
- [x] Implement automated git log generation (makeGitLogs utility)
- [x] Set up Claude Code hooks for workflow automation

### Project Tracking System
- [x] Build roadmap progress tracker (roadmap_tracker.py)
- [x] Implement phase completion detection
- [x] Create automated commit system for milestone completion
- [x] Set up project context injection for Claude sessions

### Hook System
- [x] UserPromptSubmit hook - automatic project context loading
- [x] Stop hook - phase completion detection and auto-commit
- [x] PostToolUse hook - development workflow reminders

**Milestone**: Complete development infrastructure with automated project tracking and workflow management

---

## Phase 1: Discord Foundation 🎮 (COMPLETED ✅)
**Goal**: Get a basic Discord bot running with voice channel capabilities

### Week 1-2: Basic Bot Setup
- [x] Set up Python development environment
- [x] Create Discord application and bot account
- [x] Install discord.py with voice support
- [x] Create basic bot that can:
  - [x] Connect to Discord
  - [x] Join/leave voice channels
  - [x] Respond to text commands
- [x] Test voice channel connection stability

### Week 2-3: Voice Capture
- [x] Implement voice recording using AudioSink
- [x] Capture Opus packets from Discord
- [x] Decode Opus to PCM format
- [x] Save audio to files for testing
- [x] Test with multiple users speaking

**Milestone**: ✅ Bot can join voice channels and save audio files

---

## Phase 2: Speech-to-Text Integration 🎤
**Goal**: Convert captured audio to text

### Week 3-4: Whisper Setup
- [ ] Deploy Whisper in Docker container
- [ ] Set up REST API endpoint (port 9000)
- [ ] Test Whisper with saved audio files
- [ ] Optimize model size (base vs small vs medium)

### Week 4-5: Bot-to-Whisper Pipeline
- [ ] Connect bot to Whisper API
- [ ] Stream audio from Discord to Whisper
- [ ] Handle transcription results
- [ ] Add error handling and retries
- [ ] Log all transcriptions for debugging

**Milestone**: Bot transcribes voice to text in real-time

---

## Phase 3: Basic LLM Integration 🤖
**Goal**: Generate responses without routing

### Week 5-6: Ollama Setup
- [ ] Install Ollama locally
- [ ] Download and test Llama 3.2 model
- [ ] Create simple HTTP client for Ollama
- [ ] Test response generation

### Week 6-7: Simple Chat Loop
- [ ] Connect transcribed text to Ollama
- [ ] Generate responses with Llama 3.2
- [ ] Return text responses to Discord (text channel first)
- [ ] Test conversation flow

**Milestone**: Voice input generates AI text responses

---

## Phase 4: Text-to-Speech 🔊
**Goal**: Complete the voice loop

### Week 7-8: Piper Setup
- [ ] Deploy Piper TTS in Docker
- [ ] Test different voice models
- [ ] Create API wrapper for Piper
- [ ] Generate audio files from text

### Week 8-9: Voice Response
- [ ] Convert AI responses to speech
- [ ] Stream audio back to Discord
- [ ] Handle audio queuing (multiple responses)
- [ ] Optimize for latency

**Milestone**: Full voice-to-voice conversation working

---

## Phase 5: API Gateway 🌐
**Goal**: Centralize communication between services

### Week 9-10: FastAPI Development
- [ ] Create FastAPI application structure
- [ ] Design RESTful endpoints:
  - [ ] POST /transcribe
  - [ ] POST /generate
  - [ ] POST /synthesize
- [ ] Move all service communication to API
- [ ] Add request/response logging
- [ ] Implement error handling

### Week 10-11: Refactor Bot
- [ ] Update bot to use API Gateway
- [ ] Remove direct service connections
- [ ] Add retry logic
- [ ] Test complete flow through API

**Milestone**: All services communicate through central API

---

## Phase 6: Intelligent Routing 🧠
**Goal**: Route requests based on intent

### Week 11-12: DistilBERT Classifier
- [ ] Create intent classification service
- [ ] Train/fine-tune on conversational vs agentic examples
- [ ] Deploy as FastAPI microservice
- [ ] Test classification accuracy

### Week 12-13: LiteLLM Integration
- [ ] Deploy LiteLLM proxy
- [ ] Configure routing rules
- [ ] Add Qwen 2.5-Coder to Ollama
- [ ] Create custom routing strategy
- [ ] Test model selection logic

### Week 13-14: Complete Routing
- [ ] Integrate classifier with API Gateway
- [ ] Route requests through LiteLLM
- [ ] Test both conversation and coding paths
- [ ] Monitor routing decisions

**Milestone**: Bot intelligently selects appropriate AI model

---

## Phase 7: Optimization & Polish ⚡
**Goal**: Production-ready system

### Week 14-15: Performance
- [ ] Add Redis caching layer
- [ ] Implement response streaming
- [ ] Optimize Docker configurations
- [ ] Reduce latency at each step
- [ ] Add performance monitoring

### Week 15-16: Reliability
- [ ] Create Docker Compose for full stack
- [ ] Add health checks for all services
- [ ] Implement graceful error handling
- [ ] Create backup/fallback paths
- [ ] Add comprehensive logging

### Week 16-17: User Experience
- [ ] Add voice activity detection
- [ ] Implement conversation context
- [ ] Create user preferences system
- [ ] Add command shortcuts
- [ ] Polish response formatting

**Milestone**: Production-ready voice assistant

---

## Phase 8: Deployment & Documentation 📚
**Goal**: Easy deployment and maintenance

### Week 17-18: Final Preparation
- [ ] Write comprehensive documentation
- [ ] Create deployment scripts
- [ ] Add environment configuration
- [ ] Create troubleshooting guide
- [ ] Record demo videos

---

## 🎯 Success Metrics

### Phase Checkpoints
1. **Phase 1**: Bot stays connected for 1 hour without crashes
2. **Phase 2**: 90%+ transcription accuracy
3. **Phase 3**: <3 second response time
4. **Phase 4**: Natural sounding voice output
5. **Phase 5**: All services accessible via API
6. **Phase 6**: 95%+ routing accuracy
7. **Phase 7**: <1 second average latency
8. **Phase 8**: One-command deployment

### Final Goals
- ✅ Complete voice-to-voice conversations
- ✅ Intelligent model selection
- ✅ Production stability
- ✅ Easy to deploy and maintain
- ✅ Extensible architecture

## 🚀 Next Steps After MVP
- Add more specialized models
- Implement multi-language support
- Create web dashboard
- Add conversation memory
- Integrate with external tools
- Scale to multiple Discord servers
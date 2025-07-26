# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview
The user is that you tutor them as they learn about AI models and MCP. Please take it slow. This should be a learning experience for them.


**CRITICAL RULES**
- Always begin sessions by reading the latest 3 commits in git_logs.md
- Read Requirements.txt
- Always consult online documentation for each module while planning. 
- Test all code after finishing each task before moving on by reading the service logs.
- Git commit with comment after successfully completing tasks.  
- All models are running locally. Either via docker or as system services.

## PROJECT SETUP

**Current Stack Status:**
- ✅ **Discord Bot**: Python 3.12+ with py-cord 2.6.1
  - Continuous audio streaming with overlap buffer (5s segments, 0.5s overlap)
  - Energy-based VAD with 50 threshold
  - Real-time transcription to Discord channels
  
- ✅ **Whisper STT**: Native service on port 9000
  - Using 'small' model with CUDA acceleration (RTX 2080)
  - Handles 16kHz mono WAV audio
  - ~300ms response time for 5s segments
  
- ⏳ **Ollama**: Not yet installed (Phase 3)
  - Will host Llama 3.2 (3B) for conversational responses
  - Will host Qwen 2.5-Coder (7B) for agentic tasks
  
- ⏳ **Piper TTS**: Not yet deployed (Phase 4)
  - Will run in Docker on port 10200
  
- ⏳ **FastAPI Gateway**: Not yet implemented (Phase 5)
  - Will centralize all service communication on port 8000
  
- ⏳ **LiteLLM Router**: Not yet deployed (Phase 6)
  - Will handle intelligent model routing on port 4000
  
- ⏳ **DistilBERT Classifier**: Not yet implemented (Phase 6)
  - Will classify intents on port 8001

**Dependencies** (requirements.txt):
- py-cord==2.6.1
- python-dotenv==1.1.1
- aiohttp==3.12.14
- numpy==1.26.4 (for audio processing)
- asyncio (built-in)

**PROJECT OVERVIEW** 
```
graph TB
    %% User Layer
    subgraph "User Layer"
        User[("👤 Discord User")]
    end

    %% Discord Layer
    subgraph "Discord Platform"
        DiscordServer["🎮 Discord Server<br/>Voice Channel"]
    end

    %% Bot Layer
    subgraph "Bot Service"
        Bot["🤖 Discord Bot<br/>Python 3.12+<br/>py-cord<br/>AudioSink Voice Recording"]
    end

    %% API Gateway Layer
    subgraph "API Gateway"
        API["🌐 FastAPI<br/>Port: 8000"]
    end

    %% Speech Processing Layer
    subgraph "Speech Processing"
        Whisper["🎤 Whisper STT<br/>Native Service<br/>Port: 9000"]
        Piper["🔊 Piper TTS<br/>Docker Container<br/>Port: 10200"]
    end

    %% Intelligence Layer
    subgraph "Intelligence & Routing"
        Classifier["🧠 DistilBERT<br/>Intent Classifier<br/>Port: 8001"]
        LiteLLM["🔀 LiteLLM Router<br/>Proxy Server<br/>Port: 4000"]
    end

    %% Model Layer
    subgraph "Model Hosting"
        Ollama["💾 Ollama<br/>Model Host<br/>Port: 11434"]
        Llama["💬 Llama 3.2<br/>3B Model<br/>Conversational"]
        Qwen["⚙️ Qwen 2.5-Coder<br/>7B Model<br/>Coding/Tools"]
    end

    %% Optional Storage
    subgraph "Cache Layer"
        Redis[("🗄️ Redis<br/>Cache/Sessions<br/>Port: 6379")]
    end

    %% User Voice Flow
    User -->|"🎤 Voice Input"| DiscordServer
    DiscordServer -->|"📡 Opus Packets<br/>48kHz"| Bot
    
    %% Audio Processing
    Bot -->|"🔄 Decode Opus → PCM<br/>16-bit 48kHz"| API
    API -->|"🎵 PCM/WAV Audio"| Whisper
    Whisper -->|"📝 Transcribed Text"| API

    %% Intelligence Routing
    API -->|"❓ User Query"| Classifier
    Classifier -->|"🏷️ Intent Classification<br/>(conversational/agentic)"| API
    API -->|"📨 Routed Request"| LiteLLM
    
    %% Model Selection
    LiteLLM -->|"🚦 Route Decision"| Ollama
    Ollama -->|"💭 Conversational Route"| Llama
    Ollama -->|"🛠️ Agentic Route"| Qwen
    
    %% Response Generation
    Llama -->|"💬 Response Text"| Ollama
    Qwen -->|"📋 Response Text"| Ollama
    Ollama -->|"✨ Generated Text"| LiteLLM
    LiteLLM -->|"📤 Response"| API

    %% Text-to-Speech
    API -->|"📄 Response Text"| Piper
    Piper -->|"🎶 Audio Stream<br/>WAV/PCM"| API
    
    %% Voice Output
    API -->|"🔉 Audio Data"| Bot
    Bot -->|"🔊 Voice Output"| DiscordServer
    DiscordServer -->|"🎧 Audio Stream"| User

    %% Cache Integration
    API -.->|"🔍 Cache Check"| Redis
    Redis -.->|"💾 Cached Data"| API    
```


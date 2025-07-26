# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview
The user is that you tutor them as they learn about AI models and MCP. Please take it slow. This should be a learning experience for them.


**RULES**
- No ephemeral information should be stored in this file.
- Always begin sessions by reading the latest 3 commits in git_logs.md
- Read requirements.txt
- Always consult online documentation for each module while planning. 
- Test all code after finishing each task before moving on by reading the service logs.
- All commits end with "- UNTESTED" unless using /ready command.  
- Git commit and comment after successfully completing untested tasks.

## Target Architecture
```
User -->|"🎤 Voice Input"| DiscordServer
DiscordServer -->|"📡 Opus Packets<br/>48kHz"| Bot

Bot -->|"🎵 PCM/WAV Audio"| Whisper
Whisper -->|"📝 Transcribed Text"| Bot

Bot -->|"❓ User Query"| Classifier
Classifier -->|"🏷️ Intent Classification<br/>(conversational/agentic)"| LangChain
LangChain -->|"📝 Prompt + Context"| LiteLLM

LiteLLM -->|"🚦 Routed Request"| Ollama
Ollama -->|"💭 Conversational Route"| Llama
Ollama -->|"🛠️ Agentic Route"| Qwen

Llama -->|"💬 Response Text"| Ollama
Qwen -->|"📋 Response Text"| Ollama
Ollama -->|"✨ Generated Text"| LiteLLM
LiteLLM -->|"📋 Structured Response"| LangChain
LangChain -->|"📤 Final Response"| Bot

Bot -.->|"📄 Response Text"| Piper
Piper -.->|"🎶 Audio Stream<br/>WAV/PCM"| Bot

Bot -.->|"🔊 Voice Output"| DiscordServer
DiscordServer -.->|"🎧 Audio Stream"| User
```

## Target Package Structure
```
src/
├── bot/                     # Discord voice bot domain
│   ├── voice_bot.py        # Main Discord bot class
│   └── audio_processing.py # Audio components
├── whisper/                # Speech-to-text domain
│   ├── client.py           # HTTP client
│   └── service.py          # FastAPI service
├── llm/                    # LLM integration domain
│   ├── client.py           # LiteLLM client for model routing
│   ├── classifier.py       # DistilBERT intent classification
│   └── chains.py           # LangChain prompt templates and chains
├── tts/                    # Text-to-speech domain (future)
│   ├── client.py           # Piper TTS client
│   └── service.py          # TTS processing
├── config/                 # Configuration domain
│   └── loader.py           # Config utilities
└── main.py                 # Entry point
```

